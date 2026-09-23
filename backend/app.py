import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

vector_db = Chroma(
    persist_directory="./chroma_db",
    embedding_function=embedding_model
)

retriever = vector_db.as_retriever(
    search_type="mmr",
    search_kwargs={
        "k": 4,
        "fetch_k": 10
    }
)

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    api_key=groq_api_key
)

class Question(BaseModel):
    question: str

@app.get("/")
def home():
    return {
        "message": "RAG API is running"
    }

@app.post("/ask")
def ask_question(data: Question):
    retrieved_docs = retriever.invoke(data.question)

    context = "\n\n".join(
        doc.page_content
        for doc in retrieved_docs
    )

    prompt = f"""
Answer the question using only the context below.

If the answer is not available in the context, say:

"I could not find the answer in the PDF."

Do not make up information.

Context:

{context}

Question:

{data.question}
"""

    response = llm.invoke(prompt)

    answer = response.content

    if isinstance(answer, list):
        answer = "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in answer
        )

    return {
        "answer": answer
    }
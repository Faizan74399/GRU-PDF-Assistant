import os
import uuid

from dotenv import load_dotenv

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")

if not groq_api_key:
    raise ValueError("GROQ_API_KEY is missing from .env file")

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

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    api_key=groq_api_key
)

UPLOAD_DIR = "uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)


class Question(BaseModel):
    question: str
    document_id: str


@app.get("/")
def home():
    return {
        "message": "RAG API is running"
    }


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file selected."
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed."
        )

    document_id = uuid.uuid4().hex

    original_filename = file.filename

    file_path = os.path.join(
        UPLOAD_DIR,
        f"{document_id}.pdf"
    )

    file_content = await file.read()

    if not file_content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded PDF is empty."
        )

    with open(file_path, "wb") as f:
        f.write(file_content)

    try:
        loader = PyPDFLoader(file_path)

        docs = loader.load()

        if not docs:
            raise HTTPException(
                status_code=400,
                detail="Could not read the PDF."
            )

        for doc in docs:
            doc.metadata["filename"] = original_filename

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )

        chunks = text_splitter.split_documents(docs)

        for chunk in chunks:
            chunk.metadata["filename"] = original_filename

        collection_name = f"pdf_{document_id}"

        Chroma.from_documents(
            documents=chunks,
            embedding=embedding_model,
            collection_name=collection_name,
            persist_directory="./chroma_db"
        )

        return {
            "message": "PDF processed successfully",
            "document_id": document_id,
            "filename": original_filename,
            "pages": len(docs),
            "chunks": len(chunks)
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"PDF processing failed: {str(e)}"
        )


@app.post("/ask")
def ask_question(data: Question):
    if not data.question.strip():
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty."
        )

    if not data.document_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Document ID is required."
        )

    collection_name = f"pdf_{data.document_id}"

    try:
        vector_db = Chroma(
            persist_directory="./chroma_db",
            collection_name=collection_name,
            embedding_function=embedding_model
        )

        retriever = vector_db.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": 4,
                "fetch_k": 10
            }
        )

        retrieved_docs = retriever.invoke(
            data.question
        )

        if not retrieved_docs:
            return {
                "answer": "I could not find the answer in the PDF.",
                "sources": []
            }

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

        sources = []

        for doc in retrieved_docs:
            page = doc.metadata.get("page", 0) + 1

            filename = doc.metadata.get(
                "filename",
                "Uploaded PDF"
            )

            sources.append({
                "filename": filename,
                "page": page,
                "content": doc.page_content
            })

        return {
            "answer": answer,
            "sources": sources
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Question processing failed: {str(e)}"
        )
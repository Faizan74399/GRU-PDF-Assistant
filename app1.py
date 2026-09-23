import os
import streamlit as st
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")

st.set_page_config(
    page_title="GRU PDF Assistant",
    page_icon="📚"
)

st.title("📚 GRU PDF Assistant")

@st.cache_resource
def load_rag():
    embedding_model = GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-001",
        google_api_key=api_key
    )

    vector_db = Chroma(
        persist_directory="./chroma_db",
        embedding_function=embedding_model
    )

    retriever = vector_db.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 4, "fetch_k": 10}
    )

    llm = ChatGoogleGenerativeAI(
        model="gemini-3.7-flash",
        google_api_key=api_key
    )

    return retriever, llm

retriever, llm = load_rag()

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("Ask something about the GRU PDF...")

if question:
    st.session_state.messages.append({
        "role": "user",
        "content": question
    })

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            retrieved_docs = retriever.invoke(question)

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
{question}
"""

            response = llm.invoke(prompt)
            answer = response.content[0]["text"]

        st.markdown(answer)

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer
    })
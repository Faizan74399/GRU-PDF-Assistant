import io
import math
import os
import re
import time
import uuid
from collections import Counter, OrderedDict

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from pydantic import BaseModel
from pypdf import PdfReader

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = "openai/gpt-oss-20b"

MAX_FILE_SIZE = 20 * 1024 * 1024
MAX_PAGES = 200
MAX_DOCUMENTS = 2
MAX_CHUNKS_PER_DOCUMENT = 1500
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
TOP_K = 4
MAX_QUESTION_LENGTH = 2000

documents = OrderedDict()

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

app = FastAPI(title="RAG PDF Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


class Question(BaseModel):
    question: str
    document_id: str


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def tokenize(text):
    return re.findall(r"\b[a-zA-Z0-9_]{2,}\b", text.lower())


def split_text(text):
    text = clean_text(text)

    if not text:
        return []

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + CHUNK_SIZE, text_length)

        if end < text_length:
            boundary = text.rfind(" ", start, end)

            if boundary > start + int(CHUNK_SIZE * 0.6):
                end = boundary

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        next_start = end - CHUNK_OVERLAP

        if next_start <= start:
            next_start = end

        start = next_start

    return chunks


def build_index(chunks):
    document_frequency = Counter()
    token_counts = []

    for chunk in chunks:
        counts = Counter(tokenize(chunk["content"]))
        token_counts.append(counts)

        for token in counts:
            document_frequency[token] += 1

    total_chunks = len(chunks)
    vectors = []

    for counts in token_counts:
        vector = {}
        magnitude = 0.0

        for token, count in counts.items():
            idf = math.log(
                (total_chunks + 1) / (document_frequency[token] + 1)
            ) + 1

            weight = (1 + math.log(count)) * idf
            vector[token] = weight
            magnitude += weight * weight

        magnitude = math.sqrt(magnitude)

        if magnitude > 0:
            for token in vector:
                vector[token] /= magnitude

        vectors.append(vector)

    return vectors, document_frequency


def create_query_vector(question, document_frequency, total_chunks):
    counts = Counter(tokenize(question))

    if not counts:
        return {}

    vector = {}
    magnitude = 0.0

    for token, count in counts.items():
        if token not in document_frequency:
            continue

        idf = math.log(
            (total_chunks + 1) / (document_frequency[token] + 1)
        ) + 1

        weight = (1 + math.log(count)) * idf
        vector[token] = weight
        magnitude += weight * weight

    magnitude = math.sqrt(magnitude)

    if magnitude > 0:
        for token in vector:
            vector[token] /= magnitude

    return vector


def cosine_similarity(query_vector, document_vector):
    if not query_vector or not document_vector:
        return 0.0

    if len(query_vector) > len(document_vector):
        query_vector, document_vector = document_vector, query_vector

    return sum(
        value * document_vector.get(token, 0.0)
        for token, value in query_vector.items()
    )


def retrieve_chunks(document, question):
    chunks = document["chunks"]

    query_vector = create_query_vector(
        question,
        document["document_frequency"],
        len(chunks)
    )

    scored_chunks = []

    for index, chunk in enumerate(chunks):
        score = cosine_similarity(
            query_vector,
            chunk["vector"]
        )

        scored_chunks.append(
            (score, index, chunk)
        )

    scored_chunks.sort(
        key=lambda item: item[0],
        reverse=True
    )

    selected = []

    for score, index, chunk in scored_chunks[:TOP_K]:
        if score > 0:
            selected.append(
                {
                    "score": round(score, 4),
                    "index": index,
                    "chunk": chunk
                }
            )

    if not selected:
        selected = [
            {
                "score": 0.0,
                "index": index,
                "chunk": chunk
            }
            for index, chunk in enumerate(chunks[:TOP_K])
        ]

    return selected


def get_status_code(error):
    status_code = getattr(error, "status_code", None)

    if status_code:
        return status_code

    response = getattr(error, "response", None)

    if response:
        return getattr(response, "status_code", None)

    return None


def groq_answer(context, question):
    if not groq_client:
        return None, "Groq API key is not configured."

    system_prompt = """
You are a PDF question-answering assistant.

Answer using only the provided PDF context.

Do not use outside knowledge.

If the answer cannot be found in the provided context, respond exactly:

I could not find the answer in the PDF.

Keep the answer clear, accurate, and concise.
"""

    user_prompt = f"""
PDF context:

{context}

Question:

{question}
"""

    last_error = None

    for attempt in range(2):
        try:
            response = groq_client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                temperature=0.2,
                max_completion_tokens=700
            )

            answer = response.choices[0].message.content

            if answer:
                return answer.strip(), None

            return "I could not find the answer in the PDF.", None

        except Exception as error:
            last_error = error
            status_code = get_status_code(error)

            if status_code in {429, 500, 502, 503, 504} and attempt == 0:
                time.sleep(1)
                continue

            break

    status_code = get_status_code(last_error)

    if status_code == 401:
        return None, "Groq authentication failed. The API key may be invalid or expired."

    if status_code == 403:
        return None, "Groq access was denied for this API key."

    if status_code == 429:
        return None, "Groq rate limit reached. Please try again later."

    if status_code in {500, 502, 503, 504}:
        return None, "Groq is temporarily unavailable."

    return None, "Groq could not process the request."


def fallback_answer(retrieved):
    if not retrieved:
        return "I could not find relevant information in the PDF."

    lines = [
        "AI-generated answering is temporarily unavailable.",
        "Here are the most relevant sections found in the PDF:"
    ]

    for item in retrieved:
        chunk = item["chunk"]
        lines.append(
            f"\nPage {chunk['page']}:\n{chunk['content']}"
        )

    return "\n".join(lines)


def remove_oldest_document():
    while len(documents) >= MAX_DOCUMENTS:
        documents.popitem(last=False)


@app.get("/")
def home():
    return {
        "message": "RAG API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "ai_configured": bool(GROQ_API_KEY),
        "documents_in_memory": len(documents)
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

    file_content = await file.read()

    if not file_content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded PDF is empty."
        )

    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="PDF is too large. Maximum size is 20 MB."
        )

    try:
        reader = PdfReader(
            io.BytesIO(file_content)
        )

        total_pages = len(reader.pages)

        if total_pages == 0:
            raise HTTPException(
                status_code=400,
                detail="Could not read the PDF."
            )

        if total_pages > MAX_PAGES:
            raise HTTPException(
                status_code=400,
                detail=f"PDF has too many pages. Maximum allowed is {MAX_PAGES}."
            )

        chunks = []

        for page_number, page in enumerate(
            reader.pages,
            start=1
        ):
            text = clean_text(
                page.extract_text() or ""
            )

            page_chunks = split_text(text)

            for chunk_text in page_chunks:
                chunks.append(
                    {
                        "content": chunk_text,
                        "page": page_number
                    }
                )

                if len(chunks) >= MAX_CHUNKS_PER_DOCUMENT:
                    break

            if len(chunks) >= MAX_CHUNKS_PER_DOCUMENT:
                break

        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="No readable text was found in the PDF. Scanned image-only PDFs may not be supported."
            )

        vectors, document_frequency = build_index(
            chunks
        )

        for index, vector in enumerate(vectors):
            chunks[index]["vector"] = vector

        document_id = uuid.uuid4().hex

        remove_oldest_document()

        documents[document_id] = {
            "filename": file.filename,
            "pages": total_pages,
            "chunks": chunks,
            "document_frequency": document_frequency
        }

        return {
            "message": "PDF processed successfully",
            "document_id": document_id,
            "filename": file.filename,
            "pages": total_pages,
            "chunks": len(chunks)
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"PDF processing failed: {str(error)}"
        )


@app.post("/ask")
def ask_question(data: Question):
    question = data.question.strip()
    document_id = data.document_id.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty."
        )

    if len(question) > MAX_QUESTION_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Question is too long. Maximum allowed is {MAX_QUESTION_LENGTH} characters."
        )

    if not document_id:
        raise HTTPException(
            status_code=400,
            detail="Document ID is required."
        )

    document = documents.get(document_id)

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found. Please upload the PDF again."
        )

    retrieved = retrieve_chunks(
        document,
        question
    )

    context_parts = []

    for item in retrieved:
        chunk = item["chunk"]

        context_parts.append(
            f"[Page {chunk['page']}]\n{chunk['content']}"
        )

    context = "\n\n".join(context_parts)

    answer, warning = groq_answer(
        context,
        question
    )

    fallback = False

    if answer is None:
        answer = fallback_answer(
            retrieved
        )
        fallback = True

    sources = []

    for item in retrieved:
        chunk = item["chunk"]

        sources.append(
            {
                "filename": document["filename"],
                "page": chunk["page"],
                "content": chunk["content"]
            }
        )

    return {
        "answer": answer,
        "sources": sources,
        "ai_available": not fallback,
        "fallback": fallback,
        "warning": warning
    }
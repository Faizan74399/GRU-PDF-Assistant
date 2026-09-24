import { useState } from "react";
import "./App.css";

function App() {
  const [file, setFile] = useState(null);
  const [documentId, setDocumentId] = useState("");
  const [fileInfo, setFileInfo] = useState(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const uploadPDF = async () => {
    if (!file) return;

    setUploading(true);
    setError("");
    setAnswer("");
    setSources("");
    setDocumentId("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch("http://127.0.0.1:8001/upload", {
        method: "POST",
        body: formData
      });

      if (!response.ok) {
        throw new Error("Upload failed");
      }

      const data = await response.json();

      setDocumentId(data.document_id);

      setFileInfo({
        filename: data.filename,
        pages: data.pages,
        chunks: data.chunks
      });
    } catch (err) {
      setError("Unable to upload and process the PDF.");
    } finally {
      setUploading(false);
    }
  };

  const askQuestion = async (text = question) => {
    if (!text.trim() || !documentId) return;

    setQuestion(text);
    setAnswer("");
    setSources([]);
    setError("");
    setLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8001/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          question: text,
          document_id: documentId
        })
      });

      if (!response.ok) {
        throw new Error("Something went wrong");
      }

      const data = await response.json();

      setAnswer(data.answer);
      setSources(data.sources || []);
    } catch (err) {
      setError("Unable to get an answer from the RAG backend.");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      askQuestion();
    }
  };

  const clearChat = () => {
    setQuestion("");
    setAnswer("");
    setSources([]);
    setError("");
  };

  const resetPDF = () => {
    setFile(null);
    setDocumentId("");
    setFileInfo(null);
    setQuestion("");
    setAnswer("");
    setSources([]);
    setError("");
  };

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <div className="brand-icon">✦</div>

          <div>
            <h1>DocMind AI</h1>
            <p>Intelligent answers powered by RAG</p>
          </div>
        </div>

        <div className="status">
          <span></span>
          RAG Online
        </div>
      </header>

      <main className="main-content">
        <section className="hero">
          <div className="badge">AI • PDF • RAG</div>

          <h2>
            Ask any PDF.
            <br />
            <span>Get intelligent answers.</span>
          </h2>

          <p className="hero-text">
            Upload any PDF and ask questions using an AI-powered retrieval
            system that finds relevant information from your document.
          </p>
        </section>

        <section className="upload-card">
          <div className="card-top">
            <div>
              <h3>Upload your PDF</h3>
              <p>
                Upload a document and build a searchable knowledge base.
              </p>
            </div>

            {fileInfo && (
              <button className="clear-btn" onClick={resetPDF}>
                New PDF
              </button>
            )}
          </div>

          <div className="upload-area">
            <div className="upload-icon">↑</div>

            <h4>
              {file ? file.name : "Choose a PDF document"}
            </h4>

            <p>
              {file
                ? "Your PDF is ready to process."
                : "Upload any PDF to start asking questions."}
            </p>

            <label className="file-btn">
              Choose PDF
              <input
                type="file"
                accept=".pdf,application/pdf"
                onChange={(e) => {
                  setFile(e.target.files[0]);
                  setFileInfo(null);
                  setDocumentId("");
                  setAnswer("");
                  setSources([]);
                  setError("");
                }}
              />
            </label>

            {file && !fileInfo && (
              <button
                className="upload-btn"
                onClick={uploadPDF}
                disabled={uploading}
              >
                {uploading ? "Processing PDF..." : "Upload & Process →"}
              </button>
            )}
          </div>

          {fileInfo && (
            <div className="file-info">
              <div>
                <strong>✓ PDF Ready</strong>
                <p>{fileInfo.filename}</p>
              </div>

              <div className="file-stats">
                <span>{fileInfo.pages} Pages</span>
                <span>{fileInfo.chunks} Chunks</span>
              </div>
            </div>
          )}
        </section>

        {documentId && (
          <section className="chat-card">
            <div className="card-top">
              <div>
                <h3>Ask your PDF</h3>
                <p>Ask anything about the uploaded document.</p>
              </div>

              {(answer || error) && (
                <button className="clear-btn" onClick={clearChat}>
                  Clear
                </button>
              )}
            </div>

            <div className="input-wrapper">
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="What would you like to know about this PDF?"
                rows="3"
              />

              <button
                className="ask-btn"
                onClick={() => askQuestion()}
                disabled={loading || !question.trim()}
              >
                {loading ? "Thinking..." : "Ask AI →"}
              </button>
            </div>

            <div className="suggestions">
              <span>Try asking:</span>

              <button onClick={() => askQuestion("Summarize this PDF.")}>
                Summarize PDF
              </button>

              <button
                onClick={() => askQuestion("What are the main topics discussed?")}
              >
                Main topics?
              </button>

              <button
                onClick={() =>
                  askQuestion("What are the key findings of this document?")
                }
              >
                Key findings?
              </button>
            </div>

            {loading && (
              <div className="loading-box">
                <div className="loader"></div>

                <div>
                  <strong>Searching the knowledge base...</strong>
                  <p>Retrieving relevant information from the PDF</p>
                </div>
              </div>
            )}

            {error && !loading && (
              <div className="error-box">
                <strong>Something went wrong</strong>
                <p>{error}</p>
              </div>
            )}

            {answer && !loading && (
              <>
                <div className="answer-box">
                  <div className="answer-header">
                    <div className="answer-icon">✦</div>

                    <div>
                      <span>AI RESPONSE</span>
                      <h4>Answer</h4>
                    </div>
                  </div>

                  <div className="answer-content">
                    {answer}
                  </div>
                </div>

                {sources.length > 0 && (
                  <div className="sources-box">
                    <div className="sources-header">
                      <div>
                        <span>SOURCES</span>
                        <h4>Retrieved Context</h4>
                      </div>
                    </div>

                    <div className="sources-list">
                      {sources.map((source, index) => (
                        <details key={index} className="source-item">
                          <summary>
                            <div>
                              <strong>{source.filename}</strong>
                              <span>Page {source.page}</span>
                            </div>

                            <span>⌄</span>
                          </summary>

                          <div className="source-content">
                            {source.content}
                          </div>
                        </details>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </section>
        )}

        <section className="features">
          <div className="feature">
            <div className="feature-icon">↑</div>

            <div>
              <h4>Any PDF</h4>
              <p>Upload and process your own documents.</p>
            </div>
          </div>

          <div className="feature">
            <div className="feature-icon">⌕</div>

            <div>
              <h4>Semantic Search</h4>
              <p>Finds relevant information from your document.</p>
            </div>
          </div>

          <div className="feature">
            <div className="feature-icon">◈</div>

            <div>
              <h4>RAG Powered</h4>
              <p>Answers with retrieved context and sources.</p>
            </div>
          </div>
        </section>
      </main>

      <footer>
        <span>DocMind AI</span>
        <span>Built with React + FastAPI + LangChain + RAG</span>
      </footer>
    </div>
  );
}

export default App;
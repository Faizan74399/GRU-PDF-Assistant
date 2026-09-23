import { useState } from "react";
import "./App.css";

function App() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const askQuestion = async (text = question) => {
    if (!text.trim()) return;

    setQuestion(text);
    setAnswer("");
    setError("");
    setLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8001/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          question: text
        })
      });

      if (!response.ok) {
        throw new Error("Something went wrong");
      }

      const data = await response.json();
      setAnswer(data.answer);
    } catch (err) {
      setError("Unable to connect with the RAG backend.");
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
    setError("");
  };

  return (
    <div className="app">
      <div className="background-glow glow-one"></div>
      <div className="background-glow glow-two"></div>

      <header className="header">
        <div className="brand">
          <div className="brand-icon">✦</div>

          <div>
            <h1>GRU PDF Assistant</h1>
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
            Ask your PDF.
            <br />
            <span>Get intelligent answers.</span>
          </h2>

          <p className="hero-text">
            Ask anything about the GRU research paper and get answers
            directly from the information stored in your knowledge base.
          </p>
        </section>

        <section className="chat-card">
          <div className="card-top">
            <div>
              <h3>Ask the GRU Assistant</h3>
              <p>Ask a question related to the uploaded PDF</p>
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
              placeholder="What would you like to know about GRU?"
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

            <button onClick={() => askQuestion("What is GRU?")}>
              What is GRU?
            </button>

            <button onClick={() => askQuestion("How does GRU work?")}>
              How does GRU work?
            </button>

            <button
              onClick={() =>
                askQuestion("What are the main components of GRU?")
              }
            >
              Main components?
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
              <strong>Connection Error</strong>
              <p>{error}</p>
            </div>
          )}

          {answer && !loading && (
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
          )}
        </section>

        <section className="features">
          <div className="feature">
            <div className="feature-icon">⌕</div>

            <div>
              <h4>Semantic Search</h4>
              <p>Finds relevant information from your PDF.</p>
            </div>
          </div>

          <div className="feature">
            <div className="feature-icon">◈</div>

            <div>
              <h4>RAG Powered</h4>
              <p>Uses retrieved context to generate answers.</p>
            </div>
          </div>

          <div className="feature">
            <div className="feature-icon">✓</div>

            <div>
              <h4>PDF Based</h4>
              <p>Answers are generated from your knowledge base.</p>
            </div>
          </div>
        </section>
      </main>

      <footer>
        <span>GRU PDF Assistant</span>
        <span>Built with React + FastAPI + LangChain + RAG</span>
      </footer>
    </div>
  );
}

export default App;
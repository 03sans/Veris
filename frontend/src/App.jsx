import { useState } from "react";

const API =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export default function App() {
  const [file, setFile] = useState(null);
  const [text, setText] = useState("");
  const [meta, setMeta] = useState(null); // { filename, filetype, pages? }
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Summarizer state
  const [jurisdiction, setJurisdiction] = useState("General");
  const [sumLoading, setSumLoading] = useState(false);
  const [summary, setSummary] = useState("");
  const [clauses, setClauses] = useState([]); // [{type, snippet}]
  const [sumError, setSumError] = useState("");

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
    setText("");
    setMeta(null);
    setError("");
    setSummary("");
    setClauses([]);
    setSumError("");
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Please select a file first.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setLoading(true);
    setError("");
    setSummary("");
    setClauses([]);
    setSumError("");

    try {
      const res = await fetch(`${API}/api/upload`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Upload failed (${res.status})`);
      }
      const data = await res.json();
      setMeta({
        filename: data.filename,
        filetype: data.filetype,
        pages: data.pages,
      });
      setText(data.text || "");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSummarize = async () => {
    if (!text.trim()) {
      setSumError("No text available. Please upload a document first.");
      return;
    }
    setSumLoading(true);
    setSumError("");
    setSummary("");
    setClauses([]);

    try {
      const res = await fetch(`${API}/api/summarize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, jurisdiction }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Summarize failed (${res.status})`);
      }
      const data = await res.json();
      setSummary(data.summary || "");
      setClauses(Array.isArray(data.clauses) ? data.clauses : []);
    } catch (err) {
      setSumError(err.message);
    } finally {
      setSumLoading(false);
    }
  };

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: 900, margin: "0 auto" }}>
      <h1>Veris — Your AI Legal Assistant</h1>
      <p>Upload a PDF or DOCX, extract text, then summarize in plain English.</p>

      {/* Upload controls */}
      <div style={{ marginTop: "1rem" }}>
        <input type="file" accept=".pdf,.docx" onChange={handleFileChange} />
        <button
          onClick={handleUpload}
          style={{ marginLeft: "0.5rem", padding: "0.4rem 1rem", cursor: "pointer" }}
        >
          Upload
        </button>
      </div>

      {loading && <p style={{ color: "gray" }}>Extracting text…</p>}
      {error && <p style={{ color: "crimson" }}>{error}</p>}

      {meta && (
        <div style={{ marginTop: "1rem", fontSize: "0.95rem" }}>
          <strong>File:</strong> {meta.filename} · <strong>Type:</strong>{" "}
          {meta.filetype?.toUpperCase()}
          {meta.filetype === "pdf" && meta.pages != null && (
            <>
              {" "}· <strong>Pages:</strong> {meta.pages}
            </>
          )}
        </div>
      )}

      {/* Extracted text */}
      {text?.trim().length > 0 && (
  <div
    style={{
      marginTop: "1rem",
      padding: "1rem",
      border: "1px solid #ccc",
      borderRadius: 6,
      maxHeight: 260,
      overflowY: "auto",
      whiteSpace: "pre-wrap",
      background: "#fafafa",
    }}
  >
    {text}
  </div>
)}

      {/* Summarize controls */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "1rem" }}>
        <label htmlFor="jurisdiction"><strong>Jurisdiction:</strong></label>
        <select
          id="jurisdiction"
          value={jurisdiction}
          onChange={(e) => setJurisdiction(e.target.value)}
        >
          <option>General</option>
          <option>Nepal</option>
          <option>United States</option>
          <option>United Kingdom</option>
          <option>India</option>
          <option>EU</option>
        </select>

        <button
          onClick={handleSummarize}
          disabled={sumLoading || !text}
          style={{ padding: "0.45rem 1rem", cursor: "pointer" }}
        >
          {sumLoading ? "Summarizing…" : "Summarize"}
        </button>
      </div>

      {sumError && <p style={{ color: "crimson" }}>{sumError}</p>}

      {/* Summary output */}
      {(summary || clauses.length > 0) && (
        <div style={{ marginTop: "1rem" }}>
          {summary && (
            <div style={{ padding: "1rem", border: "1px solid #ddd", borderRadius: 6 }}>
              <h3 style={{ marginTop: 0 }}>Summary</h3>
              <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{summary}</p>
            </div>
          )}

          {clauses.length > 0 && (
            <div style={{ marginTop: "1rem", padding: "1rem", border: "1px solid #ddd", borderRadius: 6 }}>
              <h3 style={{ marginTop: 0 }}>Key Clauses</h3>
              <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
                {clauses.map((c, i) => (
                  <li key={i} style={{ marginBottom: "0.5rem" }}>
                    <strong>{c.type}</strong>: {c.snippet}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Disclaimer */}
      <p style={{ marginTop: "1.25rem", fontSize: "0.9rem", color: "#555" }}>
        ⚠️ Veris provides AI‑generated explanations and is not a substitute for legal advice.
      </p>
    </main>
  );
}
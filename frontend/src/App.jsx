import { useState } from "react";

export default function App() {
  const [file, setFile] = useState(null);
  const [text, setText] = useState("");
  const [meta, setMeta] = useState(null); // { filename, filetype, pages? }
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
    setText("");
    setMeta(null);
    setError("");
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
    try {
      const res = await fetch("http://127.0.0.1:8000/api/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Upload failed");
      }

      const data = await res.json();
      setMeta({
        filename: data.filename,
        filetype: data.filetype,
        pages: data.pages, // present for PDFs
      });
      setText(data.text);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
      <h1>Veris — AI Legal Assistant</h1>
      <p>Upload a PDF or DOCX to extract text.</p>

      <div style={{ marginTop: "1rem" }}>
        <input type="file" accept=".pdf,.docx" onChange={handleFileChange} />
        <button
          onClick={handleUpload}
          style={{
            marginLeft: "0.5rem",
            padding: "0.4rem 1rem",
            cursor: "pointer",
          }}
        >
          Upload
        </button>
      </div>

      {loading && <p style={{ color: "gray" }}>Extracting text…</p>}
      {error && <p style={{ color: "crimson" }}>{error}</p>}

      {meta && (
        <div style={{ marginTop: "1rem", fontSize: "0.95rem" }}>
          <strong>File:</strong> {meta.filename} · <strong>Type:</strong>{" "}
          {meta.filetype.toUpperCase()}
          {meta.filetype === "pdf" && meta.pages != null && (
            <>
              {" "}&middot; <strong>Pages:</strong> {meta.pages}
            </>
          )}
        </div>
      )}

      {text && (
        <div
          style={{
            marginTop: "1rem",
            padding: "1rem",
            border: "1px solid #ccc",
            borderRadius: "6px",
            maxHeight: "300px",
            overflowY: "auto",
            whiteSpace: "pre-wrap",
          }}
        >
          {text}
        </div>
      )}
    </main>
  );
}
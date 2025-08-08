// frontend/src/App.jsx
import { useEffect, useState } from "react";

export default function App() {
  const [apiMessage, setApiMessage] = useState("Checking backend…");
  const [error, setError] = useState("");

  useEffect(() => {
    async function pingBackend() {
      try {
        const res = await fetch("http://127.0.0.1:8000/");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setApiMessage(data.message || "Backend responded.");
      } catch (err) {
        setError(`Could not reach backend: ${err.message}`);
      }
    }
    pingBackend();
  }, []);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
      <h1>Veris — AI Legal Assistant</h1>
      <p style={{ marginTop: "0.5rem" }}>
        Frontend ↔ Backend wiring demo.
      </p>

      <section style={{ marginTop: "2rem" }}>
        <h2>Backend status</h2>
        {!error ? <p>{apiMessage}</p> : <p style={{color: "crimson"}}>{error}</p>}
      </section>
    </main>
  );
}
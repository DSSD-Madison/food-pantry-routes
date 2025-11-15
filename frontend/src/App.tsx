import { useState } from "react";
import "./App.css";

type TableResponse = {
  filename: string;
  columns: string[];
  rows: Record<string, any>[];
};

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"; // FastAPI URL

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [table, setTable] = useState<TableResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] || null;
    setFile(f);
    setTable(null);
    setError(null);
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Please choose a CSV or Excel file first.");
      return;
    }

    setLoading(true);
    setError(null);
    setTable(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(`${API_BASE_URL}/upload-spreadsheet`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(
          data?.detail || `Upload failed with status ${res.status}`
        );
      }

      const data = (await res.json()) as TableResponse;
      setTable(data);
    } catch (err: any) {
      setError(err.message || "Something went wrong while uploading.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <h1>Spreadsheet Uploader</h1>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h2>Upload a spreadsheet</h2>
        <input
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={handleFileChange}
        />
        <button
          onClick={handleUpload}
          disabled={!file || loading}
          style={{ marginLeft: "0.5rem" }}
        >
          {loading ? "Uploading…" : "Upload & Process"}
        </button>

        {file && (
          <p style={{ marginTop: "0.5rem" }}>
            Selected file: <strong>{file.name}</strong>
          </p>
        )}

        {error && <p style={{ color: "red", marginTop: "0.5rem" }}>{error}</p>}
      </div>

      {table && (
        <div
          className="card"
          style={{ marginTop: "1rem", maxWidth: "100%", overflowX: "auto" }}
        >
          <h2>Parsed Table ({table.filename})</h2>
          <table>
            <thead>
              <tr>
                {table.columns.map((col) => (
                  <th key={col}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, idx) => (
                <tr key={idx}>
                  {table.columns.map((col) => (
                    <td key={col}>{row[col]?.toString?.() ?? ""}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="read-the-docs">
        Backend: <code>{API_BASE_URL}</code>
      </p>
    </>
  );
}

export default App;

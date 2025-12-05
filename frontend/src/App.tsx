import { useState } from "react";
import "./App.css";
import DragDropDemo from "./DragDropDemo";

type TableResponse = {
  filename: string;
  columns: string[];
  groups: Record<string, any>[][];
};

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [numGroups, setNumGroups] = useState<number>(2);
  const [table, setTable] = useState<TableResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ------------------------------
  // Handle file selection
  // ------------------------------
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] || null;
    setFile(f);
    setError(null);
  };

  // ------------------------------
  // Handle spreadsheet upload
  // ------------------------------
  const handleUpload = async () => {
    if (!file) {
      setError("Please choose a CSV or Excel file first.");
      return;
    }

    if (!numGroups || numGroups <= 0) {
      setError("Please enter a valid number of groups.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("number_of_groups", numGroups.toString());

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

      // 🔥 Switch UI to DragDropDemo after upload
      setTable(data);
    } catch (err: any) {
      setError(err.message || "Something went wrong while uploading.");
    } finally {
      setLoading(false);
    }
  };

  // ----------------------------------------------------
  // If table exists → Show DragDropDemo instead of upload UI
  // ----------------------------------------------------
  if (table) {
    return (
      <DragDropDemo
        filename={table.filename}
        columns={table.columns}
        groups={table.groups}
      />
    );
  }

  // ----------------------------------------------------
  // Upload UI
  // ----------------------------------------------------
  return (
    <div>
      <h1>Spreadsheet Uploader</h1>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h2>Upload a spreadsheet</h2>

        <input
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={handleFileChange}
        />

        <div style={{ marginTop: "1rem" }}>
          <label>Number of Groups:</label>
          <input
            type="number"
            value={numGroups}
            onChange={(e) => setNumGroups(Number(e.target.value))}
            style={{ marginLeft: "0.5rem", width: "80px" }}
            min={1}
          />
        </div>

        <button
          onClick={handleUpload}
          disabled={!file || loading}
          style={{ marginLeft: "0.5rem", marginTop: "1rem" }}
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

      <p className="read-the-docs">
        Backend: <code>{API_BASE_URL}</code>
      </p>
    </div>
  );
}

export default App;

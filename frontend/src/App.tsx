import { useState, useEffect } from "react";
import "./App.css";
import DragDropDemo from "./DragDropDemo";

type TableResponse = {
  filename: string;
  columns: string[];
  groups: Record<string, any>[][];
};

type SavedGrouping = {
  id: string;
  filename: string;
  number_of_groups: number;
  columns: string[];
  groups: Record<string, any>[][];
  created_at: string;
};

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [numGroups, setNumGroups] = useState<number>(2);
  const [table, setTable] = useState<TableResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedGroupings, setSavedGroupings] = useState<SavedGrouping[]>([]);
  const [showSaved, setShowSaved] = useState(false);

  // ------------------------------
  // Fetch saved groupings on mount
  // ------------------------------
  useEffect(() => {
    fetchSavedGroupings();
  }, []);

  const fetchSavedGroupings = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/groupings`);
      if (res.ok) {
        const data = await res.json();
        setSavedGroupings(data.groupings || []);
      }
    } catch (err) {
      console.error("Failed to fetch saved groupings:", err);
    }
  };

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

  // ------------------------------
  // Load saved grouping
  // ------------------------------
  const handleLoadGrouping = (grouping: SavedGrouping) => {
    setTable({
      filename: grouping.filename,
      columns: grouping.columns,
      groups: grouping.groups,
    });
    setShowSaved(false);
  };

  // ------------------------------
  // Delete saved grouping
  // ------------------------------
  const handleDeleteGrouping = async (id: string) => {
    if (!confirm("Are you sure you want to delete this grouping?")) return;

    try {
      const res = await fetch(`${API_BASE_URL}/groupings/${id}`, {
        method: "DELETE",
      });

      if (res.ok) {
        setSavedGroupings((prev) => prev.filter((g) => g.id !== id));
        alert("Grouping deleted successfully");
      } else {
        throw new Error("Failed to delete");
      }
    } catch (err: any) {
      alert(`Error deleting grouping: ${err.message}`);
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

      {/* Saved Groupings Section */}
      <div className="card" style={{ marginTop: "2rem" }}>
        <h2>Previously Saved Groupings</h2>
        <button
          onClick={() => setShowSaved(!showSaved)}
          style={{ marginBottom: "1rem" }}
        >
          {showSaved ? "Hide" : "Show"} Saved Groupings ({savedGroupings.length})
        </button>

        {showSaved && (
          <div style={{ maxHeight: "400px", overflowY: "auto" }}>
            {savedGroupings.length === 0 ? (
              <p>No saved groupings yet.</p>
            ) : (
              <ul style={{ listStyle: "none", padding: 0 }}>
                {savedGroupings.map((grouping) => (
                  <li
                    key={grouping.id}
                    style={{
                      border: "1px solid #ccc",
                      padding: "10px",
                      marginBottom: "10px",
                      borderRadius: "5px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div>
                        <strong>{grouping.filename}</strong>
                        <div style={{ fontSize: "0.9em", color: "#666" }}>
                          {grouping.number_of_groups} groups • Created: {new Date(grouping.created_at).toLocaleString()}
                        </div>
                      </div>
                      <div style={{ display: "flex", gap: "10px" }}>
                        <button onClick={() => handleLoadGrouping(grouping)}>
                          Load
                        </button>
                        <button
                          onClick={() => handleDeleteGrouping(grouping.id)}
                          style={{ background: "#dc3545" }}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <p className="read-the-docs">
        Backend: <code>{API_BASE_URL}</code>
      </p>
    </div>
  );
}

export default App;

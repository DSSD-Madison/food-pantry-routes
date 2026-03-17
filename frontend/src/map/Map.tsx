import { useState } from "react";
import "./Map.css";

function Map() {
  const [showMap] = useState(true);

  return (
    <div
      style={{
        width: "100%",
        margin: 0,
        padding: 0,
        overflowX: "hidden",
      }}
    >
      <h1 style={{ padding: "1rem", margin: 0 }}>Map Page</h1>
      <p style={{ padding: "0 1rem", marginTop: "0.5rem" }}>
        This is an interactive map.
      </p>

      <a href="/">
        <button style={{ margin: "1rem" }}>Back to Home</button>
      </a>

      {showMap && (
        <div
          style={{
            width: "100%",
            height: "500px",
            overflow: "hidden",
          }}
        >
          <iframe
            title="map"
            width="100%"
            height="100%"
            style={{ border: 0, display: "block" }}
            loading="lazy"
            allowFullScreen
            src="https://www.google.com/maps?q=Madison,WI&output=embed"
          />
        </div>
      )}
    </div>
  );
}

export default Map;
import { useEffect, useState } from "react";
import axios from "axios";

export default function MyRoutesPage() {
  const [routes, setRoutes] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchRoutes();
  }, []);

  async function fetchRoutes() {
    try {
      const token = localStorage.getItem("token");
      const res = await axios.get("http://localhost:8000/routes", {
        headers: { Authorization: `Bearer ${token}` },
      });
      setRoutes(res.data);
    } catch {
      setError("Could not load routes.");
    }
  }

  async function deleteRoute(id) {
    try {
      const token = localStorage.getItem("token");
      await axios.delete(`http://localhost:8000/routes/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setRoutes((prev) => prev.filter((r) => r.id !== id));
    } catch {
      setError("Could not delete route.");
    }
  }

  return (
    <div className="page-container" style={{ maxWidth: "600px" }}>
      <h2>My Routes</h2>
      {error && <p style={{ color: "red" }}>{error}</p>}
      {routes.length === 0 && !error && <p style={{ color: "#666" }}>No saved routes yet.</p>}
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {routes.map((route) => (
          <div
            key={route.id}
            style={{
              border: "1px solid #ddd",
              borderRadius: "8px",
              padding: "14px 16px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
            }}
          >
            <div>
              <strong>{route.name}</strong>
              {route.description && <p style={{ margin: "4px 0 0", color: "#555", fontSize: "14px" }}>{route.description}</p>}
              <p style={{ margin: "6px 0 0", fontSize: "12px", color: "#999" }}>
                {route.start_lat.toFixed(4)}, {route.start_lng.toFixed(4)} → {route.end_lat.toFixed(4)}, {route.end_lng.toFixed(4)}
              </p>
              <p style={{ margin: "2px 0 0", fontSize: "12px", color: "#bbb" }}>
                {new Date(route.created_at).toLocaleDateString()}
              </p>
            </div>
            <button
              onClick={() => deleteRoute(route.id)}
              style={{ color: "red", background: "none", border: "none", cursor: "pointer", fontSize: "18px", lineHeight: 1 }}
              title="Delete"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

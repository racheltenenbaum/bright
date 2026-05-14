import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

const MAP_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

function staticMapUrl(route) {
  const start = `${route.start_lat},${route.start_lng}`;
  const end = `${route.end_lat},${route.end_lng}`;
  return (
    `https://maps.googleapis.com/maps/api/staticmap` +
    `?size=100x100&scale=2` +
    `&markers=color:0x7bc67e%7C${start}` +
    `&markers=color:0x1a6b1a%7C${end}` +
    `&path=color:0x3d7a3d80%7Cweight:3%7C${start}%7C${end}` +
    `&key=${MAP_KEY}`
  );
}

async function reverseGeocode(lat, lng) {
  try {
    const res = await fetch(
      `https://maps.googleapis.com/maps/api/geocode/json?latlng=${lat},${lng}&key=${MAP_KEY}`
    );
    const data = await res.json();
    return data.results[0]?.formatted_address?.split(",")[0].trim() || null;
  } catch {
    return null;
  }
}

export default function MyRoutesPage() {
  const navigate = useNavigate();
  const [routes, setRoutes] = useState([]);
  const [resolvedAddresses, setResolvedAddresses] = useState({});
  const [error, setError] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null); // { id, name }

  useEffect(() => {
    fetchRoutes();
  }, []);

  useEffect(() => {
    const missing = routes.filter((r) => !r.start_address || !r.end_address);
    if (!missing.length) return;
    missing.forEach(async (route) => {
      const [start, end] = await Promise.all([
        route.start_address ? route.start_address : reverseGeocode(route.start_lat, route.start_lng),
        route.end_address ? route.end_address : reverseGeocode(route.end_lat, route.end_lng),
      ]);
      setResolvedAddresses((prev) => ({ ...prev, [route.id]: { start, end } }));
    });
  }, [routes]);

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

  async function confirmDelete() {
    try {
      const token = localStorage.getItem("token");
      await axios.delete(`http://localhost:8000/routes/${pendingDelete.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setRoutes((prev) => prev.filter((r) => r.id !== pendingDelete.id));
      setPendingDelete(null);
    } catch {
      setError("Could not delete route.");
      setPendingDelete(null);
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
            onClick={() => navigate("/plan", { state: { route: {
              ...route,
              start_address: route.start_address || resolvedAddresses[route.id]?.start || "",
              end_address: route.end_address || resolvedAddresses[route.id]?.end || "",
            } } })}
            style={{
              border: "1px solid #ddd",
              borderRadius: "8px",
              overflow: "hidden",
              display: "flex",
              alignItems: "stretch",
              cursor: "pointer",
            }}
          >
            <div style={{ width: "100px", flexShrink: 0, alignSelf: "stretch" }}>
              <img
                src={staticMapUrl(route)}
                alt="route map"
                style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
              />
            </div>
            <div style={{ padding: "10px 14px", display: "flex", justifyContent: "space-between", alignItems: "flex-start", flex: 1 }}>
              <div>
                <strong>{route.name}</strong>
                {route.description && <p style={{ margin: "4px 0 0", color: "#555", fontSize: "14px" }}>{route.description}</p>}
                <p style={{ margin: "6px 0 0", fontSize: "12px", color: "#999" }}>
                  {route.start_address || resolvedAddresses[route.id]?.start || `${route.start_lat.toFixed(4)}, ${route.start_lng.toFixed(4)}`}
                  {" → "}
                  {route.end_address || resolvedAddresses[route.id]?.end || `${route.end_lat.toFixed(4)}, ${route.end_lng.toFixed(4)}`}
                </p>
                <p style={{ margin: "2px 0 0", fontSize: "12px", color: "#bbb" }}>
                  {new Date(route.created_at).toLocaleDateString()}
                </p>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); setPendingDelete({ id: route.id, name: route.name }); }}
                style={{ color: "#aaa", background: "none", border: "none", cursor: "pointer", fontSize: "18px", lineHeight: 1 }}
                title="Delete"
              >
                ×
              </button>
            </div>
          </div>
        ))}
      </div>

      {pendingDelete && (
        <div style={{
          position: "fixed", inset: 0,
          background: "rgba(0,0,0,0.35)",
          display: "flex", alignItems: "center", justifyContent: "center",
          zIndex: 1000,
        }}>
          <div style={{
            background: "#fff",
            borderRadius: "12px",
            padding: "28px 32px",
            maxWidth: "360px",
            width: "90%",
            boxShadow: "0 8px 32px rgba(0,0,0,0.18)",
            display: "flex",
            flexDirection: "column",
            gap: "12px",
          }}>
            <h3 style={{ margin: 0 }}>Delete route?</h3>
            <p style={{ margin: 0, color: "#555" }}>
              <strong>{pendingDelete.name}</strong> will be permanently deleted.
            </p>
            <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end", marginTop: "4px" }}>
              <button onClick={() => setPendingDelete(null)}>Cancel</button>
              <button
                onClick={confirmDelete}
                style={{ background: "#c0392b", color: "#fff", border: "none" }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faSun, faArrowRight, faTrash } from "@fortawesome/free-solid-svg-icons";

const MAP_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

function distanceKm(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * (Math.PI / 180);
  const dLng = (lng2 - lng1) * (Math.PI / 180);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * (Math.PI / 180)) * Math.cos(lat2 * (Math.PI / 180)) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

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
      <h2>My Routes <FontAwesomeIcon icon={faSun} style={{ color: "#FFD600", fontSize: "0.85em" }} /></h2>
      {error && <p style={{ color: "#C0392B", fontSize: "0.88em" }}>{error}</p>}
      {routes.length === 0 && !error && (
        <p style={{ color: "#A87500", fontSize: "0.92em" }}>No saved routes yet. Plan one!</p>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
        {routes.map((route) => (
          <div
            key={route.id}
            onClick={() => navigate("/plan", { state: { route: {
              ...route,
              start_address: route.start_address || resolvedAddresses[route.id]?.start || "",
              end_address: route.end_address || resolvedAddresses[route.id]?.end || "",
            } } })}
            style={{
              border: "2.5px solid #ffffff",
              borderRadius: "16px",
              overflow: "hidden",
              display: "flex",
              alignItems: "stretch",
              cursor: "pointer",
              background: "#FFFDF5",
              boxShadow: "4px 4px 0 #E8C000",
              transition: "transform 0.1s, box-shadow 0.1s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = "translate(-2px, -2px)";
              e.currentTarget.style.boxShadow = "6px 6px 0 #E8C000";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = "translate(0, 0)";
              e.currentTarget.style.boxShadow = "4px 4px 0 #E8C000";
            }}
          >
            <div style={{ width: "100px", flexShrink: 0, alignSelf: "stretch" }}>
              <img
                src={staticMapUrl(route)}
                alt="route map"
                style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
              />
            </div>
            <div style={{ padding: "12px 14px", display: "flex", justifyContent: "space-between", alignItems: "flex-start", flex: 1 }}>
              <div>
                <strong style={{ color: "#3D2C00", fontSize: "0.97em" }}>{route.name}</strong>
                {route.description && (
                  <p style={{ margin: "3px 0 0", color: "#7B5800", fontSize: "0.82em" }}>{route.description}</p>
                )}
                <p style={{ margin: "6px 0 0", fontSize: "0.78em", color: "#A87500" }}>
                  {route.start_address || resolvedAddresses[route.id]?.start || `${route.start_lat.toFixed(4)}, ${route.start_lng.toFixed(4)}`}
                  {" "}<FontAwesomeIcon icon={faArrowRight} style={{ fontSize: "0.75em", color: "#C8A84B" }} />{" "}
                  {route.end_address || resolvedAddresses[route.id]?.end || `${route.end_lat.toFixed(4)}, ${route.end_lng.toFixed(4)}`}
                </p>
                <p style={{ margin: "3px 0 0", fontSize: "0.76em", color: "#C8A84B", fontWeight: 500 }}>
                  {(() => {
                    const km = distanceKm(route.start_lat, route.start_lng, route.end_lat, route.end_lng);
                    const mins = Math.round(km / 5 * 60);
                    return `Approx. ${km.toFixed(1)} km · ${mins} min walk`;
                  })()}
                </p>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); setPendingDelete({ id: route.id, name: route.name }); }}
                style={{
                  color: "#C8A84B", background: "none", border: "none",
                  cursor: "pointer", fontSize: "20px", lineHeight: 1,
                  padding: "2px 4px", boxShadow: "none",
                  transition: "color 0.15s",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.color = "#C0392B"; }}
                onMouseLeave={(e) => { e.currentTarget.style.color = "#C8A84B"; }}
                title="Delete"
              >
                <FontAwesomeIcon icon={faTrash} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {pendingDelete && (
        <div style={{
          position: "fixed", inset: 0,
          background: "rgba(61, 44, 0, 0.25)",
          backdropFilter: "blur(2px)",
          display: "flex", alignItems: "center", justifyContent: "center",
          zIndex: 1000,
        }}>
          <div style={{
            background: "#FFFDF5",
            border: "2.5px solid #ffffff",
            borderRadius: "24px",
            padding: "32px",
            maxWidth: "340px",
            width: "90%",
            boxShadow: "6px 6px 0 #E8C000",
            display: "flex",
            flexDirection: "column",
            gap: "12px",
          }}>
            <h3 style={{ margin: 0, fontSize: "1.1em" }}>Delete route?</h3>
            <p style={{ margin: 0, color: "#7B5800", fontSize: "0.9em" }}>
              <strong>{pendingDelete.name}</strong> will be permanently deleted.
            </p>
            <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end", marginTop: "4px" }}>
              <button className="btn-outline" onClick={() => setPendingDelete(null)}>Cancel</button>
              <button className="btn-danger" onClick={confirmDelete}>Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

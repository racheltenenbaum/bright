import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "../api";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faArrowRight, faSun, faCloudSun } from "@fortawesome/free-solid-svg-icons";

const MAP_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

const COLORS = {
  sun:   { startPin: "0xFFD600", endPin: "0xf5ae0a", path: "0xFFD60080" },
  shade: { startPin: "0x7AB3CF", endPin: "0x4A7090", path: "0x4A709080" },
};

function staticMapUrl(route) {
  const start = `${route.start_lat},${route.start_lng}`;
  const end = `${route.end_lat},${route.end_lng}`;
  const c = route.preference === "shade" ? COLORS.shade : COLORS.sun;
  let pathParam = `&path=color:${c.path}%7Cweight:4%7C${start}%7C${end}`;
  if (route.route_path) {
    try {
      const coords = JSON.parse(route.route_path);
      const points = coords.map(([lat, lng]) => `${lat},${lng}`).join("%7C");
      pathParam = `&path=color:${c.path}%7Cweight:4%7C${points}`;
    } catch { /* fall back to straight line */ }
  }
  return (
    `https://maps.googleapis.com/maps/api/staticmap` +
    `?size=600x300&scale=2` +
    `&markers=size:mid%7Ccolor:${c.startPin}%7C${start}` +
    `&markers=size:mid%7Ccolor:${c.endPin}%7C${end}` +
    pathParam +
    `&key=${MAP_KEY}`
  );
}

export default function SharedRoutePage() {
  const { token } = useParams();
  const [route, setRoute] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.get(`/share/${token}`)
      .then((res) => setRoute(res.data))
      .catch(() => setError("This route link is invalid or has been removed."));
  }, [token]);

  if (error) {
    return (
      <div className="page-container" style={{ display: "flex", justifyContent: "center", alignItems: "center" }}>
        <div className="auth-card" style={{ textAlign: "center" }}>
          <img src="/logo.gif" alt="bright" style={{ height: "56px", marginBottom: "16px" }} />
          <p style={{ color: "#C0392B", fontWeight: 700 }}>{error}</p>
          <Link to="/"><button style={{ marginTop: "8px" }}>Go to bright</button></Link>
        </div>
      </div>
    );
  }

  if (!route) {
    return (
      <div className="page-container" style={{ display: "flex", justifyContent: "center", alignItems: "center" }}>
        <p style={{ color: "var(--color-subtext)" }}>Loading...</p>
      </div>
    );
  }

  return (
    <div className="page-container" style={{ maxWidth: "560px", margin: "0 auto" }}>
      <div style={{ textAlign: "center", marginBottom: "24px" }}>
        <img src="/logo.gif" alt="bright" style={{ height: "52px" }} />
      </div>

      <div style={{
        background: "var(--color-surface)",
        border: "2.5px solid #ffffff",
        borderRadius: "20px",
        overflow: "hidden",
        boxShadow: "4px 4px 0 var(--color-accent-dim)",
      }}>
        <img
          src={staticMapUrl(route)}
          alt="route map"
          style={{ width: "100%", display: "block", maxHeight: "220px", objectFit: "cover" }}
        />
        <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <h2 style={{ margin: 0, fontSize: "1.3em" }}>{route.name}</h2>
            {route.preference && (
              <span style={{
                fontSize: "0.78em", fontWeight: 700, padding: "3px 10px",
                borderRadius: "999px",
                background: route.preference === "shade" ? "#7AB3CF" : "#FFD600",
                color: route.preference === "shade" ? "#ffffff" : "#3D2C00",
              }}>
                <FontAwesomeIcon icon={route.preference === "shade" ? faCloudSun : faSun} style={{ marginRight: "4px" }} />
                {route.preference === "shade" ? "Shade" : "Sun"}
              </span>
            )}
          </div>

          {route.description && (
            <p style={{ margin: 0, color: "var(--color-subtext)", fontSize: "0.88em" }}>{route.description}</p>
          )}

          {(route.start_address || route.end_address) && (
            <p style={{ margin: 0, fontSize: "0.82em", color: "var(--color-subtext)", fontWeight: 500 }}>
              {route.start_address || `${route.start_lat.toFixed(4)}, ${route.start_lng.toFixed(4)}`}
              {" "}<FontAwesomeIcon icon={faArrowRight} style={{ fontSize: "0.75em" }} />{" "}
              {route.end_address || `${route.end_lat.toFixed(4)}, ${route.end_lng.toFixed(4)}`}
            </p>
          )}
        </div>
      </div>

      <div style={{
        marginTop: "28px", textAlign: "center",
        display: "flex", flexDirection: "column", alignItems: "center", gap: "10px",
      }}>
        <p style={{ margin: 0, fontWeight: 700, fontSize: "1em", color: "var(--color-text)" }}>
          Plan sunny (or shady) walks with bright
        </p>
        <p style={{ margin: 0, fontSize: "0.85em", color: "var(--color-subtext)" }}>
          Find the sunniest or shadiest route between any two points.
        </p>
        <Link to="/register">
          <button style={{ marginTop: "4px", fontSize: "0.95em", padding: "0.55em 1.8em" }}>
            Sign up free
          </button>
        </Link>
        <p style={{ margin: 0, fontSize: "0.82em", color: "var(--color-subtext)" }}>
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  );
}

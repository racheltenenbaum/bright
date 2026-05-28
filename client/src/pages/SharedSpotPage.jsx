import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "../api";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faMapPin, faLocationDot } from "@fortawesome/free-solid-svg-icons";
import { spotIcon } from "./MySpotsPage";

const MAP_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

function staticMapUrl(lat, lng) {
  return (
    `https://maps.googleapis.com/maps/api/staticmap` +
    `?center=${lat},${lng}&zoom=15&size=600x300&scale=2` +
    `&markers=color:0xFFD600%7Csize:mid%7C${lat},${lng}` +
    `&key=${MAP_KEY}`
  );
}

function googleMapsUrl(spot) {
  if (spot.place_id) return `https://www.google.com/maps/place/?q=place_id:${spot.place_id}`;
  return `https://maps.google.com/?q=${spot.lat},${spot.lng}`;
}

export default function SharedSpotPage() {
  const { token } = useParams();
  const [spot, setSpot] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.get(`/share/spot/${token}`)
      .then((res) => setSpot(res.data))
      .catch(() => setError("This spot link is invalid or has been removed."));
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

  if (!spot) {
    return (
      <div className="page-container" style={{ display: "flex", justifyContent: "center", alignItems: "center" }}>
        <p style={{ color: "var(--color-subtext)" }}>Loading...</p>
      </div>
    );
  }

  return (
    <div className="page-container" style={{ maxWidth: "560px", margin: "0 auto" }}>
      <div style={{ textAlign: "center", marginBottom: "24px" }}>
        <img src="/logo.gif"      className="logo-light" alt="bright" style={{ height: "52px" }} />
        <img src="/logo-dark.gif" className="logo-dark"  alt="bright" style={{ height: "52px" }} />
      </div>

      <div style={{
        background: "var(--color-surface)",
        border: "2.5px solid var(--color-card-border)",
        borderRadius: "20px",
        overflow: "hidden",
        boxShadow: "4px 4px 0 var(--color-accent-dim)",
      }}>
        <img
          src={staticMapUrl(spot.lat, spot.lng)}
          alt={spot.name}
          style={{ width: "100%", display: "block", maxHeight: "220px", objectFit: "cover" }}
        />
        <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <span style={{
              width: "38px", height: "38px", borderRadius: "50%", flexShrink: 0,
              background: "var(--color-accent)", display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <FontAwesomeIcon icon={spotIcon(spot.icon)} style={{ color: "#fff", fontSize: "1em" }} />
            </span>
            <h2 style={{ margin: 0, fontSize: "1.3em" }}>{spot.name}</h2>
          </div>

          <p style={{ margin: 0, fontSize: "0.85em", color: "var(--color-subtext)", fontWeight: 500 }}>
            <FontAwesomeIcon icon={faMapPin} style={{ marginRight: "5px" }} />
            {spot.address}
          </p>

          {spot.description && (
            <p style={{ margin: 0, color: "var(--color-subtext)", fontSize: "0.88em" }}>{spot.description}</p>
          )}

          <a
            href={googleMapsUrl(spot)}
            target="_blank"
            rel="noopener noreferrer"
            style={{ textDecoration: "none" }}
          >
            <button className="btn-outline" style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: "7px", fontSize: "0.88em" }}>
              <FontAwesomeIcon icon={faLocationDot} />
              Open in Google Maps
            </button>
          </a>
        </div>
      </div>

      <div style={{
        marginTop: "28px", textAlign: "center",
        display: "flex", flexDirection: "column", alignItems: "center", gap: "10px",
      }}>
        <p style={{ margin: 0, fontWeight: 700, fontSize: "1em", color: "var(--color-text)" }}>
          Save your favourite spots with bright
        </p>
        <p style={{ margin: 0, fontSize: "0.85em", color: "var(--color-subtext)" }}>
          Find the sunniest or shadiest route to any of them.
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

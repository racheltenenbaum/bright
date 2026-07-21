import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faStar } from "@fortawesome/free-solid-svg-icons";

const TILES = [
  { emoji: "☀️", label: "Walk in the sunshine", sub: "Real-time sun position, street by street" },
  { emoji: "🌿", label: "Or seek the shade", sub: "Stay cool when it's too hot to be outside" },
  { emoji: "📍", label: "Save what you find", sub: "Routes, spots, and favourite places" },
];

export default function HomePage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  return (
    <div className="page-container" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div className="home-inner">

        {/* Branding + CTA */}
        <div className="home-left">
          <img src="/logo.gif"      className="logo-light" alt="bright" style={{ height: "90px", marginBottom: "14px" }} />
          <img src="/logo-dark.gif" className="logo-dark"  alt="bright" style={{ height: "90px", marginBottom: "14px" }} />
          <p style={{ fontSize: "1.05em", color: "var(--color-subtext)", fontWeight: 700, lineHeight: 1.7, marginBottom: "28px", maxWidth: "260px" }}>
            Find routes in the sunshine - or the shade.
          </p>
          {isAuthenticated ? (
            <div className="home-cta">
              <button onClick={() => navigate("/plan")} style={{ fontSize: "1.05em", padding: "0.65em 2.4em" }}>
                to the sun <FontAwesomeIcon icon={faStar} style={{ fontSize: "0.75em" }} />
              </button>
              <Link to="/about" style={{ fontSize: "0.85em", color: "var(--color-subtext)", fontWeight: 600 }}>
                discover bright →
              </Link>
            </div>
          ) : (
            <div className="home-cta">
              <div style={{ display: "flex", gap: "14px" }}>
                <Link to="/login">
                  <button style={{ fontSize: "1em", padding: "0.65em 2em" }}>Log in</button>
                </Link>
                <Link to="/register">
                  <button className="btn-outline" style={{ fontSize: "1em", padding: "0.65em 2em" }}>Register</button>
                </Link>
              </div>
              <Link to="/about" style={{ fontSize: "0.85em", color: "var(--color-subtext)", fontWeight: 600 }}>
                discover bright →
              </Link>
            </div>
          )}
        </div>

        {/* Feature tiles — desktop only */}
        <div className="home-tiles">
          {TILES.map(({ emoji, label, sub }) => (
            <div key={label} style={{
              background: "var(--color-surface)",
              border: "2px solid var(--color-card-border)",
              borderRadius: "20px",
              padding: "22px 20px",
            }}>
              <div style={{ fontSize: "1.9em", marginBottom: "10px" }}>{emoji}</div>
              <p style={{ margin: "0 0 5px", fontWeight: 800, fontSize: "0.92em", color: "var(--color-text)" }}>{label}</p>
              <p style={{ margin: 0, fontSize: "0.78em", color: "var(--color-subtext)", fontWeight: 600, lineHeight: 1.55 }}>{sub}</p>
            </div>
          ))}
        </div>

      </div>
    </div>
  );
}

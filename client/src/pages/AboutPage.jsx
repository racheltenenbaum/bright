import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faSun, faMagnifyingGlass,
  faLocationDot, faBookmark, faShareNodes,
  faPersonWalking, faSliders,
} from "@fortawesome/free-solid-svg-icons";

const STEPS = [
  { icon: faLocationDot,   label: "Tap a start and end point - and select your sun / shade preference" },
  { icon: faSun,           label: "bright calculates the real-time sun position" },
  { icon: faPersonWalking, label: "Walk the sunniest (or shadiest) route" },
];

const FEATURES = [
  {
    icon: faMagnifyingGlass,
    title: "Find places that are sunny or shaded right now",
    body: "Cafes, bars, parks, and restaurants open right now, filtered by sun or shade.",
    accent: "#FFD600",
  },
  {
    icon: faBookmark,
    title: "Save your frequently taken routes",
    body: "For your home → work or work → gym daily routes. bright recalculates sun and shade every time you open them.",
    accent: "#3CB9FF",
  },
  {
    icon: faLocationDot,
    title: "Save spots",
    body: "Save sunny benches or shady terraces as spots and use them as route endpoints.",
    accent: "#FF7A3C",
  },
  {
    icon: faSliders,
    title: "Tailored to you",
    body: "Set your default sun/shade mode, pick your map style (roadmap, terrain or satellite), and control how much of a detour bright can suggest to maximize sun/shade exposure.",
    accent: "#E84393",
  },
  {
    icon: faShareNodes,
    title: "Share anything",
    body: "Send a route or spot to anyone via link — no account needed to view.",
    accent: "#7B5FE8",
  },
];

export default function AboutPage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  return (
    <div className="page-container">
      <div className="about-inner">

        {/* Hero */}
        <div className="about-hero">
          <Link to={isAuthenticated ? "/plan" : "/"}>
            <img src="/logo.gif"      className="logo-light" alt="bright" style={{ height: "100px", marginBottom: "18px", cursor: "pointer" }} />
            <img src="/logo-dark.gif" className="logo-dark"  alt="bright" style={{ height: "100px", marginBottom: "18px", cursor: "pointer" }} />
          </Link>
          <h1 style={{ margin: "0 0 14px", fontSize: "2em", fontWeight: 900, color: "var(--color-text)", lineHeight: 1.15 }}>
            Sunshine, mapped.
          </h1>
          <p style={{ margin: 0, fontSize: "1.05em", color: "var(--color-subtext)", fontWeight: 600, lineHeight: 1.7, maxWidth: "420px" }}>
            Find the sunniest walking route using real-time sun position. Or shadiest, your call.
          </p>
        </div>

        {/* How it works */}
        <div className="about-steps-card">
          <p style={{ margin: "0 0 20px", fontWeight: 900, fontSize: "0.8em", letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-subtext)" }}>
            How it works
          </p>
          <div className="about-steps-row">
            {STEPS.map(({ icon, label }, i) => (
              <div key={i} className="about-step-item">
                <span className="about-step-number">{i + 1}</span>
                <div className="about-step-circle" style={{
                  borderRadius: "50%",
                  background: "var(--color-accent)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  flexShrink: 0,
                }}>
                  <FontAwesomeIcon
                    icon={icon}
                    className={`about-step-icon${i === 1 ? " about-step-sun-spin" : ""}`}
                    style={{ color: "rgba(255,255,255,0.9)" }}
                  />
                </div>
                <p className="about-step-label" style={{ margin: 0, fontSize: "0.92em", fontWeight: 700, color: "var(--color-text)", lineHeight: 1.45 }}>
                  {label}
                </p>
                {i < STEPS.length - 1 && (
                  <div className="about-step-connector-v" />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Feature list */}
        <div>
          <p style={{ margin: "0 0 18px", fontWeight: 900, fontSize: "0.8em", letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-subtext)" }}>
            What you can do
          </p>
          <div className="about-feature-list">
            <div className="about-feature-items">
              {FEATURES.map(({ icon, title, body, accent }) => (
                <div key={title} className="about-feature-row">
                  <div style={{
                    width: "34px", height: "34px", borderRadius: "10px", flexShrink: 0, marginTop: "2px",
                    background: accent + "20",
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}>
                    <FontAwesomeIcon icon={icon} style={{ color: accent, fontSize: "0.95em" }} />
                  </div>
                  <div>
                    <p style={{ margin: "0 0 3px", fontWeight: 800, fontSize: "0.88em", color: "var(--color-text)" }}>{title}</p>
                    <p style={{ margin: 0, fontSize: "0.78em", color: "var(--color-subtext)", lineHeight: 1.6 }}>{body}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* CTA as 6th grid slot — sun blob */}
            <div className="about-feature-cta">
              <FontAwesomeIcon icon={faSun} className="about-cta-sun-bg" />
              <div className="about-cta-content">
                {isAuthenticated ? (
                  <button
                    onClick={() => navigate("/plan")}
                    className="about-cta-link"
                    style={{
                      background: "none", border: "none", boxShadow: "none", borderRadius: 0,
                      padding: "4px 0", borderBottom: "2.5px solid var(--color-accent)",
                      cursor: "pointer", fontSize: "1.2em", fontWeight: 800,
                      color: "var(--color-text)", display: "flex", alignItems: "center", gap: "8px",
                    }}
                  >
                    Start planning →
                  </button>
                ) : (
                  <>
                    <Link to="/register" className="about-cta-link" style={{
                      background: "none", border: "none", boxShadow: "none", borderRadius: 0,
                      padding: "4px 0", borderBottom: "2.5px solid var(--color-accent)",
                      fontSize: "1.2em", fontWeight: 800,
                      color: "var(--color-text)", display: "flex", alignItems: "center", gap: "8px",
                      textDecoration: "none",
                    }}>
                      Start your sun expedition → <FontAwesomeIcon icon={faSun} style={{ fontSize: "0.85em" }} />
                    </Link>
                    <p style={{ margin: "12px 0 0", fontSize: "0.85em", color: "var(--color-subtext)", textAlign: "center" }}>
                      Already have an account? <Link to="/login">Log in</Link>
                    </p>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>

        <p style={{ margin: "32px 0 0", textAlign: "center", fontSize: "0.78em", color: "var(--color-subtext)" }}>
          <Link to="/privacy">Privacy Policy</Link>
        </p>

      </div>
    </div>
  );
}

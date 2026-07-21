import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faSun, faMoon, faMagnifyingGlass,
  faLocationDot, faBookmark, faStar, faShareNodes,
  faArrowRight,
} from "@fortawesome/free-solid-svg-icons";

const STEPS = [
  { emoji: "📍", label: "Enter two addresses - or just tap the map" },
  { emoji: "☀️", label: "bright calculates the real-time sun position" },
  { emoji: "🚶", label: "Walk your sunniest (or shadiest) route" },
];

const FEATURES = [
  {
    icon: faMagnifyingGlass,
    title: "Find places",
    body: "Cafes, bars, parks, and restaurants open right now, filtered by whether they're in the sun or shade at this exact moment.",
    accent: "#FFD600",
    bg: "var(--color-accent-glow, #FFF9D6)",
  },
  {
    icon: faLocationDot,
    title: "Save spots",
    body: "Save any sunny bench or shady terrace as a spot. Use them as route endpoints or share them with a friend.",
    accent: "#FF7A3C",
    bg: "#FFF1EB",
  },
  {
    icon: faBookmark,
    title: "Save routes",
    body: "Save routes you love. bright recalculates the sun and shade every time you reload, so it's always accurate.",
    accent: "#3CB9FF",
    bg: "#EBF6FF",
  },
  {
    icon: faShareNodes,
    title: "Share anything",
    body: "Send a route or spot to anyone via link. No account needed to view - they can open it straight in Google Maps.",
    accent: "#7B5FE8",
    bg: "#F0EDFF",
  },
  {
    icon: faMoon,
    title: "Night mode",
    body: "After sunset the app switches to night mode automatically. Route planning still works, just without sun colouring.",
    accent: "#3D5A99",
    bg: "#EDF0FF",
  },
  {
    icon: faSun,
    title: "Or seek the shade",
    body: "Not a fan of the heat? Toggle to shade mode and bright flips everything, finding you the coolest path instead.",
    accent: "#2ECC71",
    bg: "#EDFAF3",
  },
];

export default function AboutPage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [hovered, setHovered] = useState(null);

  return (
    <div className="page-container" style={{ maxWidth: "560px", margin: "0 auto", padding: "28px 16px 56px" }}>

      {/* Hero */}
      <div style={{ textAlign: "center", marginBottom: "36px" }}>
        <img src="/logo.gif"      className="logo-light" alt="bright" style={{ height: "60px", marginBottom: "12px" }} />
        <img src="/logo-dark.gif" className="logo-dark"  alt="bright" style={{ height: "60px", marginBottom: "12px" }} />
        <h1 style={{ margin: "0 0 10px", fontSize: "1.6em", fontWeight: 900, color: "var(--color-text)", lineHeight: 1.2 }}>
          Walk in the sunshine.
        </h1>
        <p style={{ margin: 0, fontSize: "1em", color: "var(--color-subtext)", fontWeight: 600, lineHeight: 1.7 }}>
          bright finds you the sunniest - or shadiest -<br />
          walking route using real-time sun position.
        </p>
      </div>

      {/* How it works */}
      <div style={{
        background: "var(--color-surface)",
        border: "2.5px solid var(--color-card-border)",
        borderRadius: "20px",
        padding: "20px 20px 16px",
        marginBottom: "28px",
        boxShadow: "4px 4px 0 var(--color-accent-dim)",
      }}>
        <p style={{ margin: "0 0 16px", fontWeight: 900, fontSize: "0.8em", letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-subtext)" }}>
          How it works
        </p>
        {STEPS.map(({ emoji, label }, i) => (
          <div key={i}>
            <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
              <div style={{
                width: "36px", height: "36px", borderRadius: "50%", flexShrink: 0,
                background: "var(--color-accent)", color: "#fff",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontWeight: 900, fontSize: "0.9em",
              }}>
                {i + 1}
              </div>
              <p style={{ margin: 0, fontSize: "0.92em", fontWeight: 700, color: "var(--color-text)", lineHeight: 1.4 }}>
                <span style={{ marginRight: "6px" }}>{emoji}</span>{label}
              </p>
            </div>
            {i < STEPS.length - 1 && (
              <div style={{ width: "2px", height: "14px", background: "var(--color-divider)", margin: "3px 0 3px 17px" }} />
            )}
          </div>
        ))}
      </div>

      {/* Feature grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "36px" }}>
        {FEATURES.map(({ icon, title, body, accent, bg }, i) => (
          <div
            key={title}
            onMouseEnter={() => setHovered(i)}
            onMouseLeave={() => setHovered(null)}
            style={{
              background: hovered === i ? bg : "var(--color-surface)",
              border: `2px solid ${hovered === i ? accent : "var(--color-card-border)"}`,
              borderRadius: "16px",
              padding: "16px 14px",
              cursor: "default",
              transition: "background 0.18s, border-color 0.18s, transform 0.12s, box-shadow 0.12s",
              transform: hovered === i ? "translateY(-2px)" : "none",
              boxShadow: hovered === i ? `3px 5px 0 ${accent}33` : "3px 3px 0 var(--color-accent-dim)",
            }}
          >
            <div style={{
              width: "34px", height: "34px", borderRadius: "10px", marginBottom: "10px",
              background: accent + "22",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <FontAwesomeIcon icon={icon} style={{ color: accent, fontSize: "1em" }} />
            </div>
            <p style={{ margin: "0 0 5px", fontWeight: 800, fontSize: "0.88em", color: "var(--color-text)" }}>{title}</p>
            <p style={{ margin: 0, fontSize: "0.78em", color: "var(--color-subtext)", lineHeight: 1.55 }}>{body}</p>
          </div>
        ))}
      </div>

      {/* CTA */}
      <div style={{ textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: "12px" }}>
        {isAuthenticated ? (
          <button
            onClick={() => navigate("/plan")}
            style={{ fontSize: "1em", padding: "0.65em 2.4em", display: "flex", alignItems: "center", gap: "8px" }}
          >
            Start planning <FontAwesomeIcon icon={faStar} style={{ fontSize: "0.75em" }} />
          </button>
        ) : (
          <>
            <Link to="/register">
              <button style={{ fontSize: "1em", padding: "0.65em 2.4em", display: "flex", alignItems: "center", gap: "8px" }}>
                Get started free <FontAwesomeIcon icon={faArrowRight} style={{ fontSize: "0.8em" }} />
              </button>
            </Link>
            <p style={{ margin: 0, fontSize: "0.85em", color: "var(--color-subtext)" }}>
              Already have an account? <Link to="/login">Log in</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}

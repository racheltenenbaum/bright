import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faStar, faLocationDot, faSun, faPersonWalking } from "@fortawesome/free-solid-svg-icons";

const STEPS = [
  { icon: faLocationDot,   label: "Tap a start and end point and select your sun / shade preference" },
  { icon: faSun,           label: "bright calculates the real-time sun position" },
  { icon: faPersonWalking, label: "Walk the sunniest (or shadiest) route" },
];

export default function HomePage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  return (
    <div className="page-container" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div className="home-inner">

        {/* Branding + CTA */}
        <div className="home-left">
          <img src="/logo.gif"      className="logo-light home-logo" alt="bright" style={{ marginBottom: "14px" }} />
          <img src="/logo-dark.gif" className="logo-dark home-logo"  alt="bright" style={{ marginBottom: "14px" }} />
          <h1 className="home-headline">Sunshine, mapped.</h1>
          <p className="home-tagline">
            your sun companion — whether you love it or hide away.
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

        {/* How it works — desktop only */}
        <div className="home-steps">
          <p style={{ margin: "0 0 24px", fontWeight: 900, fontSize: "0.8em", letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-subtext)" }}>
            How it works
          </p>
          {STEPS.map(({ icon, label }, i) => (
            <div key={i}>
              <div style={{ display: "flex", alignItems: "center", gap: "18px" }}>
                <div style={{
                  position: "relative",
                  width: "52px", height: "52px", borderRadius: "50%", flexShrink: 0,
                  background: "var(--color-accent)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <FontAwesomeIcon icon={icon} style={{ color: "rgba(255,255,255,0.9)", fontSize: "1.1em" }} />
                </div>
                <p style={{ margin: 0, fontSize: "0.97em", fontWeight: 700, color: "var(--color-text)", lineHeight: 1.45 }}>
                  {label}
                </p>
              </div>
              {i < STEPS.length - 1 && (
                <div style={{ width: "2px", height: "20px", background: "var(--color-divider)", margin: "6px 0 6px 25px" }} />
              )}
            </div>
          ))}
        </div>

      </div>
    </div>
  );
}

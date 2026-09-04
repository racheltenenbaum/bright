import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faHand, faEllipsisVertical } from "@fortawesome/free-solid-svg-icons";
import api from "../api";

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const menuRef = useRef(null);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackText, setFeedbackText] = useState("");
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackDone, setFeedbackDone] = useState(false);
  const [feedbackError, setFeedbackError] = useState(false);

  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function go(path) {
    setOpen(false);
    navigate(path);
  }

  return (
    <>
    <nav style={{ flexShrink: 0, background: "var(--color-bg)", transition: "background-color 0.3s" }}>
      <div style={{
        padding: "10px 16px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}>
      <img src="/logo.gif"      className="logo-light" alt="bright" onClick={() => navigate("/plan")} style={{ height: "40px", cursor: "pointer" }} />
      <img src="/logo-dark.gif" className="logo-dark"  alt="bright" onClick={() => navigate("/plan")} style={{ height: "40px", cursor: "pointer" }} />

      <div ref={menuRef} style={{ position: "relative", display: "flex", alignItems: "center", gap: "0px" }}>
        <span style={{ color: "var(--color-subtext)", fontSize: "0.88em", fontWeight: 700 }}>
          Hi, {user.first_name}! <FontAwesomeIcon icon={faHand} />
        </span>
        <button
          onClick={() => setOpen(o => !o)}
          style={{
            background: "none", border: "none", boxShadow: "none",
            padding: "4px 0 4px 4px", fontSize: "1.1em", color: "var(--color-subtext)",
          }}
        >
          <FontAwesomeIcon icon={faEllipsisVertical} />
        </button>

        {open && (
          <div style={{
            position: "absolute", top: "calc(100% + 8px)", right: 0,
            background: "var(--color-surface)",
            border: "2.5px solid var(--color-card-border)",
            borderRadius: "16px",
            boxShadow: "4px 4px 0 var(--color-card-shadow)",
            minWidth: "150px",
            zIndex: 1000,
            overflow: "hidden",
          }}>
            {[
              { label: "Plan Route", path: "/plan" },
              { label: "Routes", path: "/my-routes" },
              { label: "Spots", path: "/my-spots" },
              { label: "My Account", path: "/my-account" },
              { label: "About", path: "/about" },
            ].map(({ label, path }) => (
              <button
                key={path}
                onClick={() => go(path)}
                style={{
                  display: "block", width: "100%", textAlign: "left",
                  background: "none", border: "none", boxShadow: "none",
                  borderRadius: 0, padding: "12px 18px",
                  fontSize: "0.9em", fontWeight: 700, color: "var(--color-text)",
                  borderBottom: "1px solid var(--color-divider)",
                }}
              >
                {label}
              </button>
            ))}
            <button
              onClick={() => { setOpen(false); setFeedbackOpen(true); setFeedbackText(""); setFeedbackDone(false); setFeedbackError(false); }}
              style={{
                display: "block", width: "100%", textAlign: "left",
                background: "none", border: "none", boxShadow: "none",
                borderRadius: 0, padding: "12px 18px",
                fontSize: "0.9em", fontWeight: 700, color: "var(--color-text)",
                borderBottom: "1px solid var(--color-divider)",
              }}
            >
              Send feedback
            </button>
            <button
              onClick={() => { setOpen(false); logout(); navigate("/"); }}
              style={{
                display: "block", width: "100%", textAlign: "left",
                background: "none", border: "none", boxShadow: "none",
                borderRadius: 0, padding: "12px 18px",
                fontSize: "0.9em", fontWeight: 700, color: "#C0392B",
              }}
            >
              Log out
            </button>
          </div>
        )}
      </div>
      </div>
    </nav>

      {feedbackOpen && (
        <div
          onClick={(e) => { if (e.target === e.currentTarget) setFeedbackOpen(false); }}
          style={{
            position: "fixed", inset: 0, zIndex: 2000,
            background: "rgba(0,0,0,0.4)",
            display: "flex", alignItems: "center", justifyContent: "center",
            padding: "20px",
          }}
        >
          <div style={{
            background: "var(--color-surface)",
            border: "2.5px solid var(--color-card-border)",
            borderRadius: "20px",
            padding: "28px 24px",
            boxShadow: "4px 4px 0 var(--color-accent-dim)",
            width: "min(480px, 100%)",
            display: "flex", flexDirection: "column", gap: "16px",
          }}>
            <h3 style={{ margin: 0, fontSize: "1.1em", fontWeight: 800 }}>Send feedback</h3>
            {feedbackDone ? (
              <p style={{ margin: 0, fontSize: "0.9em", fontWeight: 600, color: "#5A8F5A" }}>
                Thanks for your feedback!
              </p>
            ) : feedbackError ? (
              <p style={{ margin: 0, fontSize: "0.9em", fontWeight: 600, color: "#C0392B" }}>
                Couldn't send feedback. Please try again.
              </p>
            ) : (
              <>
                <textarea
                  value={feedbackText}
                  onChange={(e) => setFeedbackText(e.target.value)}
                  placeholder="What's on your mind?"
                  rows={5}
                  style={{
                    resize: "vertical", borderRadius: "12px",
                    border: "2px solid var(--color-card-border)",
                    padding: "12px 14px", fontSize: "0.9em",
                    fontFamily: "inherit", background: "var(--color-bg)",
                    color: "var(--color-text)", outline: "none",
                  }}
                />
                <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
                  <button
                    className="btn-outline"
                    onClick={() => setFeedbackOpen(false)}
                    style={{ padding: "0.45em 1.1em", fontSize: "0.88em" }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={async () => {
                      if (!feedbackText.trim()) return;
                      setFeedbackSubmitting(true);
                      const token = localStorage.getItem("token");
                      try {
                        await api.post(
                          "/feedback",
                          { message: feedbackText },
                          { headers: { Authorization: `Bearer ${token}` } },
                        );
                        setFeedbackDone(true);
                      } catch {
                        setFeedbackError(true);
                      } finally {
                        setFeedbackSubmitting(false);
                      }
                    }}
                    disabled={feedbackSubmitting || !feedbackText.trim()}
                    style={{ padding: "0.45em 1.1em", fontSize: "0.88em", fontWeight: 800 }}
                  >
                    {feedbackSubmitting ? "Sending…" : "Send"}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import api from "../api";

export default function ForgotPasswordPage() {
  const location = useLocation();
  const [email, setEmail] = useState(location.state?.email || "");
  const [error, setError] = useState(null);
  const [sent, setSent] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.post("/users/forgot-password", { email });
      setSent(true);
    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page-container" style={{ display: "flex", justifyContent: "center", alignItems: "center" }}>
      <div className="auth-card">
        <div style={{ textAlign: "center", marginBottom: "24px" }}>
          <Link to="/"><img src="/logo.gif" alt="bright" style={{ height: "60px", marginBottom: "8px", cursor: "pointer" }} /></Link>
          <h2 style={{ margin: 0, fontSize: "1.5em" }}>Reset your password</h2>
        </div>

        {sent ? (
          <p style={{ textAlign: "center", fontSize: "0.9em", color: "var(--color-text)" }}>
            If an account exists for <strong>{email}</strong>, we&apos;ve sent a link to reset your password.
            It&apos;s valid for 30 minutes.
          </p>
        ) : (
          <form onSubmit={handleSubmit}>
            <p style={{ margin: "0 0 16px", fontSize: "0.85em", color: "var(--color-subtext)" }}>
              Enter your email and we&apos;ll send you a link to reset your password.
            </p>
            <div className="field">
              <label>Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            {error && <p style={{ color: "#C0392B", margin: "0 0 12px", fontSize: "0.85em" }}>{error}</p>}
            <button type="submit" disabled={submitting} style={{ width: "100%", padding: "0.65em", fontSize: "0.95em", marginTop: "6px" }}>
              {submitting ? "Sending…" : "Send reset link"}
            </button>
          </form>
        )}

        <p style={{ margin: "18px 0 0", textAlign: "center", fontSize: "0.88em", color: "var(--color-subtext)" }}>
          <Link to="/login">Back to log in</Link>
        </p>
      </div>
    </div>
  );
}

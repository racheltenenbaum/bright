import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import api from "../api";

function passwordErrors(pw) {
  const errs = [];
  if (pw.length < 8) errs.push("at least 8 characters");
  if (!/\d/.test(pw)) errs.push("at least one number");
  return errs;
}

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";
  const [password, setPassword] = useState("");
  const [pwTouched, setPwTouched] = useState(false);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const pwErrs = passwordErrors(password);

  async function handleSubmit(e) {
    e.preventDefault();
    setPwTouched(true);
    if (pwErrs.length > 0) return;
    setError(null);
    setSubmitting(true);
    try {
      await api.post("/users/reset-password", { token, new_password: password });
      setDone(true);
      setTimeout(() => navigate("/login"), 2500);
    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  const showPwHints = pwTouched || password.length > 0;

  return (
    <div className="page-container" style={{ display: "flex", justifyContent: "center", alignItems: "center" }}>
      <div className="auth-card">
        <div style={{ textAlign: "center", marginBottom: "24px" }}>
          <Link to="/"><img src="/logo.gif" alt="bright" style={{ height: "60px", marginBottom: "8px", cursor: "pointer" }} /></Link>
          <h2 style={{ margin: 0, fontSize: "1.5em" }}>Choose a new password</h2>
        </div>

        {!token ? (
          <p style={{ textAlign: "center", fontSize: "0.9em", color: "#C0392B" }}>
            This reset link is missing its token. Request a new one from the{" "}
            <Link to="/forgot-password">forgot password</Link> page.
          </p>
        ) : done ? (
          <p style={{ textAlign: "center", fontSize: "0.9em", color: "var(--color-text)" }}>
            Your password has been updated. Taking you to log in…
          </p>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="field">
              <label>New password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onBlur={() => setPwTouched(true)}
                required
              />
              {showPwHints && (
                <div style={{ marginTop: "6px", display: "flex", flexDirection: "column", gap: "3px" }}>
                  {[
                    { label: "At least 8 characters", ok: password.length >= 8 },
                    { label: "At least one number", ok: /\d/.test(password) },
                  ].map(({ label, ok }) => (
                    <p key={label} style={{
                      margin: 0, fontSize: "0.78em",
                      color: ok ? "#5A8F5A" : (pwTouched && pwErrs.length > 0 ? "#C0392B" : "var(--color-subtext)"),
                      fontWeight: 600,
                    }}>
                      {ok ? "✓" : "·"} {label}
                    </p>
                  ))}
                </div>
              )}
            </div>
            {error && (
              <p style={{ color: "#C0392B", margin: "0 0 12px", fontSize: "0.85em" }}>
                {error} — you can request a new link from the{" "}
                <Link to="/forgot-password">forgot password</Link> page.
              </p>
            )}
            <button type="submit" disabled={submitting} style={{ width: "100%", padding: "0.65em", fontSize: "0.95em", marginTop: "6px" }}>
              {submitting ? "Saving…" : "Save new password"}
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

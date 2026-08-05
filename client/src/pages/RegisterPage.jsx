import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import api from "../api";
import { useAuth } from "../context/AuthContext";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function passwordErrors(pw) {
  const errs = [];
  if (pw.length < 8) errs.push("at least 8 characters");
  if (!/\d/.test(pw)) errs.push("at least one number");
  return errs;
}

export default function RegisterPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [form, setForm] = useState({ first_name: "", email: "", password: "" });
  const [emailError, setEmailError] = useState(null);
  const [pwTouched, setPwTouched] = useState(false);
  const [error, setError] = useState(null);

  const pwErrs = passwordErrors(form.password);

  function handleChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
    if (e.target.name === "email") setEmailError(null);
  }

  function handleEmailBlur() {
    if (form.email && !EMAIL_REGEX.test(form.email)) {
      setEmailError("Please enter a valid email address");
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setPwTouched(true);
    if (!EMAIL_REGEX.test(form.email)) {
      setEmailError("Please enter a valid email address");
      return;
    }
    if (pwErrs.length > 0) return;
    setError(null);
    try {
      const res = await api.post("/users/register", form);
      login(res.data.user, res.data.access_token);
      navigate("/plan");
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(Array.isArray(detail) ? detail.map(e => e.msg).join(". ") : (detail || "Something went wrong"));
    }
  }

  const showPwHints = pwTouched || form.password.length > 0;

  return (
    <div className="page-container" style={{ display: "flex", justifyContent: "center", alignItems: "center" }}>
      <div className="auth-card">
        <div style={{ textAlign: "center", marginBottom: "24px" }}>
          <img src="/logo.gif" alt="bright" style={{ height: "60px", marginBottom: "8px" }} />
          <h2 style={{ margin: 0, fontSize: "1.5em" }}>Create an account</h2>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>First name</label>
            <input type="text" name="first_name" value={form.first_name} onChange={handleChange} required />
          </div>
          <div className="field">
            <label>Email</label>
            <input
              name="email"
              type="email"
              value={form.email}
              onChange={handleChange}
              onBlur={handleEmailBlur}
              required
            />
            {emailError && <p style={{ color: "#C0392B", margin: "4px 0 0", fontSize: "0.82em" }}>{emailError}</p>}
          </div>
          <div className="field">
            <label>Password</label>
            <input
              name="password"
              type="password"
              value={form.password}
              onChange={handleChange}
              onBlur={() => setPwTouched(true)}
              required
            />
            {showPwHints && (
              <div style={{ marginTop: "6px", display: "flex", flexDirection: "column", gap: "3px" }}>
                {[
                  { label: "At least 8 characters", ok: form.password.length >= 8 },
                  { label: "At least one number", ok: /\d/.test(form.password) },
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
          {error && <p style={{ color: "#C0392B", margin: "0 0 12px", fontSize: "0.85em" }}>{error}</p>}
          <button type="submit" style={{ width: "100%", padding: "0.65em", fontSize: "0.95em", marginTop: "6px" }}>
            Register
          </button>
        </form>
        <p style={{ margin: "14px 0 0", textAlign: "center", fontSize: "0.78em", color: "var(--color-subtext)" }}>
          By creating an account, you agree to our <Link to="/privacy">Privacy Policy</Link>.
        </p>
        <p style={{ margin: "10px 0 0", textAlign: "center", fontSize: "0.88em", color: "var(--color-subtext)" }}>
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  );
}

import { useState } from "react";
import PropTypes from "prop-types";
import { Link } from "react-router-dom";
import api from "../api";
import { useAuth } from "../context/AuthContext";
import { track } from "../analytics";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faStar } from "@fortawesome/free-solid-svg-icons";
import SocialAuthButtons from "./SocialAuthButtons";

export default function LoginForm({ onSuccess, onSwitch, onLeave }) {
  const { login } = useAuth();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState(null);

  function handleChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    try {
      const res = await api.post("/users/login", form);
      login(res.data.user, res.data.access_token);
      track("Logged In");
      onSuccess();
    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong");
    }
  }

  return (
    <>
        <div style={{ textAlign: "center", marginBottom: "24px" }}>
          <img src="/logo.gif" alt="bright" style={{ height: "60px", marginBottom: "8px" }} />
          <h2 id="auth-modal-title" style={{ margin: 0, fontSize: "1.5em" }}>Welcome back</h2>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>Email</label>
            <input name="email" type="email" value={form.email} onChange={handleChange} required />
          </div>
          <div className="field">
            <label>Password</label>
            <input name="password" type="password" value={form.password} onChange={handleChange} required />
          </div>
          {error && (
            <p style={{ color: "#C0392B", margin: "0 0 12px", fontSize: "0.85em" }}>
              {error} — <Link to="/forgot-password" state={{ email: form.email }} onClick={onLeave}>Forgot password?</Link>
            </p>
          )}
          <button type="submit" style={{ width: "100%", padding: "0.65em", fontSize: "0.95em", marginTop: "6px" }}>
            to the sun <FontAwesomeIcon icon={faStar} style={{ fontSize: "0.75em" }} />
          </button>
        </form>
        <div style={{ display: "flex", alignItems: "center", gap: "10px", margin: "20px 0" }}>
          <div style={{ flex: 1, height: "1px", background: "var(--color-divider)" }} />
          <span style={{ fontSize: "0.78em", color: "var(--color-subtext)", fontWeight: 600 }}>or</span>
          <div style={{ flex: 1, height: "1px", background: "var(--color-divider)" }} />
        </div>
        <SocialAuthButtons onError={setError} onSuccess={onSuccess} />
        <p style={{ margin: "18px 0 0", textAlign: "center", fontSize: "0.88em", color: "var(--color-subtext)" }}>
          Don't have an account?{" "}
          <button type="button" className="auth-switch" onClick={onSwitch}>Register</button>
        </p>
    </>
  );
}

LoginForm.propTypes = {
  onSuccess: PropTypes.func.isRequired,
  onSwitch: PropTypes.func.isRequired,
  onLeave: PropTypes.func.isRequired,
};

import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import api from "../api";
import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const navigate = useNavigate();
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
      navigate("/");
    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong");
    }
  }

  return (
    <div className="page-container" style={{ display: "flex", justifyContent: "center", alignItems: "center" }}>
      <div className="auth-card">
        <div style={{ textAlign: "center", marginBottom: "24px" }}>
          <img src="/logo.gif" alt="bright" style={{ height: "60px", marginBottom: "8px" }} />
          <h2 style={{ margin: 0, fontSize: "1.5em" }}>Welcome back</h2>
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
          {error && <p style={{ color: "#C0392B", margin: "0 0 12px", fontSize: "0.85em" }}>{error}</p>}
          <button type="submit" style={{ width: "100%", padding: "0.65em", fontSize: "0.95em", marginTop: "6px" }}>
            Log in
          </button>
        </form>
        <p style={{ margin: "18px 0 0", textAlign: "center", fontSize: "0.88em", color: "var(--color-subtext)" }}>
          Don't have an account? <Link to="/register">Register</Link>
        </p>
      </div>
    </div>
  );
}

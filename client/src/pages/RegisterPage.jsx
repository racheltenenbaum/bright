import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import axios from "axios";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ first_name: "", email: "", password: "" });
  const [emailError, setEmailError] = useState(null);
  const [error, setError] = useState(null);

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
    if (!EMAIL_REGEX.test(form.email)) {
      setEmailError("Please enter a valid email address");
      return;
    }
    setError(null);
    try {
      await axios.post("http://localhost:8000/users/register", form);
      navigate("/");
    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong");
    }
  }

  return (
    <div className="page-container" style={{ display: "flex", justifyContent: "center", alignItems: "center" }}>
      <div className="auth-card">
        <div style={{ textAlign: "center", marginBottom: "24px" }}>
          <div style={{ fontSize: "40px", marginBottom: "6px" }}>☀️</div>
          <h2 style={{ margin: 0, fontSize: "1.5em" }}>Create an account</h2>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>First name</label>
            <input name="first_name" value={form.first_name} onChange={handleChange} required />
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
            <input name="password" type="password" value={form.password} onChange={handleChange} required />
          </div>
          {error && <p style={{ color: "#C0392B", margin: "0 0 12px", fontSize: "0.85em" }}>{error}</p>}
          <button type="submit" style={{ width: "100%", padding: "0.65em", fontSize: "0.95em", marginTop: "6px" }}>
            Register
          </button>
        </form>
        <p style={{ margin: "18px 0 0", textAlign: "center", fontSize: "0.88em", color: "#7B5800" }}>
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  );
}

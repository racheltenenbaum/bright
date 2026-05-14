import { useState } from "react";
import axios from "axios";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function RegisterForm() {
  const [form, setForm] = useState({ first_name: "", email: "", password: "" });
  const [emailError, setEmailError] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

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
      setSuccess(true);
    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong");
    }
  }

  if (success) return <p>Account created! Welcome, {form.first_name}.</p>;

  return (
    <form onSubmit={handleSubmit}>
      <h2>Create an account</h2>

      <div>
        <label>First name</label>
        <input name="first_name" value={form.first_name} onChange={handleChange} required />
      </div>

      <div>
        <label>Email</label>
        <input
          name="email"
          type="email"
          value={form.email}
          onChange={handleChange}
          onBlur={handleEmailBlur}
          required
        />
        {emailError && <p style={{ color: "red" }}>{emailError}</p>}
      </div>

      <div>
        <label>Password</label>
        <input name="password" type="password" value={form.password} onChange={handleChange} required />
      </div>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <button type="submit">Register</button>
    </form>
  );
}

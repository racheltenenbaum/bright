import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Navbar() {
  const { user, logout } = useAuth();

  return (
    <nav style={{
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      padding: "10px 24px",
      background: "#FFF9C4",
      borderBottom: "2.5px solid #ffffff",
      boxShadow: "0 3px 0 #E8C000",
      flexShrink: 0,
    }}>
      <span style={{
        fontFamily: "'Fredoka', sans-serif",
        fontWeight: 700,
        fontSize: "1.5em",
        color: "#3D2C00",
        letterSpacing: "0.5px",
      }}>
        bright ☀️
      </span>
      <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
        <Link to="/plan" style={{ color: "#7B5800", fontWeight: 700, fontSize: "0.9em" }}>Plan Route</Link>
        <Link to="/my-routes" style={{ color: "#7B5800", fontWeight: 700, fontSize: "0.9em" }}>My Routes</Link>
        <span style={{ color: "#A87500", fontSize: "0.88em", fontWeight: 700 }}>Hi, {user.first_name}! 👋</span>
        <button className="btn-outline" onClick={logout}>Log out</button>
      </div>
    </nav>
  );
}

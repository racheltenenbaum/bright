import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Navbar() {
  const { user, logout } = useAuth();

  return (
    <nav style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 20px", borderBottom: "1px solid #ccc" }}>
      <span>bright</span>
      <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
        <Link to="/plan" style={{ textDecoration: "none", color: "inherit" }}>Plan Route</Link>
        <Link to="/my-routes" style={{ textDecoration: "none", color: "inherit" }}>My Routes</Link>
        <span>Hi, {user.first_name}!</span>
        <button onClick={logout}>Log out</button>
      </div>
    </nav>
  );
}

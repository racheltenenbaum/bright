import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faSun, faHand } from "@fortawesome/free-solid-svg-icons";

export default function Navbar() {
  const { user, logout } = useAuth();

  return (
    <nav style={{
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      padding: "10px 24px",
      flexShrink: 0,
    }}>
      <span style={{
        fontFamily: "'Fredoka', sans-serif",
        fontWeight: 700,
        fontSize: "1.5em",
        color: "#3D2C00",
        letterSpacing: "0.5px",
      }}>
        bright <FontAwesomeIcon icon={faSun} style={{ color: "#FFD600", fontSize: "0.85em" }} />
      </span>
      <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
        <Link to="/plan" style={{ color: "#7B5800", fontWeight: 700, fontSize: "0.9em" }}>Plan Route</Link>
        <Link to="/my-routes" style={{ color: "#7B5800", fontWeight: 700, fontSize: "0.9em" }}>My Routes</Link>
        <span style={{ color: "#A87500", fontSize: "0.88em", fontWeight: 700 }}>Hi, {user.first_name}! <FontAwesomeIcon icon={faHand} /></span>
        <button className="btn-outline" onClick={logout}>Log out</button>
      </div>
    </nav>
  );
}

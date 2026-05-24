import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faStar } from "@fortawesome/free-solid-svg-icons";

export default function HomePage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  return (
    <div className="page-container" style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      textAlign: "center",
    }}>
      <img src="/logo.gif" alt="bright" style={{ height: "120px", marginBottom: "16px" }} />
      <p style={{
        fontSize: "1.05em",
        color: "#7B5800",
        marginBottom: "36px",
        maxWidth: "260px",
        lineHeight: 1.7,
        fontWeight: 600,
      }}>
        Find routes in the sunshine — or the shade.
      </p>
      {isAuthenticated ? (
        <button onClick={() => navigate("/plan")} style={{ fontSize: "1.05em", padding: "0.65em 2.4em" }}>
          to the sun <FontAwesomeIcon icon={faStar} style={{ fontSize: "0.75em" }} />
        </button>
      ) : (
        <div style={{ display: "flex", gap: "14px" }}>
          <Link to="/login">
            <button style={{ fontSize: "1em", padding: "0.65em 2em" }}>Log in</button>
          </Link>
          <Link to="/register">
            <button className="btn-outline" style={{ fontSize: "1em", padding: "0.65em 2em" }}>Register</button>
          </Link>
        </div>
      )}
    </div>
  );
}

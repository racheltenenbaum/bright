import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function HomePage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  return (
    <div>
      <h1>bright</h1>
      <p>Find routes in the sunshine — or the shade.</p>

      {isAuthenticated ? (
        <button onClick={() => navigate("/plan")}>Plan Route</button>
      ) : (
        <div>
          <Link to="/login"><button>Log in</button></Link>
          <Link to="/register"><button>Register</button></Link>
        </div>
      )}
    </div>
  );
}

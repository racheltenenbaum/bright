import { useAuth } from "../context/AuthContext";

export default function Navbar() {
  const { user, logout } = useAuth();

  return (
    <nav style={{ display: "flex", justifyContent: "space-between", padding: "10px 20px", borderBottom: "1px solid #ccc" }}>
      <span>bright</span>
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        <span>Hi, {user.first_name}!</span>
        <button onClick={logout}>Log out</button>
      </div>
    </nav>
  );
}

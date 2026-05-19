import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faHand, faEllipsisVertical } from "@fortawesome/free-solid-svg-icons";

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function go(path) {
    setOpen(false);
    navigate(path);
  }

  return (
    <nav style={{ flexShrink: 0 }}>
      <div style={{
        maxWidth: "700px",
        margin: "0 auto",
        padding: "10px 16px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}>
      <img src="/logo.gif" alt="bright" style={{ height: "40px" }} />

      <div ref={menuRef} style={{ position: "relative", display: "flex", alignItems: "center", gap: "0px" }}>
        <span style={{ color: "#A87500", fontSize: "0.88em", fontWeight: 700 }}>
          Hi, {user.first_name}! <FontAwesomeIcon icon={faHand} />
        </span>
        <button
          onClick={() => setOpen(o => !o)}
          style={{
            background: "none", border: "none", boxShadow: "none",
            padding: "4px 0 4px 4px", fontSize: "1.1em", color: "#A87500",
          }}
        >
          <FontAwesomeIcon icon={faEllipsisVertical} />
        </button>

        {open && (
          <div style={{
            position: "absolute", top: "calc(100% + 8px)", right: 0,
            background: "#FFFDF5",
            border: "2.5px solid #ffffff",
            borderRadius: "16px",
            boxShadow: "4px 4px 0 #E8C000",
            minWidth: "150px",
            zIndex: 1000,
            overflow: "hidden",
          }}>
            {[
              { label: "Plan Route", path: "/plan" },
              { label: "My Routes", path: "/my-routes" },
              { label: "My Spots", path: "/my-spots" },
              { label: "My Account", path: "/my-account" },
            ].map(({ label, path }) => (
              <button
                key={path}
                onClick={() => go(path)}
                style={{
                  display: "block", width: "100%", textAlign: "left",
                  background: "none", border: "none", boxShadow: "none",
                  borderRadius: 0, padding: "12px 18px",
                  fontSize: "0.9em", fontWeight: 700, color: "#3D2C00",
                  borderBottom: "1px solid #F5E070",
                }}
              >
                {label}
              </button>
            ))}
            <button
              onClick={() => { setOpen(false); logout(); }}
              style={{
                display: "block", width: "100%", textAlign: "left",
                background: "none", border: "none", boxShadow: "none",
                borderRadius: 0, padding: "12px 18px",
                fontSize: "0.9em", fontWeight: 700, color: "#C0392B",
              }}
            >
              Log out
            </button>
          </div>
        )}
      </div>
      </div>
    </nav>
  );
}

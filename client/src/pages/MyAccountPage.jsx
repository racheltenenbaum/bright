import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import api from "../api";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faUser, faEnvelope, faCalendarDays, faPen, faCheck, faXmark } from "@fortawesome/free-solid-svg-icons";

function ReadonlyField({ icon, label, value }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
      <span style={{
        fontSize: "0.72em", fontWeight: 800, textTransform: "uppercase",
        letterSpacing: "0.06em", color: "var(--color-subtext)",
      }}>
        <FontAwesomeIcon icon={icon} style={{ marginRight: "5px" }} />{label}
      </span>
      <span style={{ fontSize: "0.97em", fontWeight: 600, color: "var(--color-text)" }}>
        {value}
      </span>
    </div>
  );
}

export default function MyAccountPage() {
  const { user, updateUser } = useAuth();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const joined = user?.created_at
    ? new Date(user.created_at).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })
    : "—";

  function startEdit() {
    setDraft(user.first_name);
    setError(null);
    setEditing(true);
  }

  function cancelEdit() {
    setEditing(false);
    setError(null);
  }

  async function saveName() {
    if (!draft.trim()) { setError("Name can't be blank."); return; }
    setSaving(true);
    setError(null);
    try {
      const token = localStorage.getItem("token");
      const res = await api.patch("/users/me", { first_name: draft.trim() }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      updateUser({ first_name: res.data.first_name });
      setEditing(false);
    } catch {
      setError("Could not save. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page-container" style={{ maxWidth: "480px" }}>
      <h2>My Account</h2>
      <div style={{
        background: "var(--color-surface)",
        border: "2.5px solid #ffffff",
        borderRadius: "20px",
        padding: "28px 24px",
        boxShadow: "4px 4px 0 var(--color-accent-dim)",
        display: "flex",
        flexDirection: "column",
        gap: "22px",
      }}>
        {/* Editable name */}
        <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
          <span style={{
            fontSize: "0.72em", fontWeight: 800, textTransform: "uppercase",
            letterSpacing: "0.06em", color: "var(--color-subtext)",
          }}>
            <FontAwesomeIcon icon={faUser} style={{ marginRight: "5px" }} />Name
          </span>
          {editing ? (
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <input
                type="text"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") saveName(); if (e.key === "Escape") cancelEdit(); }}
                autoFocus
                style={{ flex: 1 }}
              />
              <button onClick={saveName} disabled={saving} style={{ padding: "0.3em 0.7em", fontSize: "0.85em" }}>
                <FontAwesomeIcon icon={faCheck} />
              </button>
              <button onClick={cancelEdit} className="btn-outline" style={{ padding: "0.3em 0.7em", fontSize: "0.85em" }}>
                <FontAwesomeIcon icon={faXmark} />
              </button>
            </div>
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "0.97em", fontWeight: 600, color: "var(--color-text)" }}>
                {user?.first_name}
              </span>
              <button
                onClick={startEdit}
                style={{ background: "none", border: "none", boxShadow: "none", padding: "2px 4px", fontSize: "0.8em", color: "var(--color-subtext)" }}
              >
                <FontAwesomeIcon icon={faPen} />
              </button>
            </div>
          )}
          {error && <p style={{ margin: 0, fontSize: "0.82em", color: "#FF5A3C", fontWeight: 700 }}>{error}</p>}
        </div>

        <ReadonlyField icon={faEnvelope}     label="Email"        value={user?.email} />
        <ReadonlyField icon={faCalendarDays} label="Member since" value={joined} />
      </div>
    </div>
  );
}

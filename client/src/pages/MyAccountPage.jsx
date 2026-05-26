import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import api from "../api";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faUser, faEnvelope, faCalendarDays, faPen, faCheck, faXmark, faSlidersH, faSun, faCloud } from "@fortawesome/free-solid-svg-icons";

const DETOUR_STEPS = [10, 30, 50, 70, 100];
const DETOUR_LABELS = {
  10:  "Minimal",
  30:  "Small",
  50:  "Moderate",
  70:  "Large",
  100: "Maximum",
};

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

function TabBar({ active, onChange }) {
  const tabs = [
    { id: "profile", label: "Profile" },
    { id: "preferences", label: "Preferences" },
  ];
  return (
    <div style={{ display: "flex", gap: "4px", marginBottom: "20px" }}>
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          style={{
            flex: 1,
            padding: "9px 0",
            fontWeight: 700,
            fontSize: "0.88em",
            borderRadius: "12px",
            background: active === t.id ? "var(--color-accent)" : "var(--color-surface)",
            color: active === t.id ? "#fff" : "var(--color-subtext)",
            border: active === t.id ? "none" : "2px solid var(--color-border, #e0e0e0)",
            boxShadow: active === t.id ? "2px 2px 0 var(--color-accent-dim)" : "none",
            cursor: "pointer",
          }}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

function DetourSlider({ value, onChange, saving, error }) {
  const idx = Math.max(0, DETOUR_STEPS.indexOf(value) === -1 ? 1 : DETOUR_STEPS.indexOf(value));

  function handleSlider(e) {
    const step = DETOUR_STEPS[parseInt(e.target.value, 10)];
    if (step !== value) onChange(step);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      <div>
        <span style={{
          fontSize: "0.72em", fontWeight: 800, textTransform: "uppercase",
          letterSpacing: "0.06em", color: "var(--color-subtext)",
        }}>
          <FontAwesomeIcon icon={faSlidersH} style={{ marginRight: "5px" }} />Max Detour
        </span>
        <p style={{ margin: "4px 0 0", fontSize: "0.84em", color: "var(--color-subtext)", fontWeight: 500 }}>
          How much longer than the shortest route you're willing to walk to maximise sun or shade.
        </p>
      </div>

      {/* Current value badge */}
      <div style={{ textAlign: "center" }}>
        <span style={{
          fontSize: "2em", fontWeight: 800, color: "var(--color-accent)",
          lineHeight: 1,
        }}>
          {value}%
        </span>
        <span style={{
          display: "block", fontSize: "0.82em", fontWeight: 600,
          color: "var(--color-subtext)", marginTop: "2px",
        }}>
          {DETOUR_LABELS[value] ?? ""} detour
        </span>
      </div>

      {/* Slider */}
      <div style={{ padding: "0 4px" }}>
        <input
          type="range"
          min="0"
          max={DETOUR_STEPS.length - 1}
          step="1"
          value={idx}
          onChange={handleSlider}
          disabled={saving}
          style={{ width: "100%", accentColor: "var(--color-accent)", cursor: saving ? "not-allowed" : "pointer" }}
        />
        {/* Step labels */}
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: "4px" }}>
          {DETOUR_STEPS.map((step) => (
            <span key={step} style={{
              fontSize: "0.72em", fontWeight: 700,
              color: step === value ? "var(--color-accent)" : "var(--color-subtext)",
            }}>
              {step}%
            </span>
          ))}
        </div>
      </div>

      {saving && (
        <p style={{ margin: 0, fontSize: "0.82em", color: "var(--color-subtext)", fontWeight: 600 }}>
          Saving…
        </p>
      )}
      {error && (
        <p style={{ margin: 0, fontSize: "0.82em", color: "#FF5A3C", fontWeight: 700 }}>{error}</p>
      )}
    </div>
  );
}

export default function MyAccountPage() {
  const { user, updateUser } = useAuth();
  const [tab, setTab] = useState("profile");

  // Profile tab state
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [nameSaving, setNameSaving] = useState(false);
  const [nameError, setNameError] = useState(null);

  // Preferences tab state
  const [detour, setDetour] = useState(user?.pref_max_detour ?? 30);
  const [detourSaving, setDetourSaving] = useState(false);
  const [detourError, setDetourError] = useState(null);

  const [mode, setMode] = useState(user?.pref_mode ?? "sun");
  const [modeSaving, setModeSaving] = useState(false);
  const [modeError, setModeError] = useState(null);

  const joined = user?.created_at
    ? new Date(user.created_at).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })
    : "—";

  function startEdit() {
    setDraft(user.first_name);
    setNameError(null);
    setEditing(true);
  }

  function cancelEdit() {
    setEditing(false);
    setNameError(null);
  }

  async function saveName() {
    if (!draft.trim()) { setNameError("Name can't be blank."); return; }
    setNameSaving(true);
    setNameError(null);
    try {
      const token = localStorage.getItem("token");
      const res = await api.patch("/users/me", { first_name: draft.trim() }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      updateUser({ first_name: res.data.first_name });
      setEditing(false);
    } catch {
      setNameError("Could not save. Please try again.");
    } finally {
      setNameSaving(false);
    }
  }

  async function saveDetour(step) {
    setDetour(step);
    setDetourSaving(true);
    setDetourError(null);
    try {
      const token = localStorage.getItem("token");
      const res = await api.patch("/users/me", { pref_max_detour: step }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      updateUser({ pref_max_detour: res.data.pref_max_detour });
    } catch {
      setDetourError("Could not save. Please try again.");
      setDetour(user?.pref_max_detour ?? 30); // revert
    } finally {
      setDetourSaving(false);
    }
  }

  async function saveMode(value) {
    setMode(value);
    setModeSaving(true);
    setModeError(null);
    try {
      const token = localStorage.getItem("token");
      const res = await api.patch("/users/me", { pref_mode: value }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      updateUser({ pref_mode: res.data.pref_mode });
    } catch {
      setModeError("Could not save. Please try again.");
      setMode(user?.pref_mode ?? "sun"); // revert
    } finally {
      setModeSaving(false);
    }
  }

  const cardStyle = {
    background: "var(--color-surface)",
    border: "2.5px solid #ffffff",
    borderRadius: "20px",
    padding: "28px 24px",
    boxShadow: "4px 4px 0 var(--color-accent-dim)",
    display: "flex",
    flexDirection: "column",
    gap: "22px",
  };

  return (
    <div className="page-container" style={{ maxWidth: "480px" }}>
      <h2>My Account</h2>
      <TabBar active={tab} onChange={setTab} />

      {tab === "profile" && (
        <div style={cardStyle}>
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
                <button onClick={saveName} disabled={nameSaving} style={{ padding: "0.3em 0.7em", fontSize: "0.85em" }}>
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
            {nameError && <p style={{ margin: 0, fontSize: "0.82em", color: "#FF5A3C", fontWeight: 700 }}>{nameError}</p>}
          </div>

          <ReadonlyField icon={faEnvelope}     label="Email"        value={user?.email} />
          <ReadonlyField icon={faCalendarDays} label="Member since" value={joined} />
        </div>
      )}

      {tab === "preferences" && (
        <div style={cardStyle}>
          <DetourSlider
            value={detour}
            onChange={saveDetour}
            saving={detourSaving}
            error={detourError}
          />

          <hr style={{ border: "none", borderTop: "2px solid var(--color-border, #e0e0e0)", margin: "0" }} />

          {/* Default mode preference */}
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <div>
              <span style={{
                fontSize: "0.72em", fontWeight: 800, textTransform: "uppercase",
                letterSpacing: "0.06em", color: "var(--color-subtext)",
              }}>
                Default Route Preference
              </span>
              <p style={{ margin: "4px 0 0", fontSize: "0.84em", color: "var(--color-subtext)", fontWeight: 500 }}>
                Whether routes and place searches default to sun or shade.
              </p>
            </div>
            <div style={{ display: "flex", gap: "8px" }}>
              {[
                { value: "sun", icon: faSun, label: "Sun" },
                { value: "shade", icon: faCloud, label: "Shade" },
              ].map(({ value, icon, label }) => (
                <button
                  key={value}
                  onClick={() => !modeSaving && saveMode(value)}
                  disabled={modeSaving}
                  style={{
                    flex: 1,
                    padding: "10px 0",
                    fontWeight: 700,
                    fontSize: "0.88em",
                    borderRadius: "12px",
                    background: mode === value ? "var(--color-accent)" : "var(--color-surface)",
                    color: mode === value ? "#fff" : "var(--color-subtext)",
                    border: mode === value ? "none" : "2px solid var(--color-border, #e0e0e0)",
                    boxShadow: mode === value ? "2px 2px 0 var(--color-accent-dim)" : "none",
                    cursor: modeSaving ? "not-allowed" : "pointer",
                  }}
                >
                  <FontAwesomeIcon icon={icon} style={{ marginRight: "6px" }} />
                  {label}
                </button>
              ))}
            </div>
            {modeSaving && (
              <p style={{ margin: 0, fontSize: "0.82em", color: "var(--color-subtext)", fontWeight: 600 }}>
                Saving…
              </p>
            )}
            {modeError && (
              <p style={{ margin: 0, fontSize: "0.82em", color: "#FF5A3C", fontWeight: 700 }}>{modeError}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

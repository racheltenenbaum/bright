import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
const MAPS_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
const MAP_PREVIEW_CENTERS = {
  roadmap: "center=51.505,-0.09&zoom=13&maptype=roadmap",
  terrain: "center=47.2,11.5&zoom=9&maptype=terrain",
};
// Esri World Imagery: free, no API key, genuine satellite over Manhattan
const SATELLITE_PREVIEW_URL =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export?bbox=-74.02,40.69,-73.97,40.74&bboxSR=4326&size=200,120&format=png&f=image";
const MAP_PREVIEW_URL = (type) =>
  type === "satellite"
    ? SATELLITE_PREVIEW_URL
    : `https://maps.googleapis.com/maps/api/staticmap?${MAP_PREVIEW_CENTERS[type] ?? `center=51.505,-0.09&zoom=13&maptype=${type}`}&size=200x120&key=${MAPS_KEY}`;
const MAP_PREVIEW_FALLBACK = {
  roadmap:   "#f2efe9",
  satellite: "radial-gradient(ellipse at 40% 55%, #2a3a2a 0%, #1a2a1a 40%, transparent 70%), radial-gradient(ellipse at 75% 30%, #3a3028 0%, #28221a 40%, transparent 65%), linear-gradient(160deg, #0e1a0e 0%, #1a2814 40%, #2a2a1e 70%, #141e10 100%)",
  terrain:   "linear-gradient(135deg, #c8d4a0 0%, #a8b880 25%, #d4c898 50%, #b0a068 75%, #c8d4a8 100%)",
};
import { useAuth } from "../context/AuthContext";
import api from "../api";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faUser, faEnvelope, faCalendarDays, faPen, faCheck, faXmark, faSlidersH, faSun, faCloud, faChevronDown, faMap, faTrash } from "@fortawesome/free-solid-svg-icons";

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
  const { user, updateUser, logout } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState("profile");

  // Danger zone state
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  // Profile tab state
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [nameSaving, setNameSaving] = useState(false);
  const [nameError, setNameError] = useState(null);

  // Preferences tab state
  const [detour, setDetour] = useState(user?.pref_max_detour ?? 30);
  const [detourSaving, setDetourSaving] = useState(false);
  const [detourError, setDetourError] = useState(null);
  const [detourOpen, setDetourOpen] = useState(false);

  const [mode, setMode] = useState(user?.pref_mode ?? "sun");
  const [modeSaving, setModeSaving] = useState(false);
  const [modeError, setModeError] = useState(null);
  const [modeOpen, setModeOpen] = useState(false);

  const [mapControls, setMapControls] = useState(user?.pref_map_controls ?? false);
  const [mapControlsSaving, setMapControlsSaving] = useState(false);
  const [mapControlsError, setMapControlsError] = useState(null);
  const [mapControlsOpen, setMapControlsOpen] = useState(false);

  const [mapType, setMapType] = useState(user?.pref_map_type ?? "roadmap");
  const [mapTypeSaving, setMapTypeSaving] = useState(false);
  const [mapTypeError, setMapTypeError] = useState(null);

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

  async function saveMapType(value) {
    setMapType(value);
    setMapTypeSaving(true);
    setMapTypeError(null);
    try {
      const token = localStorage.getItem("token");
      const res = await api.patch("/users/me", { pref_map_type: value }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      updateUser({ pref_map_type: res.data.pref_map_type });
    } catch {
      setMapTypeError("Could not save. Please try again.");
      setMapType(user?.pref_map_type ?? "roadmap");
    } finally {
      setMapTypeSaving(false);
    }
  }

  async function saveMapControls(value) {
    setMapControls(value);
    setMapControlsSaving(true);
    setMapControlsError(null);
    try {
      const token = localStorage.getItem("token");
      const res = await api.patch("/users/me", { pref_map_controls: value }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      updateUser({ pref_map_controls: res.data.pref_map_controls });
    } catch {
      setMapControlsError("Could not save. Please try again.");
      setMapControls(user?.pref_map_controls ?? false);
    } finally {
      setMapControlsSaving(false);
    }
  }

  async function handleDeleteAccount() {
    setDeleting(true);
    setDeleteError(null);
    try {
      const token = localStorage.getItem("token");
      await api.delete("/users/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
      logout();
      navigate("/");
    } catch {
      setDeleteError("Could not delete account. Please try again.");
      setDeleting(false);
    }
  }

  const cardStyle = {
    background: "var(--color-surface)",
    border: "2.5px solid var(--color-card-border)",
    borderRadius: "20px",
    padding: "28px 24px",
    boxShadow: "4px 4px 0 var(--color-accent-dim)",
    display: "flex",
    flexDirection: "column",
    gap: "22px",
  };

  return (
    <div className="page-container">
      <div className="content-inner account-inner">
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

      {tab === "profile" && (
        <div style={{ marginTop: "18px", textAlign: "center" }}>
          <Link to="/privacy" style={{ fontSize: "0.82em", color: "var(--color-subtext)" }}>
            Privacy Policy
          </Link>
        </div>
      )}

      {tab === "profile" && (
        <div style={{ ...cardStyle, marginTop: "18px", border: "2.5px solid #FF5A3C40" }}>
          <span style={{
            fontSize: "0.72em", fontWeight: 800, textTransform: "uppercase",
            letterSpacing: "0.06em", color: "#FF5A3C",
          }}>
            <FontAwesomeIcon icon={faTrash} style={{ marginRight: "5px" }} />Danger Zone
          </span>

          {!confirmingDelete ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", alignItems: "flex-start" }}>
              <p style={{ margin: 0, fontSize: "0.84em", color: "var(--color-subtext)", fontWeight: 500 }}>
                Permanently delete your account and all your saved routes and spots. This can't be undone.
              </p>
              <button
                onClick={() => setConfirmingDelete(true)}
                style={{ background: "none", border: "2px solid #FF5A3C", color: "#FF5A3C", boxShadow: "none", fontSize: "0.85em", fontWeight: 700 }}
              >
                Delete my account
              </button>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px", alignItems: "flex-start" }}>
              <p style={{ margin: 0, fontSize: "0.84em", color: "var(--color-text)", fontWeight: 700 }}>
                Are you sure? All your data will be permanently deleted.
              </p>
              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  onClick={handleDeleteAccount}
                  disabled={deleting}
                  style={{ background: "#FF5A3C", border: "none", color: "#fff", fontSize: "0.85em", fontWeight: 700 }}
                >
                  {deleting ? "Deleting…" : "Yes, delete everything"}
                </button>
                <button
                  onClick={() => setConfirmingDelete(false)}
                  disabled={deleting}
                  className="btn-outline"
                  style={{ fontSize: "0.85em", fontWeight: 700 }}
                >
                  Cancel
                </button>
              </div>
              {deleteError && (
                <p style={{ margin: 0, fontSize: "0.82em", color: "#FF5A3C", fontWeight: 700 }}>{deleteError}</p>
              )}
            </div>
          )}
        </div>
      )}

      {tab === "preferences" && (
        <div className="preferences-card" style={cardStyle}>
          {/* Sun/Shade Preference — collapsible */}
          <div>
            <button
              onClick={() => setModeOpen((o) => !o)}
              style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", background: "none", border: "none", boxShadow: "none", padding: 0, cursor: "pointer" }}
            >
              <span style={{ fontSize: "0.72em", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--color-subtext)" }}>
                <FontAwesomeIcon icon={faSun} style={{ marginRight: "5px" }} />Sun/Shade Preference
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontSize: "0.82em", fontWeight: 700, color: "var(--color-accent)", textTransform: "capitalize" }}>{mode}</span>
                <FontAwesomeIcon icon={faChevronDown} style={{ fontSize: "0.7em", color: "var(--color-subtext)", transform: modeOpen ? "rotate(180deg)" : "none", transition: "transform 0.2s" }} />
              </span>
            </button>
            {modeOpen && (
              <div style={{ marginTop: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
                <p style={{ margin: 0, fontSize: "0.84em", color: "var(--color-subtext)", fontWeight: 500 }}>
                  Whether routes and place searches default to sun or shade.
                </p>
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
                  <p style={{ margin: 0, fontSize: "0.82em", color: "var(--color-subtext)", fontWeight: 600 }}>Saving…</p>
                )}
                {modeError && (
                  <p style={{ margin: 0, fontSize: "0.82em", color: "#FF5A3C", fontWeight: 700 }}>{modeError}</p>
                )}
              </div>
            )}
          </div>

          <hr style={{ border: "none", borderTop: "2px solid var(--color-border, #e0e0e0)", margin: "0" }} />

          {/* Max Detour — collapsible */}
          <div>
            <button
              onClick={() => setDetourOpen((o) => !o)}
              style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", background: "none", border: "none", boxShadow: "none", padding: 0, cursor: "pointer" }}
            >
              <span style={{ fontSize: "0.72em", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--color-subtext)" }}>
                <FontAwesomeIcon icon={faSlidersH} style={{ marginRight: "5px" }} />Max Detour
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontSize: "0.82em", fontWeight: 700, color: "var(--color-accent)" }}>{detour}%</span>
                <FontAwesomeIcon icon={faChevronDown} style={{ fontSize: "0.7em", color: "var(--color-subtext)", transform: detourOpen ? "rotate(180deg)" : "none", transition: "transform 0.2s" }} />
              </span>
            </button>
            {detourOpen && (
              <div style={{ marginTop: "16px" }}>
                <p style={{ margin: "0 0 12px", fontSize: "0.84em", color: "var(--color-subtext)", fontWeight: 500 }}>
                  How much longer than the shortest route you're willing to walk to maximise sun or shade.
                </p>
                <DetourSlider
                  value={detour}
                  onChange={saveDetour}
                  saving={detourSaving}
                  error={detourError}
                />
              </div>
            )}
          </div>

          <hr style={{ border: "none", borderTop: "2px solid var(--color-border, #e0e0e0)", margin: "0" }} />

          {/* Map View — collapsible */}
          <div>
            <button
              onClick={() => setMapControlsOpen((o) => !o)}
              style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", background: "none", border: "none", boxShadow: "none", padding: 0, cursor: "pointer" }}
            >
              <span style={{ fontSize: "0.72em", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--color-subtext)" }}>
                <FontAwesomeIcon icon={faMap} style={{ marginRight: "5px" }} />Map View
              </span>
              <FontAwesomeIcon icon={faChevronDown} style={{ fontSize: "0.7em", color: "var(--color-subtext)", transform: mapControlsOpen ? "rotate(180deg)" : "none", transition: "transform 0.2s" }} />
            </button>
            {mapControlsOpen && (
              <div style={{ marginTop: "16px", display: "flex", flexDirection: "column", gap: "10px" }}>
                {/* Accessible Navigation sub-preference */}
                <div style={{ display: "flex", flexDirection: "column", gap: "8px", padding: "12px", background: "var(--color-bg, #f8f8f8)", borderRadius: "12px" }}>
                  <div>
                    <span style={{ fontSize: "0.72em", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--color-subtext)" }}>
                      Accessible Navigation
                    </span>
                    <p style={{ margin: "3px 0 0", fontSize: "0.82em", color: "var(--color-subtext)", fontWeight: 500 }}>
                      Show zoom and directional arrow buttons on the map.
                    </p>
                  </div>
                  <div style={{ display: "flex", gap: "8px" }}>
                    {[
                      { value: false, label: "Off" },
                      { value: true, label: "On" },
                    ].map(({ value, label }) => (
                      <button
                        key={label}
                        onClick={() => !mapControlsSaving && saveMapControls(value)}
                        disabled={mapControlsSaving}
                        style={{
                          flex: 1,
                          padding: "9px 0",
                          fontWeight: 700,
                          fontSize: "0.88em",
                          borderRadius: "10px",
                          background: mapControls === value ? "var(--color-accent)" : "var(--color-surface)",
                          color: mapControls === value ? "#fff" : "var(--color-subtext)",
                          border: mapControls === value ? "none" : "2px solid var(--color-border, #e0e0e0)",
                          boxShadow: mapControls === value ? "2px 2px 0 var(--color-accent-dim)" : "none",
                          cursor: mapControlsSaving ? "not-allowed" : "pointer",
                        }}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  {mapControlsSaving && (
                    <p style={{ margin: 0, fontSize: "0.82em", color: "var(--color-subtext)", fontWeight: 600 }}>Saving…</p>
                  )}
                  {mapControlsError && (
                    <p style={{ margin: 0, fontSize: "0.82em", color: "#FF5A3C", fontWeight: 700 }}>{mapControlsError}</p>
                  )}
                </div>

                {/* Map Type sub-preference */}
                <div style={{ display: "flex", flexDirection: "column", gap: "8px", padding: "12px", background: "var(--color-bg, #f8f8f8)", borderRadius: "12px" }}>
                  <div>
                    <span style={{ fontSize: "0.72em", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--color-subtext)" }}>
                      Map Style
                    </span>
                    <p style={{ margin: "3px 0 0", fontSize: "0.82em", color: "var(--color-subtext)", fontWeight: 500 }}>
                      Choose how the map is rendered.
                    </p>
                  </div>
                  <div style={{ display: "flex", gap: "8px" }}>
                    {[
                      { value: "roadmap",  label: "Standard"  },
                      { value: "satellite", label: "Satellite" },
                      { value: "terrain",  label: "Terrain"   },
                    ].map(({ value, label }) => (
                      <button
                        key={value}
                        onClick={() => !mapTypeSaving && saveMapType(value)}
                        disabled={mapTypeSaving}
                        style={{
                          flex: 1,
                          display: "flex",
                          flexDirection: "column",
                          alignItems: "stretch",
                          gap: "5px",
                          padding: "6px",
                          fontWeight: 700,
                          fontSize: "0.78em",
                          borderRadius: "10px",
                          background: mapType === value ? "var(--color-accent)" : "var(--color-surface)",
                          color: mapType === value ? "#fff" : "var(--color-subtext)",
                          border: mapType === value ? "none" : "2px solid var(--color-border, #e0e0e0)",
                          boxShadow: mapType === value ? "2px 2px 0 var(--color-accent-dim)" : "none",
                          cursor: mapTypeSaving ? "not-allowed" : "pointer",
                        }}
                      >
                        <div style={{ width: "100%", height: "50px", borderRadius: "6px", overflow: "hidden", position: "relative", background: MAP_PREVIEW_FALLBACK[value] }}>
                          <img
                            src={MAP_PREVIEW_URL(value)}
                            alt={label}
                            onError={(e) => { e.target.style.display = "none"; }}
                            style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                          />
                        </div>
                        <span style={{ textAlign: "center", paddingTop: "2px" }}>{label}</span>
                      </button>
                    ))}
                  </div>
                  {mapTypeSaving && (
                    <p style={{ margin: 0, fontSize: "0.82em", color: "var(--color-subtext)", fontWeight: 600 }}>Saving…</p>
                  )}
                  {mapTypeError && (
                    <p style={{ margin: 0, fontSize: "0.82em", color: "#FF5A3C", fontWeight: 700 }}>{mapTypeError}</p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      </div>
    </div>
  );
}

import { useEffect, useState, useRef } from "react";
import { Geolocation } from "@capacitor/geolocation";
import { useLoadScript, Autocomplete } from "@react-google-maps/api";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faHouse, faBriefcase, faDumbbell, faMugHot, faGraduationCap, faStar,
  faMapPin, faUtensils, faShoppingCart, faHeart, faBicycle, faMusic,
  faTree, faPlane, faTrain, faBus, faBed, faCamera, faBook, faSun,
  faPlus, faTrash, faPen, faCheck, faXmark, faLocationCrosshairs,
} from "@fortawesome/free-solid-svg-icons";
import api from "../api";

const MAP_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
const LIBRARIES = ["places"];

export const SPOT_ICONS = [
  { key: "faHouse",         icon: faHouse,         label: "Home" },
  { key: "faBriefcase",     icon: faBriefcase,     label: "Work" },
  { key: "faDumbbell",      icon: faDumbbell,      label: "Gym" },
  { key: "faMugHot",        icon: faMugHot,        label: "Café" },
  { key: "faUtensils",      icon: faUtensils,      label: "Restaurant" },
  { key: "faGraduationCap", icon: faGraduationCap, label: "School" },
  { key: "faShoppingCart",  icon: faShoppingCart,  label: "Shop" },
  { key: "faHeart",         icon: faHeart,         label: "Favourite" },
  { key: "faStar",          icon: faStar,          label: "Favourite" },
  { key: "faMapPin",        icon: faMapPin,        label: "Place" },
  { key: "faBicycle",       icon: faBicycle,       label: "Bike" },
  { key: "faMusic",         icon: faMusic,         label: "Music" },
  { key: "faTree",          icon: faTree,          label: "Park" },
  { key: "faPlane",         icon: faPlane,         label: "Airport" },
  { key: "faTrain",         icon: faTrain,         label: "Station" },
  { key: "faBus",           icon: faBus,           label: "Bus stop" },
  { key: "faBed",           icon: faBed,           label: "Hotel" },
  { key: "faCamera",        icon: faCamera,        label: "Sightseeing" },
  { key: "faBook",          icon: faBook,          label: "Library" },
  { key: "faSun",           icon: faSun,           label: "Other" },
];

export function spotIcon(key) {
  return SPOT_ICONS.find((s) => s.key === key)?.icon ?? faMapPin;
}

const BLANK_FORM = { name: "", address: "", lat: null, lng: null, icon: "faHouse" };
const DEFAULT_CENTER = { lat: 51.505, lng: -0.09 };

export default function MySpotsPage() {
  const { isLoaded } = useLoadScript({ googleMapsApiKey: MAP_KEY, libraries: LIBRARIES });

  const [spots, setSpots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(BLANK_FORM);
  const [editingId, setEditingId] = useState(null);
  const [saveError, setSaveError] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [locating, setLocating] = useState(false);

  const mapContainerRef = useRef(null);
  const formMapRef = useRef(null);
  const formMarkerRef = useRef(null);
  const autocompleteRef = useRef(null);
  const formRef = useRef(form);
  formRef.current = form;

  useEffect(() => { fetchSpots(); }, []);

  // Init mini-map when form opens
  useEffect(() => {
    if (!showForm || !isLoaded) return;
    requestAnimationFrame(() => {
      if (!mapContainerRef.current || formMapRef.current) return;
      const center = formRef.current.lat && formRef.current.lng
        ? { lat: formRef.current.lat, lng: formRef.current.lng }
        : DEFAULT_CENTER;
      formMapRef.current = new window.google.maps.Map(mapContainerRef.current, {
        center,
        zoom: 15,
        disableDefaultUI: true,
        zoomControl: true,
      });
      if (formRef.current.lat && formRef.current.lng) {
        formMarkerRef.current = new window.google.maps.Marker({
          position: center,
          map: formMapRef.current,
        });
      }
      formMapRef.current.addListener("click", async (e) => {
        const lat = e.latLng.lat();
        const lng = e.latLng.lng();
        const address = await reverseGeocode(lat, lng);
        setForm((prev) => ({ ...prev, lat, lng, address: address || prev.address }));
        placeMarker({ lat, lng });
      });
    });
    return () => {
      formMapRef.current = null;
      formMarkerRef.current = null;
    };
  }, [showForm, isLoaded]);

  // Update marker when lat/lng changes
  useEffect(() => {
    if (!formMapRef.current || !form.lat || !form.lng) return;
    const pos = { lat: form.lat, lng: form.lng };
    placeMarker(pos);
    formMapRef.current.panTo(pos);
  }, [form.lat, form.lng]);

  function placeMarker(pos) {
    if (!formMapRef.current) return;
    if (formMarkerRef.current) {
      formMarkerRef.current.setPosition(pos);
    } else {
      formMarkerRef.current = new window.google.maps.Marker({
        position: pos,
        map: formMapRef.current,
      });
    }
  }

  async function reverseGeocode(lat, lng) {
    try {
      const geocoder = new window.google.maps.Geocoder();
      const result = await geocoder.geocode({ location: { lat, lng } });
      return result.results[0]?.formatted_address || null;
    } catch { return null; }
  }

  async function useCurrentLocation() {
    setLocating(true);
    try {
      let lat, lng;
      try {
        await Geolocation.requestPermissions();
        const pos = await Geolocation.getCurrentPosition({ enableHighAccuracy: true });
        lat = pos.coords.latitude;
        lng = pos.coords.longitude;
      } catch {
        const pos = await new Promise((resolve, reject) =>
          navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true })
        );
        lat = pos.coords.latitude;
        lng = pos.coords.longitude;
      }
      const address = await reverseGeocode(lat, lng);
      setForm((prev) => ({ ...prev, lat, lng, address: address || "" }));
    } catch {
      setSaveError("Could not get your location.");
    } finally {
      setLocating(false);
    }
  }

  function onPlaceChanged() {
    const place = autocompleteRef.current?.getPlace();
    if (!place?.geometry) return;
    const lat = place.geometry.location.lat();
    const lng = place.geometry.location.lng();
    const address = place.formatted_address || place.name || "";
    setForm((prev) => ({ ...prev, lat, lng, address }));
  }

  async function fetchSpots() {
    try {
      const token = localStorage.getItem("token");
      const res = await api.get("/spots", { headers: { Authorization: `Bearer ${token}` } });
      setSpots(res.data);
    } catch {
      setError("Could not load spots.");
    } finally {
      setLoading(false);
    }
  }

  function openAdd() {
    setEditingId(null);
    setForm(BLANK_FORM);
    setSaveError(null);
    setShowForm(true);
  }

  function openEdit(spot) {
    setEditingId(spot.id);
    setForm({ name: spot.name, address: spot.address, lat: spot.lat, lng: spot.lng, icon: spot.icon });
    setSaveError(null);
    setShowForm(true);
  }

  function closeForm() {
    setShowForm(false);
    formMapRef.current = null;
    formMarkerRef.current = null;
  }

  async function saveSpot() {
    if (!form.name.trim()) { setSaveError("Name is required."); return; }
    if (!form.lat || !form.lng) { setSaveError("Please pick a location on the map or search an address."); return; }
    setSaveError(null);
    try {
      const token = localStorage.getItem("token");
      const payload = { name: form.name.trim(), address: form.address, lat: form.lat, lng: form.lng, icon: form.icon };
      if (editingId) {
        const res = await api.patch(`/spots/${editingId}`, payload, { headers: { Authorization: `Bearer ${token}` } });
        setSpots((prev) => prev.map((s) => s.id === editingId ? res.data : s));
      } else {
        const res = await api.post("/spots", payload, { headers: { Authorization: `Bearer ${token}` } });
        setSpots((prev) => [...prev, res.data]);
      }
      closeForm();
    } catch {
      setSaveError("Could not save spot.");
    }
  }

  async function deleteSpot(id) {
    try {
      const token = localStorage.getItem("token");
      await api.delete(`/spots/${id}`, { headers: { Authorization: `Bearer ${token}` } });
      setSpots((prev) => prev.filter((s) => s.id !== id));
      setPendingDelete(null);
    } catch {
      setError("Could not delete spot.");
      setPendingDelete(null);
    }
  }

  return (
    <div className="page-container" style={{ maxWidth: "600px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
        <h2 style={{ margin: 0 }}>My Spots <FontAwesomeIcon icon={faMapPin} style={{ color: "#FFD600", fontSize: "0.85em" }} /></h2>
        <button onClick={openAdd} style={{ fontSize: "0.82em", padding: "0.4em 1em", display: "flex", alignItems: "center", gap: "6px" }}>
          <FontAwesomeIcon icon={faPlus} /> Add spot
        </button>
      </div>

      {error && <p style={{ color: "#C0392B", fontSize: "0.88em" }}>{error}</p>}
      {loading && <p style={{ color: "#A87500", fontSize: "0.92em" }}>Loading spots...</p>}
      {!loading && spots.length === 0 && !error && (
        <p style={{ color: "#A87500", fontSize: "0.92em" }}>No spots saved yet. Add your first one!</p>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {spots.map((spot) => (
          <div key={spot.id} style={{
            border: "2.5px solid #ffffff", borderRadius: "14px",
            padding: "12px 16px", background: "#FFFDF5",
            boxShadow: "4px 4px 0 #E8C000",
            display: "flex", alignItems: "center", gap: "14px",
          }}>
            <div style={{
              width: "38px", height: "38px", borderRadius: "50%",
              background: "#FFD600", display: "flex", alignItems: "center",
              justifyContent: "center", flexShrink: 0,
            }}>
              <FontAwesomeIcon icon={spotIcon(spot.icon)} style={{ color: "#3D2C00", fontSize: "16px" }} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <strong style={{ color: "#3D2C00", fontSize: "0.95em" }}>{spot.name}</strong>
              <p style={{ margin: "2px 0 0", fontSize: "0.78em", color: "#A87500", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {spot.address}
              </p>
            </div>
            <div style={{ display: "flex", gap: "6px", flexShrink: 0 }}>
              <button onClick={() => openEdit(spot)} style={{ background: "none", border: "none", cursor: "pointer", color: "#C8A84B", fontSize: "16px", padding: "2px 4px", boxShadow: "none" }}>
                <FontAwesomeIcon icon={faPen} />
              </button>
              <button onClick={() => setPendingDelete(spot)} style={{ background: "none", border: "none", cursor: "pointer", color: "#C8A84B", fontSize: "16px", padding: "2px 4px", boxShadow: "none" }}>
                <FontAwesomeIcon icon={faTrash} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Add / Edit modal */}
      {showForm && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(61,44,0,0.25)",
          backdropFilter: "blur(2px)", display: "flex", alignItems: "flex-start",
          justifyContent: "center", zIndex: 1000, overflowY: "auto", padding: "20px 0",
        }}>
          <div style={{
            background: "#FFFDF5", border: "2.5px solid #ffffff",
            borderRadius: "24px", padding: "24px", maxWidth: "400px",
            width: "90%", boxShadow: "6px 6px 0 #E8C000",
            display: "flex", flexDirection: "column", gap: "14px",
            margin: "auto",
          }}>
            <h3 style={{ margin: 0, fontSize: "1.05em" }}>{editingId ? "Edit spot" : "Add spot"}</h3>

            <input
              type="text" placeholder="Name (e.g. Home) *"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />

            {/* Address with autocomplete + inline location button */}
            <div style={{ position: "relative" }}>
              {isLoaded ? (
                <Autocomplete
                  onLoad={(a) => { autocompleteRef.current = a; }}
                  onPlaceChanged={onPlaceChanged}
                >
                  <input
                    type="text"
                    placeholder="Search address *"
                    value={form.address}
                    onChange={(e) => setForm({ ...form, address: e.target.value, lat: null, lng: null })}
                    style={{ paddingRight: "130px", width: "100%", boxSizing: "border-box" }}
                  />
                </Autocomplete>
              ) : (
                <input type="text" placeholder="Search address *" disabled value="" style={{ width: "100%", boxSizing: "border-box" }} />
              )}
              <button
                onClick={useCurrentLocation}
                disabled={locating}
                style={{
                  position: "absolute", right: "6px", top: "50%", transform: "translateY(-50%)",
                  fontSize: "10px", padding: "2px 7px", display: "flex", alignItems: "center",
                  gap: "4px", background: "rgba(255,193,7,0.15)", border: "1.5px solid #FFD600",
                  color: "#A87500", fontWeight: 700, whiteSpace: "nowrap", boxShadow: "none",
                }}
              >
                <FontAwesomeIcon icon={faLocationCrosshairs} />
                {locating ? "Locating…" : "Use my location"}
              </button>
            </div>

            {/* Mini map */}
            <div style={{ borderRadius: "12px", overflow: "hidden", border: "2px solid #E8C000", height: "200px" }}>
              <div ref={mapContainerRef} style={{ height: "100%", width: "100%" }} />
            </div>
            {!form.lat && (
              <p style={{ margin: "-8px 0 0", fontSize: "0.75em", color: "#A87500" }}>
                Search an address, use your location, or tap the map to set a spot.
              </p>
            )}

            {/* Icon picker */}
            <div>
              <p style={{ margin: "0 0 8px", fontSize: "0.82em", color: "#7B5800", fontWeight: 600 }}>Icon</p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {SPOT_ICONS.map(({ key, icon }) => (
                  <button
                    key={key}
                    onClick={() => setForm({ ...form, icon: key })}
                    style={{
                      width: "36px", height: "36px", borderRadius: "50%",
                      border: form.icon === key ? "2.5px solid #3D2C00" : "2px solid #E8C000",
                      background: form.icon === key ? "#FFD600" : "#FFF8DC",
                      cursor: "pointer", display: "flex", alignItems: "center",
                      justifyContent: "center", padding: 0, boxShadow: "none",
                    }}
                  >
                    <FontAwesomeIcon icon={icon} style={{ color: "#3D2C00", fontSize: "14px" }} />
                  </button>
                ))}
              </div>
            </div>

            {saveError && <p style={{ margin: 0, color: "#C0392B", fontSize: "0.82em", fontWeight: 700 }}>{saveError}</p>}

            <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
              <button className="btn-outline" onClick={closeForm}>
                <FontAwesomeIcon icon={faXmark} /> Cancel
              </button>
              <button onClick={saveSpot}>
                <FontAwesomeIcon icon={faCheck} /> Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirm */}
      {pendingDelete && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(61,44,0,0.25)",
          backdropFilter: "blur(2px)", display: "flex", alignItems: "center",
          justifyContent: "center", zIndex: 1000,
        }}>
          <div style={{
            background: "#FFFDF5", border: "2.5px solid #ffffff",
            borderRadius: "24px", padding: "32px", maxWidth: "340px",
            width: "90%", boxShadow: "6px 6px 0 #E8C000",
            display: "flex", flexDirection: "column", gap: "12px",
          }}>
            <h3 style={{ margin: 0, fontSize: "1.1em" }}>Delete spot?</h3>
            <p style={{ margin: 0, color: "#7B5800", fontSize: "0.9em" }}>
              <strong>{pendingDelete.name}</strong> will be permanently deleted.
            </p>
            <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end", marginTop: "4px" }}>
              <button className="btn-outline" onClick={() => setPendingDelete(null)}>Cancel</button>
              <button className="btn-danger" onClick={() => deleteSpot(pendingDelete.id)}>Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

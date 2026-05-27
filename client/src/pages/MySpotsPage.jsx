import { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Geolocation } from "@capacitor/geolocation";
import { Share } from "@capacitor/share";
import { useLoadScript, Autocomplete } from "@react-google-maps/api";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faHouse, faBriefcase, faDumbbell, faMugHot, faMugSaucer, faGraduationCap, faStar,
  faMapPin, faUtensils, faShoppingCart, faHeart, faBicycle, faMusic,
  faTree, faPlane, faTrain, faBus, faBed, faCamera, faBook, faSun,
  faPlus, faTrash, faPen, faCheck, faXmark, faLocationCrosshairs, faShareNodes,
  faBeerMugEmpty, faWineGlass, faMartiniGlassCitrus, faGlassWhiskey, faChampagneGlasses,
  faPizzaSlice, faBurger, faIceCream, faCookieBite, faBreadSlice,
  faDrumstickBite, faFish, faBowlFood, faLeaf, faCarrot, faLemon, faCakeCandles, faEgg,
} from "@fortawesome/free-solid-svg-icons";
import api from "../api";

const MAP_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
const LIBRARIES = ["places"];

export const SPOT_ICONS = [
  // Food & drink
  { key: "faMugHot",             icon: faMugHot,             label: "Café" },
  { key: "faMugSaucer",          icon: faMugSaucer,          label: "Coffee" },
  { key: "faUtensils",           icon: faUtensils,           label: "Restaurant" },
  { key: "faPizzaSlice",         icon: faPizzaSlice,         label: "Pizza" },
  { key: "faBurger",             icon: faBurger,             label: "Burger" },
  { key: "faDrumstickBite",      icon: faDrumstickBite,      label: "Chicken" },
  { key: "faFish",               icon: faFish,               label: "Seafood" },
  { key: "faBowlFood",           icon: faBowlFood,           label: "Bowl" },
  { key: "faBreadSlice",         icon: faBreadSlice,         label: "Bakery" },
  { key: "faCookieBite",         icon: faCookieBite,         label: "Bakery" },
  { key: "faCakeCandles",        icon: faCakeCandles,        label: "Cake" },
  { key: "faIceCream",           icon: faIceCream,           label: "Ice cream" },
  { key: "faEgg",                icon: faEgg,                label: "Brunch" },
  { key: "faCarrot",             icon: faCarrot,             label: "Vegan" },
  { key: "faLeaf",               icon: faLeaf,               label: "Healthy" },
  { key: "faLemon",              icon: faLemon,              label: "Juice" },
  // Drinks
  { key: "faBeerMugEmpty",       icon: faBeerMugEmpty,       label: "Pub" },
  { key: "faWineGlass",          icon: faWineGlass,          label: "Wine bar" },
  { key: "faMartiniGlassCitrus", icon: faMartiniGlassCitrus, label: "Cocktails" },
  { key: "faGlassWhiskey",       icon: faGlassWhiskey,       label: "Bar" },
  { key: "faChampagneGlasses",   icon: faChampagneGlasses,   label: "Celebrate" },
  // Places & lifestyle
  { key: "faHouse",         icon: faHouse,         label: "Home" },
  { key: "faBriefcase",     icon: faBriefcase,     label: "Work" },
  { key: "faDumbbell",      icon: faDumbbell,      label: "Gym" },
  { key: "faGraduationCap", icon: faGraduationCap, label: "School" },
  { key: "faShoppingCart",  icon: faShoppingCart,  label: "Shop" },
  { key: "faHeart",         icon: faHeart,         label: "Favourite" },
  { key: "faStar",          icon: faStar,          label: "Star" },
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

const BLANK_FORM = { name: "", address: "", lat: null, lng: null, icon: "faHouse", description: "", city: "" };

function extractCity(components) {
  if (!components) return "";
  for (const type of ["locality", "postal_town", "administrative_area_level_2", "administrative_area_level_1"]) {
    const comp = components.find((c) => c.types.includes(type));
    if (comp) return comp.long_name;
  }
  return "";
}

const ICON_GROUPS = [
  { key: "coffee", label: "Coffee", icons: new Set(["faMugHot","faMugSaucer"]) },
  { key: "food", label: "Food", icons: new Set(["faUtensils","faPizzaSlice","faBurger","faDrumstickBite","faFish","faBowlFood","faBreadSlice","faCookieBite","faCakeCandles","faIceCream","faEgg","faCarrot","faLeaf","faLemon"]) },
  { key: "drinks", label: "Drinks", icons: new Set(["faBeerMugEmpty","faWineGlass","faMartiniGlassCitrus","faGlassWhiskey","faChampagneGlasses"]) },
];
const DEFAULT_CENTER = { lat: 51.505, lng: -0.09 };

export default function MySpotsPage() {
  const { isLoaded } = useLoadScript({ googleMapsApiKey: MAP_KEY, libraries: LIBRARIES });
  const navigate = useNavigate();

  const [spots, setSpots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedSpotId, setExpandedSpotId] = useState(null);
  const [filterCity, setFilterCity] = useState(null);
  const [filterGroup, setFilterGroup] = useState(null);
  const [showCityModal, setShowCityModal] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(BLANK_FORM);
  const [editingId, setEditingId] = useState(null);
  const [saveError, setSaveError] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [locating, setLocating] = useState(false);

  const mapContainerRef = useRef(null);
  const formMapRef = useRef(null);
  const formMarkerRef = useRef(null);
  const locationDotRef = useRef(null);
  const autocompleteRef = useRef(null);
  const formRef = useRef(form);
  formRef.current = form;

  const previewMapContainerRef = useRef(null);
  const previewMapRef = useRef(null);
  const previewMarkerRef = useRef(null);

  useEffect(() => { fetchSpots(); }, []);

  // Init mini-map when form opens
  useEffect(() => {
    if (!showForm || !isLoaded) return;
    requestAnimationFrame(async () => {
      if (!mapContainerRef.current || formMapRef.current) return;
      const hasSpotPos = formRef.current.lat && formRef.current.lng;
      const center = hasSpotPos
        ? { lat: formRef.current.lat, lng: formRef.current.lng }
        : DEFAULT_CENTER;
      formMapRef.current = new window.google.maps.Map(mapContainerRef.current, {
        center,
        zoom: 15,
        disableDefaultUI: true,
        zoomControl: true,
      });
      if (hasSpotPos) {
        placeMarker(center);
      }
      formMapRef.current.addListener("click", async (e) => {
        const lat = e.latLng.lat();
        const lng = e.latLng.lng();
        const { address, city } = await reverseGeocode(lat, lng);
        setForm((prev) => ({ ...prev, lat, lng, address: address || prev.address, city: city || prev.city }));
        placeMarker({ lat, lng });
      });

      // Show current location dot and pan to it if no spot position yet
      const locationDotSvg = encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 22 22">' +
          '<circle cx="11" cy="11" r="11" fill="rgba(255,214,0,0.25)"/>' +
          '<circle cx="11" cy="11" r="6" fill="#FFD600" stroke="white" stroke-width="2"/>' +
        '</svg>'
      );
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
        if (!formMapRef.current) return;
        locationDotRef.current = new window.google.maps.Marker({
          position: { lat, lng },
          map: formMapRef.current,
          icon: {
            url: `data:image/svg+xml;charset=UTF-8,${locationDotSvg}`,
            scaledSize: new window.google.maps.Size(22, 22),
            anchor: new window.google.maps.Point(11, 11),
          },
          zIndex: 1,
          title: "Your location",
        });
        if (!hasSpotPos) {
          formMapRef.current.panTo({ lat, lng });
        }
        const bias = new window.google.maps.LatLngBounds(
          { lat: lat - 0.15, lng: lng - 0.15 },
          { lat: lat + 0.15, lng: lng + 0.15 },
        );
        autocompleteRef.current?.setBounds(bias);
      } catch { /* geolocation unavailable */ }
    });
    return () => {
      formMapRef.current = null;
      formMarkerRef.current = null;
      locationDotRef.current = null;
    };
  }, [showForm, isLoaded]);

  // Update marker when lat/lng changes
  useEffect(() => {
    if (!formMapRef.current || !form.lat || !form.lng) return;
    const pos = { lat: form.lat, lng: form.lng };
    placeMarker(pos);
    formMapRef.current.panTo(pos);
  }, [form.lat, form.lng]);

  // Init read-only preview mini-map when a spot is expanded
  useEffect(() => {
    if (!expandedSpotId || !isLoaded) {
      previewMapRef.current = null;
      previewMarkerRef.current = null;
      return;
    }
    const spot = spots.find((s) => s.id === expandedSpotId);
    if (!spot?.lat || !spot?.lng) return;
    requestAnimationFrame(() => {
      if (!previewMapContainerRef.current) return;
      const pos = { lat: spot.lat, lng: spot.lng };
      previewMapRef.current = new window.google.maps.Map(previewMapContainerRef.current, {
        center: pos,
        zoom: 15,
        disableDefaultUI: true,
        gestureHandling: "none",
        clickableIcons: false,
      });
      const pin = {
        url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(
          '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="36" viewBox="0 0 24 36">' +
            '<path fill="#FFD600" stroke="#fff" stroke-width="1.5" d="M12 0C5.4 0 0 5.4 0 12c0 9 12 24 12 24S24 21 24 12C24 5.4 18.6 0 12 0z"/>' +
            '<circle cx="12" cy="12" r="5" fill="white"/>' +
          '</svg>'
        )}`,
        scaledSize: new window.google.maps.Size(24, 36),
        anchor: new window.google.maps.Point(12, 36),
      };
      previewMarkerRef.current = new window.google.maps.Marker({
        position: pos,
        map: previewMapRef.current,
        icon: pin,
        zIndex: 2,
      });
    });
    return () => {
      previewMapRef.current = null;
      previewMarkerRef.current = null;
    };
  }, [expandedSpotId, isLoaded]); // eslint-disable-line react-hooks/exhaustive-deps

  function placeMarker(pos) {
    if (!formMapRef.current) return;
    const sunnyPin = {
      url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="36" viewBox="0 0 24 36">' +
          '<path fill="#FFD600" stroke="#fff" stroke-width="1.5" d="M12 0C5.4 0 0 5.4 0 12c0 9 12 24 12 24S24 21 24 12C24 5.4 18.6 0 12 0z"/>' +
          '<circle cx="12" cy="12" r="5" fill="white"/>' +
        '</svg>'
      )}`,
      scaledSize: new window.google.maps.Size(24, 36),
      anchor: new window.google.maps.Point(12, 36),
    };
    if (formMarkerRef.current) {
      formMarkerRef.current.setPosition(pos);
    } else {
      formMarkerRef.current = new window.google.maps.Marker({
        position: pos,
        map: formMapRef.current,
        icon: sunnyPin,
        zIndex: 2,
      });
    }
  }

  async function reverseGeocode(lat, lng) {
    try {
      const geocoder = new window.google.maps.Geocoder();
      const result = await geocoder.geocode({ location: { lat, lng } });
      const first = result.results[0];
      return {
        address: first?.formatted_address || null,
        city: extractCity(first?.address_components || []),
      };
    } catch { return { address: null, city: "" }; }
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
      const { address, city } = await reverseGeocode(lat, lng);
      setForm((prev) => ({ ...prev, lat, lng, address: address || "", city: city || prev.city }));
      const bias = new window.google.maps.LatLngBounds(
        { lat: lat - 0.15, lng: lng - 0.15 },
        { lat: lat + 0.15, lng: lng + 0.15 },
      );
      autocompleteRef.current?.setBounds(bias);
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
    const city = extractCity(place.address_components || []);
    setForm((prev) => ({ ...prev, lat, lng, address, city }));
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
    setForm({ name: spot.name, address: spot.address, lat: spot.lat, lng: spot.lng, icon: spot.icon, city: spot.city || "", description: spot.description || "" });
    setSaveError(null);
    setShowForm(true);
  }

  function closeForm() {
    setShowForm(false);
    formMapRef.current = null;
    formMarkerRef.current = null;
    locationDotRef.current = null;
  }

  async function saveSpot() {
    if (!form.name.trim()) { setSaveError("Name is required."); return; }
    if (!form.lat || !form.lng) { setSaveError("Please pick a location on the map or search an address."); return; }
    setSaveError(null);
    try {
      const token = localStorage.getItem("token");
      const payload = { name: form.name.trim(), address: form.address, lat: form.lat, lng: form.lng, icon: form.icon, city: form.city, description: form.description.trim() || null };
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

  async function shareSpot(spot) {
    const url = `https://maps.google.com/?q=${spot.lat},${spot.lng}`;
    const canShare = (await Share.canShare()).value;
    if (canShare) {
      await Share.share({ title: spot.name, text: `Check out ${spot.name}!`, url, dialogTitle: "Share spot" });
    } else {
      await navigator.clipboard.writeText(`${spot.name} — ${url}`);
    }
  }

  return (
    <div className="page-container" style={{ maxWidth: "600px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
        <h2 style={{ margin: 0 }}>Spots <FontAwesomeIcon icon={faMapPin} style={{ color: "#FFD600", fontSize: "0.85em" }} /></h2>
        <button onClick={openAdd} style={{ fontSize: "0.82em", padding: "0.4em 1em", display: "flex", alignItems: "center", gap: "6px" }}>
          <FontAwesomeIcon icon={faPlus} /> Add spot
        </button>
      </div>

      {error && <p style={{ color: "#C0392B", fontSize: "0.88em" }}>{error}</p>}
      {loading && <p style={{ color: "var(--color-subtext)", fontSize: "0.92em" }}>Loading spots...</p>}
      {!loading && spots.length === 0 && !error && (
        <p style={{ color: "var(--color-subtext)", fontSize: "0.92em" }}>No spots saved yet. Add your first one!</p>
      )}

      {!loading && spots.length > 0 && (() => {
        const cities = [...new Set(spots.map((s) => s.city).filter(Boolean))].sort();
        const chipBase = {
          fontSize: "0.76em", fontWeight: 700, padding: "0.3em 0.85em",
          borderRadius: "999px", cursor: "pointer", border: "2px solid var(--color-accent-dim)",
          background: "var(--color-accent-hover)", color: "var(--color-subtext)", boxShadow: "none",
        };
        const chipActive = { ...chipBase, background: "var(--color-accent)", color: "var(--color-text)", border: "2px solid var(--color-text)" };
        return (
          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "14px" }}>
            <button style={!filterGroup ? chipActive : chipBase} onClick={() => setFilterGroup(null)}>All</button>
            {ICON_GROUPS.map((g) => (
              <button key={g.key} style={filterGroup === g.key ? chipActive : chipBase}
                onClick={() => setFilterGroup(filterGroup === g.key ? null : g.key)}>
                {g.label}
              </button>
            ))}
            {cities.length >= 1 && (
              <button
                style={filterCity ? chipActive : chipBase}
                onClick={() => setShowCityModal(true)}
              >
                {filterCity || "City"} ▾
              </button>
            )}
          </div>
        );
      })()}

      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {spots.filter((s) => {
          if (filterCity && s.city !== filterCity) return false;
          if (filterGroup) {
            const group = ICON_GROUPS.find((g) => g.key === filterGroup);
            if (group && !group.icons.has(s.icon)) return false;
          }
          return true;
        }).map((spot) => {
          const expanded = expandedSpotId === spot.id;
          return (
            <div
              key={spot.id}
              onClick={() => setExpandedSpotId(expanded ? null : spot.id)}
              style={{
                border: "2.5px solid var(--color-card-border)", borderRadius: "14px",
                padding: "12px 16px", background: "var(--color-surface)",
                boxShadow: "4px 4px 0 var(--color-card-shadow)",
                cursor: "pointer",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                <div style={{
                  width: "38px", height: "38px", borderRadius: "50%",
                  background: "var(--color-accent)", display: "flex", alignItems: "center",
                  justifyContent: "center", flexShrink: 0,
                }}>
                  <FontAwesomeIcon icon={spotIcon(spot.icon)} style={{ color: "var(--color-text)", fontSize: "16px" }} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <strong style={{ color: "var(--color-text)", fontSize: "0.95em" }}>{spot.name}</strong>
                  <p style={{ margin: "2px 0 0", fontSize: "0.78em", color: "var(--color-subtext)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {spot.address}
                  </p>
                  {spot.description && !expanded && (
                    <p style={{ margin: "3px 0 0", fontSize: "0.76em", color: "var(--color-subtext)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {spot.description}
                    </p>
                  )}
                </div>
                <div style={{ display: "flex", gap: "6px", flexShrink: 0 }}>
                  <button onClick={(e) => { e.stopPropagation(); shareSpot(spot); }} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--color-placeholder)", fontSize: "16px", padding: "2px 4px", boxShadow: "none" }}>
                    <FontAwesomeIcon icon={faShareNodes} />
                  </button>
                  {expanded && (
                    <>
                      <button onClick={(e) => { e.stopPropagation(); openEdit(spot); }} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--color-placeholder)", fontSize: "16px", padding: "2px 4px", boxShadow: "none" }}>
                        <FontAwesomeIcon icon={faPen} />
                      </button>
                      <button onClick={(e) => { e.stopPropagation(); setPendingDelete(spot); }} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--color-placeholder)", fontSize: "16px", padding: "2px 4px", boxShadow: "none" }}>
                        <FontAwesomeIcon icon={faTrash} />
                      </button>
                    </>
                  )}
                </div>
              </div>

              {expanded && (
                <div style={{ marginTop: "12px", paddingTop: "10px", borderTop: "1px solid var(--color-divider)" }}>
                  {/* Read-only mini-map */}
                  <div style={{ borderRadius: "12px", overflow: "hidden", border: "2px solid var(--color-accent-dim)", height: "160px", marginBottom: "10px" }}>
                    <div ref={expandedSpotId === spot.id ? previewMapContainerRef : null} style={{ height: "100%", width: "100%" }} />
                  </div>
                  {spot.description && (
                    <p style={{ margin: "0 0 10px", fontSize: "0.82em", color: "var(--color-subtext)", lineHeight: 1.4 }}>
                      {spot.description}
                    </p>
                  )}
                  <button
                    onClick={(e) => { e.stopPropagation(); navigate("/plan", { state: { spot } }); }}
                    style={{ fontSize: "0.8em", padding: "0.35em 1em" }}
                  >
                    Open in Find Places →
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Add / Edit modal */}
      {showForm && (
        <div style={{
          position: "fixed", inset: 0, background: "var(--color-overlay)",
          backdropFilter: "blur(2px)", display: "flex", alignItems: "flex-start",
          justifyContent: "center", zIndex: 1000, overflowY: "auto", padding: "20px 0",
        }}>
          <div style={{
            background: "var(--color-surface)", border: "2.5px solid var(--color-card-border)",
            borderRadius: "24px", padding: "24px", maxWidth: "400px",
            width: "90%", boxShadow: "6px 6px 0 var(--color-card-shadow)",
            display: "flex", flexDirection: "column", gap: "14px",
            margin: "auto",
          }}>
            <h3 style={{ margin: 0, fontSize: "1.05em" }}>{editingId ? "Edit spot" : "Add spot"}</h3>

            <input
              type="text" placeholder="Name (e.g. Home) *"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />

            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="Note (optional)"
              rows={2}
              style={{
                display: "block", width: "100%", boxSizing: "border-box",
                background: "var(--color-input-bg)", border: "2px solid var(--color-card-border)",
                borderRadius: "10px", padding: "8px 12px", fontSize: "16px",
                fontFamily: "Nunito, sans-serif", fontWeight: 500,
                color: "var(--color-text)", outline: "none", resize: "none",
                boxShadow: "2px 2px 0 var(--color-accent-dim)",
              }}
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
                  gap: "4px", background: "var(--color-accent-hover)", border: "1.5px solid var(--color-accent)",
                  color: "var(--color-subtext)", fontWeight: 700, whiteSpace: "nowrap", boxShadow: "none",
                }}
              >
                <FontAwesomeIcon icon={faLocationCrosshairs} />
                {locating ? "Locating…" : "Use my location"}
              </button>
            </div>

            {/* Mini map */}
            <div style={{ borderRadius: "12px", overflow: "hidden", border: "2px solid var(--color-accent-dim)", height: "200px" }}>
              <div ref={mapContainerRef} style={{ height: "100%", width: "100%" }} />
            </div>
            {!form.lat && (
              <p style={{ margin: "-8px 0 0", fontSize: "0.75em", color: "var(--color-subtext)" }}>
                Search an address, use your location, or tap the map to set a spot.
              </p>
            )}

            {/* Icon picker */}
            <div>
              <p style={{ margin: "0 0 8px", fontSize: "0.82em", color: "var(--color-subtext)", fontWeight: 600 }}>Icon</p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {SPOT_ICONS.map(({ key, icon }) => (
                  <button
                    key={key}
                    onClick={() => setForm({ ...form, icon: key })}
                    style={{
                      width: "36px", height: "36px", borderRadius: "50%",
                      border: form.icon === key ? "2.5px solid var(--color-text)" : "2px solid var(--color-accent-dim)",
                      background: form.icon === key ? "var(--color-accent)" : "var(--color-accent-hover)",
                      cursor: "pointer", display: "flex", alignItems: "center",
                      justifyContent: "center", padding: 0, boxShadow: "none",
                    }}
                  >
                    <FontAwesomeIcon icon={icon} style={{ color: "var(--color-text)", fontSize: "14px" }} />
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

      {/* City picker modal */}
      {showCityModal && (() => {
        const cities = [...new Set(spots.map((s) => s.city).filter(Boolean))].sort();
        return (
          <div
            style={{ position: "fixed", inset: 0, background: "var(--color-overlay)", backdropFilter: "blur(2px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}
            onClick={() => setShowCityModal(false)}
          >
            <div
              style={{ background: "var(--color-surface)", border: "2.5px solid var(--color-card-border)", borderRadius: "24px", padding: "24px", maxWidth: "320px", width: "90%", boxShadow: "6px 6px 0 var(--color-card-shadow)", display: "flex", flexDirection: "column", gap: "10px" }}
              onClick={(e) => e.stopPropagation()}
            >
              <h3 style={{ margin: 0, fontSize: "1em" }}>Filter by city</h3>
              <button
                style={{ textAlign: "left", background: filterCity === null ? "var(--color-accent)" : "var(--color-accent-hover)", border: filterCity === null ? "2px solid var(--color-text)" : "2px solid var(--color-accent-dim)", borderRadius: "10px", padding: "10px 14px", cursor: "pointer", fontWeight: 700, color: "var(--color-text)", fontSize: "0.9em", boxShadow: "none" }}
                onClick={() => { setFilterCity(null); setShowCityModal(false); }}
              >
                All cities
              </button>
              {cities.map((c) => (
                <button
                  key={c}
                  style={{ textAlign: "left", background: filterCity === c ? "var(--color-accent)" : "var(--color-accent-hover)", border: filterCity === c ? "2px solid var(--color-text)" : "2px solid var(--color-accent-dim)", borderRadius: "10px", padding: "10px 14px", cursor: "pointer", fontWeight: 700, color: "var(--color-text)", fontSize: "0.9em", boxShadow: "none" }}
                  onClick={() => { setFilterCity(c); setShowCityModal(false); }}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
        );
      })()}

      {/* Delete confirm */}
      {pendingDelete && (
        <div style={{
          position: "fixed", inset: 0, background: "var(--color-overlay)",
          backdropFilter: "blur(2px)", display: "flex", alignItems: "center",
          justifyContent: "center", zIndex: 1000,
        }}>
          <div style={{
            background: "var(--color-surface)", border: "2.5px solid var(--color-card-border)",
            borderRadius: "24px", padding: "32px", maxWidth: "340px",
            width: "90%", boxShadow: "6px 6px 0 var(--color-card-shadow)",
            display: "flex", flexDirection: "column", gap: "12px",
          }}>
            <h3 style={{ margin: 0, fontSize: "1.1em" }}>Delete spot?</h3>
            <p style={{ margin: 0, color: "var(--color-subtext)", fontSize: "0.9em" }}>
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

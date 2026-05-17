import { useState, useEffect, useRef } from "react";
import { Geolocation } from "@capacitor/geolocation";
import { useLocation } from "react-router-dom";
import { useLoadScript, Autocomplete } from "@react-google-maps/api";
import api from "../api";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faSun,
  faCloudSun,
  faHeart,
  faTriangleExclamation,
  faLocationCrosshairs,
} from "@fortawesome/free-solid-svg-icons";

const MAP_CENTER = { lat: 51.505, lng: -0.09 };
const API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

const LIBRARIES = ["places"];

function clearPolylines(ref) {
  ref.current.forEach((p) => p.setMap(null));
  ref.current = [];
}

function scoreRouteFromShadow(segments, preference) {
  const shadedCount = segments.filter((s) => s.shaded).length;
  return preference === "shade" ? shadedCount : segments.length - shadedCount;
}

function drawRoute(mapInstance, polylinesRef, coords, segments, sunAltitude) {
  clearPolylines(polylinesRef);
  if (!mapInstance || !coords || !segments) return;

  coords.slice(0, -1).forEach((point, i) => {
    const seg = segments[i] ?? segments[segments.length - 1];
    const color =
      sunAltitude <= 0 ? "#888888" : seg.shaded ? "#888888" : "#FFD700";

    const polyline = new window.google.maps.Polyline({
      path: [
        { lat: point[0], lng: point[1] },
        { lat: coords[i + 1][0], lng: coords[i + 1][1] },
      ],
      strokeColor: color,
      strokeWeight: 4,
      map: mapInstance,
    });
    polylinesRef.current.push(polyline);
  });
}

export default function RouteMap() {
  const { isLoaded } = useLoadScript({
    googleMapsApiKey: API_KEY,
    libraries: LIBRARIES,
  });
  const location = useLocation();

  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const polylinesRef = useRef([]);
  const startMarkerRef = useRef(null);
  const endMarkerRef = useRef(null);
  const currentLocationMarkerRef = useRef(null);
  const watchIdRef = useRef(null);
  const weatherLocationRef = useRef(null);
  const startAutocompleteRef = useRef(null);
  const endAutocompleteRef = useRef(null);
  const autoCalculateRef = useRef(false);
  const currentLocationRef = useRef(null);

  // Refs for use inside map click listener (avoids stale closures)
  const startRef = useRef(null);
  const endRef = useRef(null);
  const sunDataRef = useRef(null);

  const [preference, setPreference] = useState("sun");
  const [start, setStart] = useState(null);
  const [end, setEnd] = useState(null);
  const [startAddress, setStartAddress] = useState("");
  const [endAddress, setEndAddress] = useState("");
  const [sunData, setSunData] = useState(null);
  const [error, setError] = useState(null);
  const [saveForm, setSaveForm] = useState(null); // null = hidden, {} = open
  const [saveError, setSaveError] = useState(null);
  const [routeSaved, setRouteSaved] = useState(false);
  const [savedRouteName, setSavedRouteName] = useState(null);
  const [routeStats, setRouteStats] = useState(null);
  const [routeCoords, setRouteCoords] = useState(null);
  const [routeSegments, setRouteSegments] = useState(null);
  const [goMode, setGoMode] = useState(false);
  const [goSegmentIdx, setGoSegmentIdx] = useState(0);
  const [planning, setPlanning] = useState(false);
  const [currentLocation, setCurrentLocation] = useState(null);
  const [weather, setWeather] = useState(null);

  startRef.current = start;
  endRef.current = end;
  sunDataRef.current = sunData;
  currentLocationRef.current = currentLocation;

  const colors = preference === "shade" ? {
    accent:      "#5E8FAD",
    accentFaint: "#B0CCDE",
    accentGlow:  "rgba(94,143,173,0.15)",
    text:        "#263748",
    subtext:     "#4A7090",
    surface:     "rgba(226,234,240,0.95)",
  } : {
    accent:      "#FFD600",
    accentFaint: "#FFE082",
    accentGlow:  "rgba(255,193,7,0.15)",
    text:        "#3D2C00",
    subtext:     "#A87500",
    surface:     "rgba(255,253,240,0.95)",
  };

  // Pre-populate from a saved route navigated from My Routes
  useEffect(() => {
    const saved = location.state?.route;
    if (!saved) return;
    setStart({ lat: saved.start_lat, lng: saved.start_lng });
    setEnd({ lat: saved.end_lat, lng: saved.end_lng });
    setStartAddress(saved.start_address || "");
    setEndAddress(saved.end_address || "");
    setSavedRouteName(saved.name);
    setRouteSaved(true);
    if (saved.preference) setPreference(saved.preference);
    autoCalculateRef.current = true;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync body theme class with preference
  useEffect(() => {
    document.body.classList.toggle("shade-mode", preference === "shade");
    return () => document.body.classList.remove("shade-mode");
  }, [preference]);

  // Auto-calculate once start, end and API are ready
  useEffect(() => {
    if (autoCalculateRef.current && start && end && isLoaded) {
      autoCalculateRef.current = false;
      planRoute();
    }
  }, [start, end, isLoaded]); // eslint-disable-line react-hooks/exhaustive-deps

  // Create the map once the API is loaded — mapId goes into the constructor
  useEffect(() => {
    if (!isLoaded || !containerRef.current || mapRef.current) return;

    mapRef.current = new window.google.maps.Map(containerRef.current, {
      center: MAP_CENTER,
      zoom: 15,
      disableDefaultUI: true,
      mapTypeControl: true,
      streetViewControl: true,
      streetViewControlOptions: { position: window.google.maps.ControlPosition.RIGHT_BOTTOM },
    });
  }, [isLoaded]);

  // Pan to show both endpoints as soon as start, end and map are all ready
  useEffect(() => {
    if (!mapRef.current || !start || !end) return;
    const bounds = new window.google.maps.LatLngBounds();
    bounds.extend(start);
    bounds.extend(end);
    mapRef.current.fitBounds(bounds, { top: 60, right: 20, bottom: 20, left: 20 });
  }, [start, end, isLoaded]); // eslint-disable-line react-hooks/exhaustive-deps

  // Show current location dot
  useEffect(() => {
    if (!isLoaded) return;

    const blueDotSvg = encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 22 22">' +
        '<circle cx="11" cy="11" r="11" fill="rgba(255,214,0,0.25)"/>' +
        '<circle cx="11" cy="11" r="6" fill="#FFD600" stroke="white" stroke-width="2"/>' +
        "</svg>",
    );

    let initialPanDone = false;
    let cancelled = false;

    function handlePosition(lat, lng) {
      if (cancelled || !mapRef.current) return;
      setCurrentLocation({ lat, lng });
      if (!initialPanDone && !startRef.current) {
        mapRef.current.panTo({ lat, lng });
        initialPanDone = true;
        fetchWeather(lat, lng);
      }
      if (currentLocationMarkerRef.current) {
        currentLocationMarkerRef.current.setPosition({ lat, lng });
      } else {
        currentLocationMarkerRef.current = new window.google.maps.Marker({
          position: { lat, lng },
          map: mapRef.current,
          icon: {
            url: `data:image/svg+xml;charset=UTF-8,${blueDotSvg}`,
            scaledSize: new window.google.maps.Size(22, 22),
            anchor: new window.google.maps.Point(11, 11),
          },
          zIndex: 1,
          title: "Your location",
        });
      }
    }

    Geolocation.requestPermissions().then(() => {
      Geolocation.watchPosition(
        { enableHighAccuracy: true, maximumAge: 10000 },
        (pos, err) => {
          if (err || !pos) return;
          handlePosition(pos.coords.latitude, pos.coords.longitude);
        },
      ).then((id) => { watchIdRef.current = id; });
    }).catch(() => {
      // fall back to browser geolocation on web
      if (!navigator.geolocation) return;
      watchIdRef.current = navigator.geolocation.watchPosition(
        ({ coords: { latitude: lat, longitude: lng } }) => handlePosition(lat, lng),
        null,
        { enableHighAccuracy: true, maximumAge: 10000 },
      );
    });

    return () => {
      cancelled = true;
      if (watchIdRef.current !== null) {
        Geolocation.clearWatch({ id: watchIdRef.current }).catch(() => {
          navigator.geolocation?.clearWatch(watchIdRef.current);
        });
      }
      if (currentLocationMarkerRef.current) {
        currentLocationMarkerRef.current.setMap(null);
        currentLocationMarkerRef.current = null;
      }
    };
  }, [isLoaded]);

  // In Go mode, find which route segment the user is currently on
  useEffect(() => {
    if (!goMode || !currentLocation || !routeCoords) return;
    let minDist = Infinity;
    let nearestIdx = 0;
    routeCoords.forEach(([lat, lng], i) => {
      const d = (lat - currentLocation.lat) ** 2 + (lng - currentLocation.lng) ** 2;
      if (d < minDist) { minDist = d; nearestIdx = i; }
    });
    setGoSegmentIdx(nearestIdx);
    mapRef.current?.panTo(currentLocation);
  }, [goMode, currentLocation]); // eslint-disable-line react-hooks/exhaustive-deps

  // Re-register click listener whenever start/end change
  useEffect(() => {
    if (!mapRef.current) return;
    const map = mapRef.current;
    window.google.maps.event.clearListeners(map, "click");

    map.addListener("click", async (e) => {
      const coords = { lat: e.latLng.lat(), lng: e.latLng.lng() };
      const geocoder = new window.google.maps.Geocoder();
      const result = await geocoder.geocode({ location: coords });
      const address = result.results[0]?.formatted_address || "";

      if (!startRef.current) {
        setStart(coords);
        setStartAddress(address);
      } else if (!endRef.current || !sunDataRef.current) {
        setEnd(coords);
        setEndAddress(address);
        setSavedRouteName(null);
        setRouteSaved(false);
      }
    });
  }, [isLoaded]);

  // Sync start marker
  useEffect(() => {
    if (!mapRef.current) return;
    if (startMarkerRef.current) {
      startMarkerRef.current.setMap(null);
      startMarkerRef.current = null;
    }
    if (start) {
      startMarkerRef.current = new window.google.maps.Marker({
        position: start,
        map: mapRef.current,
        icon: {
          url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="36" viewBox="0 0 24 36"><path fill="#FFD600" stroke="#fff" stroke-width="1.5" d="M12 0C5.4 0 0 5.4 0 12c0 9 12 24 12 24S24 21 24 12C24 5.4 18.6 0 12 0z"/><circle cx="12" cy="12" r="5" fill="white"/></svg>')}`,
          scaledSize: new window.google.maps.Size(24, 36),
          anchor: new window.google.maps.Point(12, 36),
        },
      });
    }
  }, [start, isLoaded]);

  // Sync end marker
  useEffect(() => {
    if (!mapRef.current) return;
    if (endMarkerRef.current) {
      endMarkerRef.current.setMap(null);
      endMarkerRef.current = null;
    }
    if (end) {
      endMarkerRef.current = new window.google.maps.Marker({
        position: end,
        map: mapRef.current,
        icon: {
          url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="36" viewBox="0 0 24 36"><path fill="#f5ae0a" stroke="#fff" stroke-width="1.5" d="M12 0C5.4 0 0 5.4 0 12c0 9 12 24 12 24S24 21 24 12C24 5.4 18.6 0 12 0z"/><circle cx="12" cy="12" r="5" fill="white"/></svg>')}`,
          scaledSize: new window.google.maps.Size(24, 36),
          anchor: new window.google.maps.Point(12, 36),
        },
      });
    }
  }, [end, isLoaded]);

  function togglePreference() {
    setPreference((p) => (p === "sun" ? "shade" : "sun"));
    clearPolylines(polylinesRef);
    setSunData(null);
  }

  function handlePlaceSelected(type) {
    const autocomplete =
      type === "start"
        ? startAutocompleteRef.current
        : endAutocompleteRef.current;
    const place = autocomplete.getPlace();
    if (!place.geometry) return;

    const coords = {
      lat: place.geometry.location.lat(),
      lng: place.geometry.location.lng(),
    };
    const address = place.formatted_address || place.name || "";

    if (type === "start") {
      setStart(coords);
      setStartAddress(address);
      clearPolylines(polylinesRef);
      setSunData(null);
      setSavedRouteName(null);
      setRouteSaved(false);
    } else {
      setEnd(coords);
      setEndAddress(address);
      setSavedRouteName(null);
      setRouteSaved(false);
    }
    mapRef.current?.panTo(coords);
  }

  function roughDistanceKm(a, b) {
    const dLat = (a.lat - b.lat) * 111;
    const dLng = (a.lng - b.lng) * 111 * Math.cos((a.lat * Math.PI) / 180);
    return Math.sqrt(dLat * dLat + dLng * dLng);
  }

  async function fetchWeather(lat, lng) {
    const token = localStorage.getItem("token");
    try {
      const r = await api.post(
        "/weather/current",
        { lat, lng },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setWeather(r.data);
      weatherLocationRef.current = { lat, lng };
    } catch (_) { /* weather is non-critical */ }
  }

  async function planRoute() {
    setError(null);
    setSunData(null);
    setPlanning(true);
    clearPolylines(polylinesRef);
    try {
      const directionsService = new window.google.maps.DirectionsService();
      const result = await directionsService.route({
        origin: start,
        destination: end,
        travelMode: window.google.maps.TravelMode.WALKING,
        provideRouteAlternatives: true,
      });

      const shortestDistance = Math.min(
        ...result.routes.map((r) => r.legs[0].distance.value),
      );
      if (shortestDistance > 5000) {
        setError("Route is over 5 km — please choose a shorter journey.");
        return;
      }

      const token = localStorage.getItem("token");

      // Resolve local time at the route's location, not the user's device timezone
      const midLat = (start.lat + end.lat) / 2;
      const midLng = (start.lng + end.lng) / 2;
      const tzRes = await api.get(
        "https://maps.googleapis.com/maps/api/timezone/json",
        {
          params: {
            location: `${midLat},${midLng}`,
            timestamp: Math.floor(Date.now() / 1000),
            key: API_KEY,
          },
        },
      );
      const timeZoneId = tzRes.data.timeZoneId || "UTC";
      // sv-SE gives "YYYY-MM-DD HH:MM:SS" — replace space with T for ISO format
      const datetime = new Date()
        .toLocaleString("sv-SE", { timeZone: timeZoneId })
        .replace(" ", "T");
      const allCoords = result.routes.map((r) =>
        r.overview_path.map((p) => [p.lat(), p.lng()]),
      );

      const batchRes = await api.post(
        "/sun/shadow-analyze-batch",
        { routes: allCoords, datetime },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      const {
        sun_altitude,
        sun_azimuth,
        date,
        routes: routeResults,
      } = batchRes.data;

      let bestCoords = null;
      let bestSegments = null;
      let bestScore = -1;
      let bestIndex = 0;

      allCoords.forEach((coords, i) => {
        const score = scoreRouteFromShadow(
          routeResults[i].segments,
          preference,
        );
        if (score > bestScore) {
          bestScore = score;
          bestCoords = coords;
          bestSegments = routeResults[i].segments;
          bestIndex = i;
        }
      });

      if (bestCoords) {
        const leg = result.routes[bestIndex].legs[0];
        setRouteStats({
          distance: leg.distance.text,
          duration: leg.duration.text,
        });
        setSunData({ sun_altitude, sun_azimuth, date });
        setRouteCoords(bestCoords);
        setRouteSegments(bestSegments);
        drawRoute(
          mapRef.current,
          polylinesRef,
          bestCoords,
          bestSegments,
          sun_altitude,
        );

        const bounds = new window.google.maps.LatLngBounds();
        bestCoords.forEach(([lat, lng]) => bounds.extend({ lat, lng }));
        mapRef.current.fitBounds(bounds, { top: 60, right: 20, bottom: 20, left: 20 });

        const midpoint = { lat: midLat, lng: midLng };
        if (
          !weatherLocationRef.current ||
          roughDistanceKm(midpoint, weatherLocationRef.current) > 20
        ) {
          fetchWeather(midLat, midLng);
        }
      }
    } catch (err) {
      console.error("planRoute error:", err);
      setError("Could not fetch route. Please try again.");
    } finally {
      setPlanning(false);
    }
  }

  async function saveRoute() {
    if (!saveForm?.name?.trim()) {
      setSaveError("Name is required.");
      return;
    }
    setSaveError(null);
    try {
      const token = localStorage.getItem("token");
      await api.post(
        "/routes",
        {
          name: saveForm.name.trim(),
          description: saveForm.description?.trim() || null,
          start_lat: start.lat,
          start_lng: start.lng,
          end_lat: end.lat,
          end_lng: end.lng,
          start_address: startAddress.split(",")[0].trim() || null,
          end_address: endAddress.split(",")[0].trim() || null,
          preference,
        },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setSavedRouteName(saveForm.name.trim());
      setSaveForm(null);
      setRouteSaved(true);
    } catch {
      setSaveError("Could not save route. Please try again.");
    }
  }

  function reset() {
    setStart(null);
    setEnd(null);
    setStartAddress("");
    setEndAddress("");
    setSunData(null);
    setError(null);
    setSaveForm(null);
    setSaveError(null);
    setRouteSaved(false);
    setSavedRouteName(null);
    setRouteStats(null);
    setRouteCoords(null);
    setRouteSegments(null);
    setGoMode(false);
    clearPolylines(polylinesRef);
    if (weatherLocationRef.current)
      fetchWeather(
        weatherLocationRef.current.lat,
        weatherLocationRef.current.lng,
      );
  }

  if (!isLoaded) return <p>Loading map...</p>;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Sun / Shade toggle + Reset */}
      <div
        style={{
          marginBottom: "8px",
          display: "flex",
          alignItems: "center",
          gap: "10px",
        }}
      >
        <span
          style={{
            fontSize: "0.88em",
            fontWeight: 600,
            color: preference === "sun" ? colors.text : "#A0A0A0",
          }}
        >
          <FontAwesomeIcon icon={faSun} /> Sun
        </span>
        <div
          onClick={togglePreference}
          style={{
            width: "48px",
            height: "26px",
            borderRadius: "13px",
            background: preference === "sun" ? "#FFD600" : colors.accent,
            position: "relative",
            cursor: "pointer",
            transition: "background 0.25s",
            boxShadow: "inset 0 1px 3px rgba(0,0,0,0.12)",
          }}
        >
          <div
            style={{
              width: "20px",
              height: "20px",
              borderRadius: "50%",
              background: "white",
              position: "absolute",
              top: "3px",
              left: preference === "sun" ? "3px" : "25px",
              transition: "left 0.25s",
              boxShadow: "0 1px 4px rgba(0,0,0,0.18)",
            }}
          />
        </div>
        <span
          style={{
            fontSize: "0.88em",
            fontWeight: 600,
            color: preference === "shade" ? colors.text : "#A0A0A0",
          }}
        >
          <FontAwesomeIcon icon={faCloudSun} /> Shade
        </span>
        {start && !planning && (
          <button onClick={reset} style={{ marginLeft: "auto", fontSize: "0.75em", padding: "0.35em 0.9em" }}>Reset</button>
        )}
      </div>

      {/* Address inputs + action buttons */}
      <div
        style={{
          marginBottom: "8px",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "6px",
          }}
        >
          <div style={{ position: "relative" }}>
            <Autocomplete
              onLoad={(a) => { startAutocompleteRef.current = a; }}
              onPlaceChanged={() => handlePlaceSelected("start")}
            >
              <input
                type="text"
                value={startAddress}
                onChange={(e) => {
                  setStartAddress(e.target.value);
                  setStart(null);
                  clearPolylines(polylinesRef);
                  setSunData(null);
                  setSavedRouteName(null);
                  setRouteSaved(false);
                }}
                placeholder="Start address (or click map)"
                style={currentLocation && !start ? { paddingRight: "118px" } : undefined}
              />
            </Autocomplete>
            {currentLocation && !start && (
              <button
                onClick={async () => {
                  const geocoder = new window.google.maps.Geocoder();
                  const result = await geocoder.geocode({ location: currentLocation });
                  const address = result.results[0]?.formatted_address || "My location";
                  setStart(currentLocation);
                  setStartAddress(address);
                  clearPolylines(polylinesRef);
                  setSunData(null);
                  setSavedRouteName(null);
                  setRouteSaved(false);
                }}
                style={{
                  position: "absolute", right: "6px", top: "50%", transform: "translateY(-50%)",
                  fontSize: "10px", padding: "2px 7px", display: "flex", alignItems: "center",
                  gap: "4px", background: colors.accentGlow, border: `1.5px solid ${colors.accent}`,
                  color: colors.subtext, fontWeight: 700, whiteSpace: "nowrap",
                }}
              >
                <FontAwesomeIcon icon={faLocationCrosshairs} /> Use my location
              </button>
            )}
          </div>
          <Autocomplete
            onLoad={(a) => {
              endAutocompleteRef.current = a;
            }}
            onPlaceChanged={() => handlePlaceSelected("end")}
          >
            <input
              type="text"
              value={endAddress}
              onChange={(e) => {
                setEndAddress(e.target.value);
                setSavedRouteName(null);
                setRouteSaved(false);
              }}
              placeholder="End address (or click map)"
            />
          </Autocomplete>
        </div>
        {/* Plan Route + Save row — below inputs, right-aligned */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "8px" }}>
          {!planning && start && end && !sunData && (
            <button onClick={planRoute} style={{ fontSize: "0.85em", padding: "0.4em 1.2em", fontWeight: 800, marginLeft: "auto" }}>Plan Route</button>
          )}
          {sunData && !saveForm && !routeSaved && (
            <button onClick={() => setSaveForm({ name: "", description: "" })} style={{ fontSize: "0.85em", padding: "0.4em 1.2em", fontWeight: 800 }}>
              Save Route
            </button>
          )}
        </div>
        {saveForm && (
          <div style={{ display: "flex", gap: "6px", alignItems: "flex-start" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "6px", flex: 1 }}>
              <input
                type="text"
                placeholder="Route name *"
                value={saveForm.name}
                onChange={(e) => setSaveForm({ ...saveForm, name: e.target.value })}
              />
              <input
                type="text"
                placeholder="Description (optional)"
                value={saveForm.description}
                onChange={(e) => setSaveForm({ ...saveForm, description: e.target.value })}
              />
              {saveError && (
                <p style={{ color: "#FF5A3C", margin: 0, fontSize: "0.82em", fontWeight: 700 }}>
                  {saveError}
                </p>
              )}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <button onClick={saveRoute}>Save</button>
              <button onClick={() => { setSaveForm(null); setSaveError(null); }}>Cancel</button>
            </div>
          </div>
        )}
      </div>

      {(savedRouteName || routeStats || planning) && (
        <div style={{ margin: "0 0 6px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          {savedRouteName && (
            <span style={{ fontSize: "13px", color: "#5A8F5A", fontWeight: 600 }}>
              <FontAwesomeIcon icon={faHeart} /> {savedRouteName}
            </span>
          )}
          {planning ? (
            <div className="planning-dots" style={{ marginLeft: "auto" }}>
              <span className="planning-label">planning</span>
              <span>•</span>
              <span>•</span>
              <span>•</span>
            </div>
          ) : routeStats && (
            <span style={{ fontSize: "12px", color: colors.subtext, fontWeight: 500, whiteSpace: "nowrap", marginLeft: "auto" }}>
              Approx. {routeStats.distance} · {routeStats.duration} walk
            </span>
          )}
        </div>
      )}

      {error && (
        <div
          style={{
            marginBottom: "8px",
            padding: "10px 14px",
            borderRadius: "12px",
            background: "#FFF0ED",
            border: "2px solid #FF5A3C",
            boxShadow: "3px 3px 0 #FF5A3C",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <FontAwesomeIcon
            icon={faTriangleExclamation}
            style={{ color: "#FF5A3C", fontSize: "1.1em" }}
          />
          <span
            style={{ color: "#C0392B", fontWeight: 700, fontSize: "0.88em" }}
          >
            {error}
          </span>
        </div>
      )}

      {/* Map — fills remaining height */}
      <div style={{ flex: 1, minHeight: 0, position: "relative" }}>
        <div className="map-wrapper" style={{ height: "100%", flex: "none" }}>
          <div ref={containerRef} style={{ height: "100%", width: "100%" }} />
          {currentLocation && (
            <button
              onClick={() => mapRef.current?.panTo(currentLocation)}
              title="Recenter to my location"
              style={{
                position: "absolute", bottom: "10px", right: "10px", zIndex: 10,
                width: "40px", height: "40px", borderRadius: "50%",
                background: colors.surface,
                border: `1.5px solid ${colors.accentFaint}`,
                boxShadow: `0 2px 8px ${colors.accentGlow}`,
                cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
                padding: 0,
              }}
            >
              <FontAwesomeIcon icon={faLocationCrosshairs} style={{ color: colors.subtext, fontSize: "18px" }} />
            </button>
          )}
          {sunData && (
            <div
              style={{
                position: "absolute",
                bottom: "10px",
                left: "10px",
                display: "flex",
                flexDirection: "column",
                gap: "6px",
                alignItems: "flex-start",
              }}
            >
              <div
                style={{
                  background: colors.surface,
                  padding: "5px 12px",
                  borderRadius: "20px",
                  display: "flex",
                  gap: "14px",
                  fontSize: "12px",
                  border: `1.5px solid ${colors.accentFaint}`,
                  boxShadow: `0 2px 8px ${colors.accentGlow}`,
                  fontWeight: 500,
                  color: colors.text,
                }}
              >
                <span
                  style={{ display: "flex", alignItems: "center", gap: "4px" }}
                >
                  <span
                    style={{
                      width: 14,
                      height: 4,
                      background: "#FFD700",
                      display: "inline-block",
                      borderRadius: 2,
                    }}
                  />
                  Sunny
                </span>
                <span
                  style={{ display: "flex", alignItems: "center", gap: "4px" }}
                >
                  <span
                    style={{
                      width: 14,
                      height: 4,
                      background: "#888888",
                      display: "inline-block",
                      borderRadius: 2,
                    }}
                  />
                  Shaded
                </span>
              </div>
            </div>
          )}
          {sunData && !planning && (
            <button
              onClick={() => goMode ? setGoMode(false) : (setGoMode(true), setGoSegmentIdx(0))}
              style={{
                position: "absolute", top: "52px", right: "10px", zIndex: 10,
                width: "64px", height: "64px", borderRadius: "50%",
                background: goMode ? "#FF5A3C" : colors.accent,
                border: "3px solid white",
                boxShadow: "0 4px 16px rgba(0,0,0,0.2)",
                fontSize: "0.85em", fontWeight: 800, color: goMode ? "white" : colors.text,
                cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
              }}
            >
              {goMode ? "Stop" : "Go"}
            </button>
          )}
          {goMode && routeSegments && (() => {
            const side = routeSegments[goSegmentIdx]?.sunny_side;
            const instructions = {
              left:    { text: "← Walk on the left",   color: "#3D2C00" },
              right:   { text: "Walk on the right →",  color: "#3D2C00" },
              both:    { text: "☀️ Both sides sunny",  color: "#3D2C00" },
              neither: { text: "Shaded section",        color: "#888888" },
            };
            const inst = instructions[side] ?? instructions.neither;
            return (
              <div style={{
                position: "absolute", bottom: "20px", left: "50%", transform: "translateX(-50%)",
                background: colors.surface, padding: "14px 28px", borderRadius: "20px",
                border: `2px solid ${colors.accent}`, boxShadow: `0 4px 20px ${colors.accentGlow}`,
                textAlign: "center", whiteSpace: "nowrap", zIndex: 10,
              }}>
                <div style={{ fontSize: "1.25em", fontWeight: 800, color: inst.color }}>
                  {inst.text}
                </div>
              </div>
            );
          })()}
          {weather && (
            <div
              style={{
                position: "absolute",
                top: "10px",
                right: "10px",
                background: colors.surface,
                padding: "6px 12px",
                borderRadius: "20px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
                fontSize: "12px",
                fontWeight: 500,
                color: colors.text,
                border: `1.5px solid ${colors.accentFaint}`,
                boxShadow: `0 2px 8px ${colors.accentGlow}`,
              }}
            >
              {weather.icon_url && (
                <img
                  src={weather.icon_url}
                  alt={weather.condition || ""}
                  style={{ width: 20, height: 20 }}
                />
              )}
              {weather.temperature != null && (
                <span>{Math.round(weather.temperature)}°C</span>
              )}
              {weather.uv_index != null && (
                <span style={{ color: colors.subtext }}>UV {weather.uv_index}</span>
              )}
              {weather.uv_index >= 6 && preference === "sun" && (
                <span style={{ color: "#C0392B", fontWeight: 700 }}>
                  sunscreen!
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

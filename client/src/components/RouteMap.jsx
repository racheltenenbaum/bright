import { useState, useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { useLoadScript, Autocomplete } from "@react-google-maps/api";
import axios from "axios";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faSun, faCloudSun, faHeart, faTriangleExclamation, faLocationCrosshairs } from "@fortawesome/free-solid-svg-icons";

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
    const color = sunAltitude <= 0 ? "#888888" : seg.shaded ? "#888888" : "#FFD700";

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
  const { isLoaded } = useLoadScript({ googleMapsApiKey: API_KEY, libraries: LIBRARIES });
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
  const [planning, setPlanning] = useState(false);
  const [currentLocation, setCurrentLocation] = useState(null);
  const [weather, setWeather] = useState(null);

  startRef.current = start;
  endRef.current = end;
  sunDataRef.current = sunData;

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
    autoCalculateRef.current = true;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
      fullscreenControl: false,
    });
  }, [isLoaded]);

  // Show current location blue dot
  useEffect(() => {
    if (!isLoaded || !navigator.geolocation) return;

    const blueDotSvg = encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 22 22">' +
      '<circle cx="11" cy="11" r="11" fill="rgba(255,214,0,0.25)"/>' +
      '<circle cx="11" cy="11" r="6" fill="#FFD600" stroke="white" stroke-width="2"/>' +
      '</svg>'
    );

    let initialPanDone = false;

    watchIdRef.current = navigator.geolocation.watchPosition(
      ({ coords: { latitude: lat, longitude: lng } }) => {
        if (!mapRef.current) return;
        setCurrentLocation({ lat, lng });
        if (!initialPanDone && !autoCalculateRef.current) {
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
      },
      null,
      { enableHighAccuracy: true, maximumAge: 10000 }
    );

    return () => {
      if (watchIdRef.current !== null) navigator.geolocation.clearWatch(watchIdRef.current);
      if (currentLocationMarkerRef.current) { currentLocationMarkerRef.current.setMap(null); currentLocationMarkerRef.current = null; }
    };
  }, [isLoaded]);

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
    if (startMarkerRef.current) { startMarkerRef.current.setMap(null); startMarkerRef.current = null; }
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
  }, [start]);

  // Sync end marker
  useEffect(() => {
    if (!mapRef.current) return;
    if (endMarkerRef.current) { endMarkerRef.current.setMap(null); endMarkerRef.current = null; }
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
  }, [end]);

  function togglePreference() {
    setPreference((p) => (p === "sun" ? "shade" : "sun"));
    clearPolylines(polylinesRef);
    setSunData(null);
  }

  function handlePlaceSelected(type) {
    const autocomplete = type === "start" ? startAutocompleteRef.current : endAutocompleteRef.current;
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
      const r = await axios.post(
        "http://localhost:8000/weather/current",
        { lat, lng },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setWeather(r.data);
      weatherLocationRef.current = { lat, lng };
    } catch {}
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

      const shortestDistance = Math.min(...result.routes.map((r) => r.legs[0].distance.value));
      if (shortestDistance > 5000) {
        setError("Route is over 5 km — please choose a shorter journey.");
        return;
      }

      const token = localStorage.getItem("token");

      // Resolve local time at the route's location, not the user's device timezone
      const midLat = (start.lat + end.lat) / 2;
      const midLng = (start.lng + end.lng) / 2;
      const tzRes = await axios.get("https://maps.googleapis.com/maps/api/timezone/json", {
        params: { location: `${midLat},${midLng}`, timestamp: Math.floor(Date.now() / 1000), key: API_KEY },
      });
      const timeZoneId = tzRes.data.timeZoneId || "UTC";
      // sv-SE gives "YYYY-MM-DD HH:MM:SS" — replace space with T for ISO format
      const datetime = new Date().toLocaleString("sv-SE", { timeZone: timeZoneId }).replace(" ", "T");
      const allCoords = result.routes.map((r) => r.overview_path.map((p) => [p.lat(), p.lng()]));

      const batchRes = await axios.post(
        "http://localhost:8000/sun/shadow-analyze-batch",
        { routes: allCoords, datetime },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const { sun_altitude, sun_azimuth, date, routes: routeResults } = batchRes.data;

      let bestCoords = null;
      let bestSegments = null;
      let bestScore = -1;
      let bestIndex = 0;

      allCoords.forEach((coords, i) => {
        const score = scoreRouteFromShadow(routeResults[i].segments, preference);
        if (score > bestScore) {
          bestScore = score;
          bestCoords = coords;
          bestSegments = routeResults[i].segments;
          bestIndex = i;
        }
      });

      if (bestCoords) {
        const leg = result.routes[bestIndex].legs[0];
        setRouteStats({ distance: leg.distance.text, duration: leg.duration.text });
        setSunData({ sun_altitude, sun_azimuth, date });
        drawRoute(mapRef.current, polylinesRef, bestCoords, bestSegments, sun_altitude);

        const midpoint = { lat: midLat, lng: midLng };
        if (!weatherLocationRef.current || roughDistanceKm(midpoint, weatherLocationRef.current) > 20) {
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
    if (!saveForm?.name?.trim()) { setSaveError("Name is required."); return; }
    setSaveError(null);
    try {
      const token = localStorage.getItem("token");
      await axios.post(
        "http://localhost:8000/routes",
        {
          name: saveForm.name.trim(),
          description: saveForm.description?.trim() || null,
          start_lat: start.lat, start_lng: start.lng,
          end_lat: end.lat, end_lng: end.lng,
          start_address: startAddress.split(",")[0].trim() || null,
          end_address: endAddress.split(",")[0].trim() || null,
        },
        { headers: { Authorization: `Bearer ${token}` } }
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
    clearPolylines(polylinesRef);
    if (weatherLocationRef.current) fetchWeather(weatherLocationRef.current.lat, weatherLocationRef.current.lng);
  }

  if (!isLoaded) return <p>Loading map...</p>;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Sun / Shade toggle */}
      <div style={{ marginBottom: "8px", display: "flex", alignItems: "center", gap: "10px" }}>
        <span style={{ fontSize: "0.88em", fontWeight: 600, color: preference === "sun" ? "#3D2C00" : "#A0A0A0" }}><FontAwesomeIcon icon={faSun} /> Sun</span>
        <div
          onClick={togglePreference}
          style={{
            width: "48px",
            height: "26px",
            borderRadius: "13px",
            background: preference === "sun" ? "#FFD600" : "#A8C4CC",
            position: "relative",
            cursor: "pointer",
            transition: "background 0.25s",
            boxShadow: "inset 0 1px 3px rgba(0,0,0,0.12)",
          }}
        >
          <div style={{
            width: "20px",
            height: "20px",
            borderRadius: "50%",
            background: "white",
            position: "absolute",
            top: "3px",
            left: preference === "sun" ? "3px" : "25px",
            transition: "left 0.25s",
            boxShadow: "0 1px 4px rgba(0,0,0,0.18)",
          }} />
        </div>
        <span style={{ fontSize: "0.88em", fontWeight: 600, color: preference === "shade" ? "#3D2C00" : "#A0A0A0" }}><FontAwesomeIcon icon={faCloudSun} /> Shade</span>
      </div>

      {/* Address inputs + action buttons (3 columns) */}
      <div style={{ marginBottom: "8px", display: "flex", gap: "10px", alignItems: "flex-start" }}>
        <div style={{ flex: "0 0 50%", display: "flex", flexDirection: "column", gap: "6px" }}>
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
              style={{ fontSize: "11px", padding: "2px 8px", width: "fit-content", display: "flex", alignItems: "center", gap: "5px" }}
            >
              <FontAwesomeIcon icon={faLocationCrosshairs} /> Use my location
            </button>
          )}
          <Autocomplete
            onLoad={(a) => { endAutocompleteRef.current = a; }}
            onPlaceChanged={() => handlePlaceSelected("end")}
          >
            <input
              type="text"
              value={endAddress}
              onChange={(e) => { setEndAddress(e.target.value); setSavedRouteName(null); setRouteSaved(false); }}
              placeholder="End address (or click map)"
            />
          </Autocomplete>
        </div>
        {/* Column 2: Plan Route + Reset */}
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          {planning
            ? <div className="planning-dots"><span className="planning-label">planning</span><span>•</span><span>•</span><span>•</span></div>
            : start && end && <button onClick={planRoute}>Plan Route</button>
          }
          {start && !planning && <button onClick={reset}>Reset</button>}
        </div>
        {/* Save Route button / form + routeStats — right-aligned */}
        <div style={{ marginLeft: "auto", display: "flex", flexDirection: "column", gap: "6px", alignItems: "flex-end" }}>
          {sunData && !saveForm && !routeSaved && (
            <button onClick={() => setSaveForm({ name: "", description: "" })}>Save Route</button>
          )}
          {saveForm && (
            <div style={{ display: "flex", gap: "6px", alignItems: "flex-start" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
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
                {saveError && <p style={{ color: "#FF5A3C", margin: 0, fontSize: "0.82em", fontWeight: 700 }}>{saveError}</p>}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                <button onClick={saveRoute}>Save</button>
                <button onClick={() => { setSaveForm(null); setSaveError(null); }}>Cancel</button>
              </div>
            </div>
          )}
        </div>
      </div>

      {savedRouteName && (
        <div style={{ margin: "0 0 6px" }}>
          <span style={{ fontSize: "13px", color: "#5A8F5A", fontWeight: 600 }}><FontAwesomeIcon icon={faHeart} /> {savedRouteName}</span>
        </div>
      )}

      {error && (
        <div style={{
          marginBottom: "8px", padding: "10px 14px", borderRadius: "12px",
          background: "#FFF0ED", border: "2px solid #FF5A3C",
          boxShadow: "3px 3px 0 #FF5A3C", display: "flex", alignItems: "center", gap: "8px",
        }}>
          <FontAwesomeIcon icon={faTriangleExclamation} style={{ color: "#FF5A3C", fontSize: "1.1em" }} />
          <span style={{ color: "#C0392B", fontWeight: 700, fontSize: "0.88em" }}>{error}</span>
        </div>
      )}

      {/* Map — fills remaining height */}
      <div style={{ flex: 1, minHeight: 0, position: "relative" }}>
        {routeStats && (
          <span style={{
            position: "absolute", top: "-22px", right: 0,
            fontSize: "12px", color: "#A87500", fontWeight: 500, whiteSpace: "nowrap",
          }}>
            Approx. {routeStats.distance} · {routeStats.duration} walk
          </span>
        )}
        <div className="map-wrapper" style={{ height: "100%", flex: "none" }}>
        <div ref={containerRef} style={{ height: "100%", width: "100%" }} />
        {sunData && (
          <div style={{
            position: "absolute", bottom: "10px", left: "10px",
            display: "flex", flexDirection: "column", gap: "6px", alignItems: "flex-start",
          }}>
            <div style={{
              background: "rgba(255, 253, 240, 0.95)", padding: "5px 12px",
              borderRadius: "20px", display: "flex", gap: "14px", fontSize: "12px",
              border: "1.5px solid #FFE082", boxShadow: "0 2px 8px rgba(255,193,7,0.15)",
              fontWeight: 500, color: "#3D2C00",
            }}>
              <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                <span style={{ width: 14, height: 4, background: "#FFD700", display: "inline-block", borderRadius: 2 }} />
                Sunny
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                <span style={{ width: 14, height: 4, background: "#888888", display: "inline-block", borderRadius: 2 }} />
                Shaded
              </span>
            </div>
          </div>
        )}
        {weather && (
          <div style={{
            position: "absolute", top: "10px", right: "10px",
            background: "rgba(255, 253, 240, 0.95)", padding: "6px 12px",
            borderRadius: "20px", display: "flex", alignItems: "center", gap: "8px",
            fontSize: "12px", fontWeight: 500, color: "#3D2C00",
            border: "1.5px solid #FFE082", boxShadow: "0 2px 8px rgba(255,193,7,0.15)",
          }}>
            {weather.icon_url && <img src={weather.icon_url} alt={weather.condition || ""} style={{ width: 20, height: 20 }} />}
            {weather.temperature != null && <span>{Math.round(weather.temperature)}°C</span>}
            {weather.uv_index != null && <span style={{ color: "#A87500" }}>UV {weather.uv_index}</span>}
            {weather.uv_index >= 6 && preference === "sun" && (
              <span style={{ color: "#C0392B", fontWeight: 700 }}>sunscreen!</span>
            )}
          </div>
        )}
        </div>
      </div>

    </div>
  );
}

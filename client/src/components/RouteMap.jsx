import { useState, useCallback, useEffect, useRef } from "react";
import { GoogleMap, useLoadScript, Marker, Autocomplete } from "@react-google-maps/api";
import axios from "axios";

const MAP_CENTER = { lat: 51.505, lng: -0.09 };
const MAP_STYLE = { height: "500px", width: "100%" };
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
    let color;
    if (sunAltitude <= 0) {
      color = "#888888";
    } else {
      color = seg.shaded ? "#888888" : "#FFD700";
    }

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

  const mapRef = useRef(null);
  const polylinesRef = useRef([]);
  const startAutocompleteRef = useRef(null);
  const endAutocompleteRef = useRef(null);

  const [preference, setPreference] = useState("sun");
  const [start, setStart] = useState(null);
  const [end, setEnd] = useState(null);
  const [startAddress, setStartAddress] = useState("");
  const [endAddress, setEndAddress] = useState("");
  const [sunData, setSunData] = useState(null);
  const [error, setError] = useState(null);
  const [is3D, setIs3D] = useState(false);

  async function reverseGeocode(lat, lng) {
    const geocoder = new window.google.maps.Geocoder();
    const result = await geocoder.geocode({ location: { lat, lng } });
    return result.results[0]?.formatted_address || "";
  }

  useEffect(() => {
    clearPolylines(polylinesRef);
  }, []);

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
    } else {
      setEnd(coords);
      setEndAddress(address);
    }
    mapRef.current?.panTo(coords);
  }

  const handleMapClick = useCallback(async (e) => {
    const coords = { lat: e.latLng.lat(), lng: e.latLng.lng() };
    const address = await reverseGeocode(coords.lat, coords.lng);
    if (!start) {
      setStart(coords);
      setStartAddress(address);
    } else if (!end) {
      setEnd(coords);
      setEndAddress(address);
    }
  }, [start, end]);

  async function planRoute() {
    setError(null);
    setSunData(null);
    clearPolylines(polylinesRef);
    try {
      const directionsService = new window.google.maps.DirectionsService();
      const result = await directionsService.route({
        origin: start,
        destination: end,
        travelMode: window.google.maps.TravelMode.WALKING,
        provideRouteAlternatives: true,
      });

      const token = localStorage.getItem("token");
      const datetime = new Date().toISOString();
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

      allCoords.forEach((coords, i) => {
        const score = scoreRouteFromShadow(routeResults[i].segments, preference);
        if (score > bestScore) {
          bestScore = score;
          bestCoords = coords;
          bestSegments = routeResults[i].segments;
        }
      });

      if (bestCoords) {
        setSunData({ sun_altitude, sun_azimuth, date });
        drawRoute(mapRef.current, polylinesRef, bestCoords, bestSegments, sun_altitude);
      }
    } catch {
      setError("Could not fetch route. Please try again.");
    }
  }

  function toggle3D() {
    const next = !is3D;
    setIs3D(next);
    if (mapRef.current) {
      mapRef.current.setMapTypeId(next ? "hybrid" : "roadmap");
      mapRef.current.setTilt(next ? 45 : 0);
    }
  }

  function reset() {
    setStart(null);
    setEnd(null);
    setStartAddress("");
    setEndAddress("");
    setSunData(null);
    setError(null);
    clearPolylines(polylinesRef);
  }

  if (!isLoaded) return <p>Loading map...</p>;

  return (
    <div>
      {/* Sun / Shade toggle */}
      <div style={{ marginBottom: "10px", display: "flex", alignItems: "center", gap: "10px" }}>
        <span>☀️ Sun</span>
        <div
          onClick={togglePreference}
          style={{
            width: "48px",
            height: "26px",
            borderRadius: "13px",
            background: preference === "sun" ? "#FFD700" : "#6B8FA3",
            position: "relative",
            cursor: "pointer",
            transition: "background 0.2s",
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
            transition: "left 0.2s",
          }} />
        </div>
        <span>🌥 Shade</span>
      </div>

      {/* Address inputs */}
      <div style={{ marginBottom: "10px", display: "flex", flexDirection: "column", gap: "6px" }}>
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
            }}
            placeholder="Start address (or click map)"
            style={{ width: "100%", padding: "6px 10px", boxSizing: "border-box" }}
          />
        </Autocomplete>
        <Autocomplete
          onLoad={(a) => { endAutocompleteRef.current = a; }}
          onPlaceChanged={() => handlePlaceSelected("end")}
        >
          <input
            type="text"
            value={endAddress}
            onChange={(e) => setEndAddress(e.target.value)}
            placeholder="End address (or click map)"
            style={{ width: "100%", padding: "6px 10px", boxSizing: "border-box" }}
          />
        </Autocomplete>
      </div>

      <GoogleMap
        zoom={13}
        center={MAP_CENTER}
        mapContainerStyle={MAP_STYLE}
        onClick={handleMapClick}
        onLoad={(map) => { mapRef.current = map; }}
      >
        {start && <Marker position={start} />}
        {end && <Marker position={end} />}
      </GoogleMap>

      <div style={{ marginTop: "10px", display: "flex", gap: "10px" }}>
        {start && end && <button onClick={planRoute}>Plan Route</button>}
        {start && <button onClick={reset}>Reset</button>}
        <button onClick={toggle3D}>{is3D ? "2D" : "3D Buildings"}</button>
      </div>

      {sunData && (
        <div style={{ marginTop: "8px", display: "flex", gap: "16px", fontSize: "14px" }}>
          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span style={{ width: 16, height: 4, background: "#FFD700", display: "inline-block" }} />
            Sunny
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span style={{ width: 16, height: 4, background: "#888888", display: "inline-block" }} />
            Shaded
          </span>
        </div>
      )}

      {error && <p style={{ color: "red" }}>{error}</p>}
    </div>
  );
}

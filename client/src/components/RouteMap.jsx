import { useState, useCallback } from "react";
import { GoogleMap, useLoadScript, Marker, Polyline } from "@react-google-maps/api";
import axios from "axios";

const MAP_CENTER = { lat: 51.505, lng: -0.09 };
const MAP_STYLE = { height: "500px", width: "100%" };
const API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

function getSegmentBearing(a, b) {
  const lat1 = (a[0] * Math.PI) / 180;
  const lat2 = (b[0] * Math.PI) / 180;
  const dLng = ((b[1] - a[1]) * Math.PI) / 180;
  const x = Math.sin(dLng) * Math.cos(lat2);
  const y = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng);
  return ((Math.atan2(x, y) * 180) / Math.PI + 360) % 360;
}

function getSunExposure(segmentBearing, sunAzimuth) {
  const diff = ((sunAzimuth - segmentBearing) * Math.PI) / 180;
  return Math.abs(Math.cos(diff));
}

function getSegmentColor(sunAltitude, exposure) {
  if (sunAltitude <= 0) return "#888888";
  if (exposure > 0.5) return "#FFD700";
  if (exposure >= 0.2) return "#FFA500";
  return "#6B8FA3";
}

export default function RouteMap() {
  const { isLoaded } = useLoadScript({ googleMapsApiKey: API_KEY });

  const [start, setStart] = useState(null);
  const [end, setEnd] = useState(null);
  const [route, setRoute] = useState(null);
  const [sunData, setSunData] = useState(null);
  const [error, setError] = useState(null);

  const handleMapClick = useCallback((e) => {
    const coords = { lat: e.latLng.lat(), lng: e.latLng.lng() };
    if (!start) {
      setStart(coords);
    } else if (!end) {
      setEnd(coords);
    }
  }, [start, end]);

  async function planRoute() {
    setError(null);
    setSunData(null);
    try {
      const directionsService = new window.google.maps.DirectionsService();
      const result = await directionsService.route({
        origin: start,
        destination: end,
        travelMode: window.google.maps.TravelMode.WALKING,
      });

      const coords = result.routes[0].overview_path.map((p) => [p.lat(), p.lng()]);
      setRoute(coords);

      const token = localStorage.getItem("token");
      const sunRes = await axios.post(
        "http://localhost:8000/sun/analyze",
        { coordinates: coords, datetime: new Date().toISOString() },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setSunData(sunRes.data);
    } catch {
      setError("Could not fetch route. Please try again.");
    }
  }

  function reset() {
    setStart(null);
    setEnd(null);
    setRoute(null);
    setSunData(null);
    setError(null);
  }

  const instruction = !start
    ? "Click on the map to set your start point"
    : !end
    ? "Now click to set your end point"
    : "Ready — click Plan Route";

  if (!isLoaded) return <p>Loading map...</p>;

  return (
    <div>
      <p>{instruction}</p>

      <GoogleMap
        zoom={13}
        center={MAP_CENTER}
        mapContainerStyle={MAP_STYLE}
        onClick={handleMapClick}
      >
        {start && <Marker position={start} />}
        {end && <Marker position={end} />}

        {/* Blue fallback while sun data is loading */}
        {route && !sunData && (
          <Polyline
            path={route.map(([lat, lng]) => ({ lat, lng }))}
            options={{ strokeColor: "blue", strokeWeight: 4 }}
          />
        )}

        {/* Colored segments once sun data is available */}
        {route && sunData &&
          route.slice(0, -1).map((point, i) => {
            const bearing = getSegmentBearing(point, route[i + 1]);
            const exposure = getSunExposure(bearing, sunData.sun_azimuth);
            const color = getSegmentColor(sunData.sun_altitude, exposure);
            return (
              <Polyline
                key={i}
                path={[
                  { lat: point[0], lng: point[1] },
                  { lat: route[i + 1][0], lng: route[i + 1][1] },
                ]}
                options={{ strokeColor: color, strokeWeight: 4 }}
              />
            );
          })
        }
      </GoogleMap>

      <div style={{ marginTop: "10px", display: "flex", gap: "10px" }}>
        {start && end && <button onClick={planRoute}>Plan Route</button>}
        {start && <button onClick={reset}>Reset</button>}
      </div>

      {sunData && (
        <div style={{ marginTop: "8px", display: "flex", gap: "16px", fontSize: "14px" }}>
          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span style={{ width: 16, height: 4, background: "#FFD700", display: "inline-block" }} />
            Sunny
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span style={{ width: 16, height: 4, background: "#FFA500", display: "inline-block" }} />
            Partial
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span style={{ width: 16, height: 4, background: "#6B8FA3", display: "inline-block" }} />
            Shaded
          </span>
        </div>
      )}

      {error && <p style={{ color: "red" }}>{error}</p>}
    </div>
  );
}

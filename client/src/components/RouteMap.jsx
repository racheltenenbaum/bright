import { useState } from "react";
import { MapContainer, TileLayer, Marker, Polyline, useMapEvents } from "react-leaflet";
import L from "leaflet";
import axios from "axios";
import "leaflet/dist/leaflet.css";

// Vite doesn't bundle Leaflet's marker images automatically — this fixes broken marker icons
import markerIconUrl from "leaflet/dist/images/marker-icon.png";
import markerShadowUrl from "leaflet/dist/images/marker-shadow.png";

const defaultIcon = L.icon({
  iconUrl: markerIconUrl,
  shadowUrl: markerShadowUrl,
  iconAnchor: [12, 41],
});
L.Marker.prototype.options.icon = defaultIcon;

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

function ClickHandler({ onMapClick }) {
  useMapEvents({
    click(e) {
      onMapClick(e.latlng);
    },
  });
  return null;
}

export default function RouteMap() {
  const [start, setStart] = useState(null);
  const [end, setEnd] = useState(null);
  const [route, setRoute] = useState(null);
  const [sunData, setSunData] = useState(null);
  const [error, setError] = useState(null);

  function handleMapClick(latlng) {
    if (!start) {
      setStart(latlng);
    } else if (!end) {
      setEnd(latlng);
    }
  }

  async function planRoute() {
    setError(null);
    setSunData(null);
    try {
      const osrmUrl = `https://router.project-osrm.org/route/v1/driving/${start.lng},${start.lat};${end.lng},${end.lat}?overview=full&geometries=geojson`;
      const res = await fetch(osrmUrl);
      const data = await res.json();
      const coords = data.routes[0].geometry.coordinates.map(([lng, lat]) => [lat, lng]);
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

  return (
    <div>
      <p>{instruction}</p>

      <MapContainer center={[51.505, -0.09]} zoom={13} style={{ height: "500px", width: "100%" }}>
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        />
        <ClickHandler onMapClick={handleMapClick} />
        {start && <Marker position={start} />}
        {end && <Marker position={end} />}

        {/* Blue fallback while sun data is loading */}
        {route && !sunData && <Polyline positions={route} color="blue" weight={4} />}

        {/* Colored segments once sun data is available */}
        {route && sunData &&
          route.slice(0, -1).map((point, i) => {
            const bearing = getSegmentBearing(point, route[i + 1]);
            const exposure = getSunExposure(bearing, sunData.sun_azimuth);
            const color = getSegmentColor(sunData.sun_altitude, exposure);
            return (
              <Polyline key={i} positions={[point, route[i + 1]]} color={color} weight={4} />
            );
          })
        }
      </MapContainer>

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

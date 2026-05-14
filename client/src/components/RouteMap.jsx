import { useState } from "react";
import { MapContainer, TileLayer, Marker, Polyline, useMapEvents } from "react-leaflet";
import L from "leaflet";
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
    try {
      const url = `https://router.project-osrm.org/route/v1/driving/${start.lng},${start.lat};${end.lng},${end.lat}?overview=full&geometries=geojson`;
      const res = await fetch(url);
      const data = await res.json();
      const coords = data.routes[0].geometry.coordinates.map(([lng, lat]) => [lat, lng]);
      setRoute(coords);
    } catch {
      setError("Could not fetch route. Please try again.");
    }
  }

  function reset() {
    setStart(null);
    setEnd(null);
    setRoute(null);
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
        {route && <Polyline positions={route} color="blue" weight={4} />}
      </MapContainer>

      <div style={{ marginTop: "10px", display: "flex", gap: "10px" }}>
        {start && end && <button onClick={planRoute}>Plan Route</button>}
        {start && <button onClick={reset}>Reset</button>}
      </div>

      {error && <p style={{ color: "red" }}>{error}</p>}
    </div>
  );
}

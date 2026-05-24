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
  faShareNodes,
} from "@fortawesome/free-solid-svg-icons";
import { Share } from "@capacitor/share";
import { spotIcon, SPOT_ICONS } from "../pages/MySpotsPage";

const MAP_CENTER = { lat: 51.505, lng: -0.09 };
const API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

const LIBRARIES = ["places"];

function extractCity(components) {
  if (!components) return "";
  for (const type of ["locality", "postal_town", "administrative_area_level_2", "administrative_area_level_1"]) {
    const comp = components.find((c) => c.types.includes(type));
    if (comp) return comp.long_name;
  }
  return "";
}

function iconFromPlaceTypes(types) {
  if (!types?.length) return "faMapPin";
  if (types.includes("cafe")) return "faMugHot";
  if (types.includes("bar") || types.includes("night_club")) return "faBeerMugEmpty";
  if (types.includes("bakery")) return "faBreadSlice";
  if (types.includes("restaurant") || types.includes("food")) return "faUtensils";
  if (types.includes("park") || types.includes("natural_feature")) return "faTree";
  if (types.includes("gym") || types.includes("health")) return "faDumbbell";
  if (types.includes("lodging")) return "faBed";
  if (types.includes("train_station") || types.includes("subway_station") || types.includes("transit_station")) return "faTrain";
  if (types.includes("airport")) return "faPlane";
  if (types.includes("university") || types.includes("school")) return "faGraduationCap";
  if (types.includes("library")) return "faBook";
  if (types.includes("shopping_mall") || types.includes("store") || types.includes("supermarket")) return "faShoppingCart";
  return "faMapPin";
}


function computeSunAltitude(lat, lng) {
  const now = new Date();
  const jd = now / 86400000 + 2440587.5;
  const n = jd - 2451545.0;
  const L = (280.46 + 0.9856474 * n) % 360;
  const g = ((357.528 + 0.9856003 * n) % 360) * Math.PI / 180;
  const lam = (L + 1.915 * Math.sin(g) + 0.02 * Math.sin(2 * g)) * Math.PI / 180;
  const obliquity = 23.439 * Math.PI / 180;
  const dec = Math.asin(Math.sin(obliquity) * Math.sin(lam));
  const ra = Math.atan2(Math.cos(obliquity) * Math.sin(lam), Math.cos(lam)) * (12 / Math.PI);
  const gmst = ((18.697374558 + 24.06570982441908 * n) % 24 + 24) % 24;
  const lha = (((gmst + lng / 15 - ra) % 24) + 24) % 24;
  const ha = lha * 15 * Math.PI / 180;
  const latRad = lat * Math.PI / 180;
  return Math.asin(Math.sin(latRad) * Math.sin(dec) + Math.cos(latRad) * Math.cos(dec) * Math.cos(ha)) * 180 / Math.PI;
}

function clearPolylines(ref) {
  ref.current.forEach((p) => p.setMap(null));
  ref.current = [];
}

function scoreRouteFromShadow(segments, preference) {
  const shadedCount = segments.filter((s) => s.shaded).length;
  return preference === "shade" ? shadedCount : segments.length - shadedCount;
}

function drawRoute(mapInstance, polylinesRef, coords, segments, sunAltitude, preference) {
  clearPolylines(polylinesRef);
  if (!mapInstance || !coords || !segments) return;

  coords.slice(0, -1).forEach((point, i) => {
    const seg = segments[i] ?? segments[segments.length - 1];
    let color;
    if (sunAltitude <= 0) {
      color = "#888888";
    } else if (preference === "shade") {
      color = seg.shaded ? "#5E8FAD" : "#C8D8E4";
    } else {
      color = seg.shaded ? "#C8C8A0" : "#FFD700";
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
  const sunCheckedRef = useRef(false);
  const weatherLocationRef = useRef(null);
  const startAutocompleteRef = useRef(null);
  const endAutocompleteRef = useRef(null);
  const placeNameAutocompleteRef = useRef(null);
  const locationBiasRef = useRef(null);
  const skipInitialPanRef = useRef(false);
  const autoCalculateRef = useRef(false);
  const currentLocationRef = useRef(null);

  // Refs for use inside map click listener (avoids stale closures)
  const startRef = useRef(null);
  const endRef = useRef(null);
  const sunDataRef = useRef(null);
  const modeRef = useRef("route");
  const placeMarkersRef = useRef([]);
  const placeMarkersMapRef = useRef({});
  const touchStartYRef = useRef(null);

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
  const [savedRouteId, setSavedRouteId] = useState(null);
  const [shareCopied, setShareCopied] = useState(false);
  const [routeStats, setRouteStats] = useState(null);
  const [routeCoords, setRouteCoords] = useState(null);
  const [routeSegments, setRouteSegments] = useState(null);
  const [goMode, setGoMode] = useState(false);
  const [goSegmentIdx, setGoSegmentIdx] = useState(0);
  const [planning, setPlanning] = useState(false);
  const [currentLocation, setCurrentLocation] = useState(null);
  const [weather, setWeather] = useState(null);
  const [spots, setSpots] = useState([]);
  const [mode, setMode] = useState("route");
  const [placeTypes, setPlaceTypes] = useState(["cafe"]);
  const [placesSearching, setPlacesSearching] = useState(false);
  const [placesSunAltitude, setPlacesSunAltitude] = useState(() => computeSunAltitude(MAP_CENTER.lat, MAP_CENTER.lng));
  const [selectedPlace, setSelectedPlace] = useState(null);
  const [placeDetails, setPlaceDetails] = useState(null);
  const [placeDetailsLoading, setPlaceDetailsLoading] = useState(false);
  const [placeSaveSuccess, setPlaceSaveSuccess] = useState(null);
  const [saveSpotModal, setSaveSpotModal] = useState(null); // null | { name, note, icon, place }
  const [saveSpotIconOpen, setSaveSpotIconOpen] = useState(false);
  const [saveSpotError, setSaveSpotError] = useState(null);
  const [showAllReviews, setShowAllReviews] = useState(false);
  const [panelExpanded, setPanelExpanded] = useState(false);
  const [selectedPlaceIsSunny, setSelectedPlaceIsSunny] = useState(null);
  const [placeNameQuery, setPlaceNameQuery] = useState("");

  startRef.current = start;
  endRef.current = end;
  sunDataRef.current = sunData;
  const isNighttime = placesSunAltitude <= 0;
  currentLocationRef.current = currentLocation;
  modeRef.current = mode;

  const PLACE_TYPE_OPTIONS = [
    { key: "cafe",       label: "Cafe" },
    { key: "restaurant", label: "Restaurant" },
    { key: "bar",        label: "Bar" },
    { key: "park",       label: "Park" },
  ];
  const PLACE_SPOT_ICON = { cafe: "faMugHot", restaurant: "faUtensils", bar: "faMugHot", park: "faTree" };

  const colors = isNighttime ? {
    accent:      "#3D6E8C",
    accentFaint: "#8AB0C8",
    accentGlow:  "rgba(61,110,140,0.15)",
    text:        "#1A2F40",
    subtext:     "#2D5070",
    surface:     "rgba(184,202,214,0.95)",
  } : preference === "shade" ? {
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

  // Fetch saved spots for quick-pick chips
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return;
    api.get("/spots", { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => setSpots(res.data))
      .catch(() => {});
  }, []);

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

  // Sync body theme class with preference / nighttime
  useEffect(() => {
    document.body.classList.toggle("shade-mode", !isNighttime && preference === "shade");
    document.body.classList.toggle("night-mode", isNighttime);
    return () => { document.body.classList.remove("shade-mode"); document.body.classList.remove("night-mode"); };
  }, [preference, isNighttime]); // eslint-disable-line react-hooks/exhaustive-deps


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
      styles: [],
    });

    // Auto-open a spot navigated from My Spots
    const spot = location.state?.spot;
    if (spot) {
      skipInitialPanRef.current = true;
      setMode("places");
      modeRef.current = "places";
      mapRef.current.setCenter({ lat: spot.lat, lng: spot.lng });
      mapRef.current.setZoom(16);
      const syntheticPlace = {
        place_id: spot.place_id || `spot-${spot.id}`,
        name: spot.name,
        address: spot.address,
        lat: spot.lat,
        lng: spot.lng,
        is_sunny: null,
      };
      renderPlaceMarkers([syntheticPlace]);
      setSelectedPlace(syntheticPlace);
      window.history.replaceState({}, document.title);
      const token = localStorage.getItem("token");
      api.post("/places/sun-check", { lat: spot.lat, lng: spot.lng }, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => {
          setSelectedPlaceIsSunny(res.data.is_sunny);
          setPlacesSunAltitude(res.data.sun_altitude);
        })
        .catch(() => {});
    }
  }, [isLoaded]); // eslint-disable-line react-hooks/exhaustive-deps

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
        if (!skipInitialPanRef.current) {
          mapRef.current.panTo({ lat, lng });
        }
        initialPanDone = true;
        fetchWeather(lat, lng);
      }
      if (!sunCheckedRef.current) {
        sunCheckedRef.current = true;
        setPlacesSunAltitude(computeSunAltitude(lat, lng));
        const bias = new window.google.maps.LatLngBounds(
          { lat: lat - 0.15, lng: lng - 0.15 },
          { lat: lat + 0.15, lng: lng + 0.15 },
        );
        locationBiasRef.current = bias;
        startAutocompleteRef.current?.setBounds(bias);
        endAutocompleteRef.current?.setBounds(bias);
        placeNameAutocompleteRef.current?.setBounds(bias);
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
      if (modeRef.current === "places") {
        setSelectedPlace(null);
        return;
      }
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
      const pinColor = preference === "shade" ? "#7AB3CF" : "#FFD600";
      startMarkerRef.current = new window.google.maps.Marker({
        position: start,
        map: mapRef.current,
        icon: {
          url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="24" height="36" viewBox="0 0 24 36"><path fill="${pinColor}" stroke="#fff" stroke-width="1.5" d="M12 0C5.4 0 0 5.4 0 12c0 9 12 24 12 24S24 21 24 12C24 5.4 18.6 0 12 0z"/><circle cx="12" cy="12" r="5" fill="white"/></svg>`)}`,
          scaledSize: new window.google.maps.Size(24, 36),
          anchor: new window.google.maps.Point(12, 36),
        },
      });
    }
  }, [start, isLoaded, preference]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync end marker
  useEffect(() => {
    if (!mapRef.current) return;
    if (endMarkerRef.current) {
      endMarkerRef.current.setMap(null);
      endMarkerRef.current = null;
    }
    if (end) {
      const pinColor = preference === "shade" ? "#4A7090" : "#f5ae0a";
      endMarkerRef.current = new window.google.maps.Marker({
        position: end,
        map: mapRef.current,
        icon: {
          url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="24" height="36" viewBox="0 0 24 36"><path fill="${pinColor}" stroke="#fff" stroke-width="1.5" d="M12 0C5.4 0 0 5.4 0 12c0 9 12 24 12 24S24 21 24 12C24 5.4 18.6 0 12 0z"/><circle cx="12" cy="12" r="5" fill="white"/></svg>`)}`,
          scaledSize: new window.google.maps.Size(24, 36),
          anchor: new window.google.maps.Point(12, 36),
        },
      });
    }
  }, [end, isLoaded, preference]); // eslint-disable-line react-hooks/exhaustive-deps

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
      setPlacesSunAltitude(r.data.sun_altitude);
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
          preference,
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
      const res = await api.post(
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
          route_path: routeCoords
            ? JSON.stringify(
                routeCoords.filter((_, i) => i % Math.max(1, Math.floor(routeCoords.length / 60)) === 0)
              )
            : null,
        },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setSavedRouteId(res.data.id);
      setSavedRouteName(saveForm.name.trim());
      setSaveForm(null);
      setRouteSaved(true);
    } catch {
      setSaveError("Could not save route. Please try again.");
    }
  }

  async function shareRoute() {
    try {
      const token = localStorage.getItem("token");
      const res = await api.post(`/routes/${savedRouteId}/share`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const url = `${import.meta.env.VITE_APP_URL || window.location.origin}/share/${res.data.share_token}`;
      const canShare = (await Share.canShare()).value;
      if (canShare) {
        await Share.share({ title: "Check out this route on bright", url, dialogTitle: "Share route" });
      } else {
        await navigator.clipboard.writeText(url);
        setShareCopied(true);
        setTimeout(() => setShareCopied(false), 2000);
      }
    } catch { /* ignore */ }
  }

  // Fetch full place details whenever a marker is selected
  useEffect(() => {
    if (!selectedPlace) { setPlaceDetails(null); setSelectedPlaceIsSunny(null); return; }
    setPlaceDetails(null);
    setSelectedPlaceIsSunny(null);
    setShowAllReviews(false);
    setPanelExpanded(false);
    setPlaceDetailsLoading(true);
    const token = localStorage.getItem("token");
    api.get(`/places/${selectedPlace.place_id}/details`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => setPlaceDetails(res.data))
      .catch(() => {})
      .finally(() => setPlaceDetailsLoading(false));
  }, [selectedPlace]); // eslint-disable-line react-hooks/exhaustive-deps

  // Update pin size/colour when selection changes
  useEffect(() => {
    Object.values(placeMarkersMapRef.current).forEach(({ marker, place }) => {
      const selected = selectedPlace?.place_id === place.place_id;
      const color = selected
        ? (isNighttime ? "#2D5070" : (place.is_sunny ? "#D4940A" : "#3D6E8C"))
        : (isNighttime ? "#3D6E8C" : (place.is_sunny ? "#FFD600" : "#5E8FAD"));
      const w = selected ? 34 : 28;
      const h = selected ? 49 : 40;
      marker.setIcon({
        url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(
          `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 24 36">` +
          `<path fill="${color}" stroke="#fff" stroke-width="1.5" d="M12 0C5.4 0 0 5.4 0 12c0 9 12 24 12 24S24 21 24 12C24 5.4 18.6 0 12 0z"/>` +
          `<circle cx="12" cy="12" r="5" fill="white"/></svg>`
        )}`,
        scaledSize: new window.google.maps.Size(w, h),
        anchor: new window.google.maps.Point(w / 2, h),
      });
      marker.setZIndex(selected ? 3 : 2);
    });
  }, [selectedPlace]); // eslint-disable-line react-hooks/exhaustive-deps

  function clearPlaceMarkers() {
    placeMarkersRef.current.forEach((m) => m.setMap(null));
    placeMarkersRef.current = [];
    placeMarkersMapRef.current = {};
  }

  function renderPlaceMarkers(places) {
    clearPlaceMarkers();
    places.forEach((place) => {
      const pinColor = isNighttime ? "#3D6E8C" : (place.is_sunny ? "#FFD600" : "#5E8FAD");
      const pin = encodeURIComponent(
        `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="40" viewBox="0 0 24 36">` +
        `<path fill="${pinColor}" stroke="#fff" stroke-width="1.5" d="M12 0C5.4 0 0 5.4 0 12c0 9 12 24 12 24S24 21 24 12C24 5.4 18.6 0 12 0z"/>` +
        `<circle cx="12" cy="12" r="5" fill="white"/></svg>`
      );
      const marker = new window.google.maps.Marker({
        position: { lat: place.lat, lng: place.lng },
        map: mapRef.current,
        icon: {
          url: `data:image/svg+xml;charset=UTF-8,${pin}`,
          scaledSize: new window.google.maps.Size(28, 40),
          anchor: new window.google.maps.Point(14, 40),
        },
        title: place.name,
        zIndex: 2,
      });
      marker.addListener("click", () => {
        setSelectedPlace(place);
        mapRef.current?.panTo({ lat: place.lat, lng: place.lng });
      });
      placeMarkersRef.current.push(marker);
      placeMarkersMapRef.current[place.place_id] = { marker, place };
    });
  }

  async function searchPlaces() {
    if (!mapRef.current) return;
    const center = {
      lat: mapRef.current.getCenter().lat(),
      lng: mapRef.current.getCenter().lng(),
    };

    // Compute radius to cover the visible map viewport
    const viewportBounds = mapRef.current.getBounds();
    let radius = 500;
    if (viewportBounds) {
      const ne = viewportBounds.getNorthEast();
      const dLat = Math.abs(ne.lat() - center.lat) * 111000;
      const dLng = Math.abs(ne.lng() - center.lng) * 111000 * Math.cos(center.lat * Math.PI / 180);
      radius = Math.round(Math.sqrt(dLat * dLat + dLng * dLng));
    }
    radius = Math.min(radius, 50000);

    setError(null);
    setSelectedPlace(null);
    setPlacesSearching(true);
    clearPlaceMarkers();

    try {
      const token = localStorage.getItem("token");
      const body = { lat: center.lat, lng: center.lng, radius, preference, types: placeTypes };
      let res = await api.post("/places/search", body, { headers: { Authorization: `Bearer ${token}` } });
      let places = res.data.places;

      // Auto-expand once if no results and there's room to grow
      if (places.length === 0 && radius < 50000) {
        const expanded = Math.min(radius * 2, 50000);
        res = await api.post("/places/search", { ...body, radius: expanded }, { headers: { Authorization: `Bearer ${token}` } });
        places = res.data.places;
      }

      setPlacesSunAltitude(res.data.sun_altitude);
      renderPlaceMarkers(places);
      if (places.length === 0) {
        mapRef.current.setZoom(Math.max(mapRef.current.getZoom() - 1, 10));
      }
    } catch {
      setError("Could not search for places. Please try again.");
    } finally {
      setPlacesSearching(false);
    }
  }

  function openSaveSpotModal(place) {
    setSaveSpotModal({
      name: place.name,
      note: "",
      icon: PLACE_SPOT_ICON[place.type] || iconFromPlaceTypes(place.googleTypes) || "faMapPin",
      place,
      city: "",
    });
    new window.google.maps.Geocoder().geocode({ location: { lat: place.lat, lng: place.lng } }, (results) => {
      const city = extractCity(results?.[0]?.address_components);
      setSaveSpotModal((prev) => prev ? { ...prev, city } : prev);
    });
    setSaveSpotIconOpen(false);
    setSaveSpotError(null);
  }

  async function confirmSaveSpot() {
    if (!saveSpotModal) return;
    setSaveSpotError(null);
    try {
      const token = localStorage.getItem("token");
      const placeId = saveSpotModal.place.place_id;
      const savedPlaceId = placeId && !placeId.startsWith("spot-") ? placeId : null;
      const res = await api.post(
        "/spots",
        {
          name: saveSpotModal.name.trim() || saveSpotModal.place.name,
          address: saveSpotModal.place.address,
          lat: saveSpotModal.place.lat,
          lng: saveSpotModal.place.lng,
          icon: saveSpotModal.icon,
          city: saveSpotModal.city || "",
          description: saveSpotModal.note.trim() || null,
          place_id: savedPlaceId,
        },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setSpots((prev) => [...prev, res.data]);
      setPlaceSaveSuccess(saveSpotModal.place.place_id);
      setSaveSpotModal(null);
      setTimeout(() => setPlaceSaveSuccess(null), 2500);
    } catch {
      setSaveSpotError("Could not save spot.");
    }
  }

  async function handlePlaceNameSearch() {
    const place = placeNameAutocompleteRef.current?.getPlace();
    if (!place?.geometry) return;
    const lat = place.geometry.location.lat();
    const lng = place.geometry.location.lng();
    const syntheticPlace = {
      place_id: place.place_id,
      name: place.name || place.formatted_address?.split(",")[0] || "",
      address: place.formatted_address || "",
      lat,
      lng,
      is_sunny: null,
      type: null,
      googleTypes: place.types || [],
    };
    clearPlaceMarkers();
    renderPlaceMarkers([syntheticPlace]);
    setSelectedPlace(syntheticPlace);
    mapRef.current?.setCenter({ lat, lng });
    mapRef.current?.setZoom(16);
    const token = localStorage.getItem("token");
    api.post("/places/sun-check", { lat, lng }, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => { setSelectedPlaceIsSunny(res.data.is_sunny); setPlacesSunAltitude(res.data.sun_altitude); })
      .catch(() => {});
  }

  function planRouteToPlace(place) {
    clearPlaceMarkers();
    setSelectedPlace(null);
    setShowAllReviews(false);
    setPanelExpanded(false);
    setPlaceSaveSuccess(null);
    setError(null);
    setMode("route");
    clearPolylines(polylinesRef);
    setSunData(null);
    setEnd({ lat: place.lat, lng: place.lng });
    setEndAddress(place.address || place.name || "");
    setSavedRouteName(null);
    setRouteSaved(false);
    if (currentLocationRef.current) {
      autoCalculateRef.current = true;
      setStart(currentLocationRef.current);
      new window.google.maps.Geocoder().geocode(
        { location: currentLocationRef.current },
        (results) => setStartAddress(results?.[0]?.formatted_address || "My location"),
      );
    }
  }

  function switchMode(newMode) {
    if (newMode === mode) return;
    if (newMode === "places") {
      clearPolylines(polylinesRef);
      setStart(null); setEnd(null);
      setStartAddress(""); setEndAddress("");
      setSunData(null); setRouteStats(null);
      setRouteCoords(null); setRouteSegments(null);
      setRouteSaved(false); setSavedRouteName(null);
      setGoMode(false); setSaveForm(null);
    } else {
      clearPlaceMarkers();
      setSelectedPlace(null);
      setShowAllReviews(false);
      setPanelExpanded(false);
      setPlaceSaveSuccess(null);
      setPlaceNameQuery("");
    }
    setError(null);
    setMode(newMode);
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
    clearPlaceMarkers();
    setSelectedPlace(null);
    setPlaceDetails(null);
    setShowAllReviews(false);
    setPanelExpanded(false);
    setPlaceSaveSuccess(null);
    if (weatherLocationRef.current)
      fetchWeather(
        weatherLocationRef.current.lat,
        weatherLocationRef.current.lng,
      );
  }

  if (!isLoaded) return <p>Loading map...</p>;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Mode tabs: Plan Route | Find Places */}
      <div style={{ display: "flex", gap: "6px", marginBottom: "8px" }}>
        {["route", "places"].map((m) => (
          <button
            key={m}
            onClick={() => switchMode(m)}
            style={{
              flex: 1, fontSize: "0.82em", fontWeight: 700,
              padding: "0.45em 0",
              background: mode === m ? colors.accent : "transparent",
              color: mode === m ? colors.text : colors.subtext,
              border: `2px solid ${mode === m ? colors.accent : colors.accentFaint}`,
              borderRadius: "10px", cursor: "pointer", boxShadow: "none",
            }}
          >
            {m === "route" ? "Plan Route" : "Find Places"}
          </button>
        ))}
      </div>

      {/* Sun / Shade toggle + Reset — or after-sunset notice in places mode */}
      {mode === "places" && isNighttime ? (
        <div style={{ marginBottom: "8px", display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{ fontSize: "0.88em", color: colors.subtext }}>🌙 After sunset</span>
        </div>
      ) : (
        <div style={{ marginBottom: "8px", display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{ fontSize: "0.88em", fontWeight: 600, color: preference === "sun" ? colors.text : colors.subtext }}>
            <FontAwesomeIcon icon={faSun} /> Sun
          </span>
          <div
            onClick={togglePreference}
            style={{
              width: "48px", height: "26px", borderRadius: "13px",
              background: preference === "sun" ? "#FFD600" : colors.accent,
              position: "relative", cursor: "pointer",
              transition: "background 0.25s", boxShadow: "inset 0 1px 3px rgba(0,0,0,0.12)",
            }}
          >
            <div style={{
              width: "20px", height: "20px", borderRadius: "50%",
              background: "white", position: "absolute", top: "3px",
              left: preference === "sun" ? "3px" : "25px",
              transition: "left 0.25s", boxShadow: "0 1px 4px rgba(0,0,0,0.18)",
            }} />
          </div>
          <span style={{ fontSize: "0.88em", fontWeight: 600, color: preference === "shade" ? colors.text : colors.subtext }}>
            <FontAwesomeIcon icon={faCloudSun} /> Shade
          </span>
          {mode === "route" && (start && !planning) && (
            <button onClick={reset} style={{ marginLeft: "auto", fontSize: "0.75em", padding: "0.35em 0.9em" }}>Reset</button>
          )}
        </div>
      )}

      {/* Address inputs + action buttons — route mode only */}
      <div
        style={{
          marginBottom: "8px",
          display: mode === "route" ? "flex" : "none",
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
        {/* Spot chips — shown when start or end is empty */}
        {spots.length > 0 && (!start || !end) && !sunData && (
          <div style={{ display: "flex", gap: "6px", overflowX: "auto", paddingBottom: "2px" }}>
            {spots.map((spot) => (
              <button
                key={spot.id}
                onClick={() => {
                  const coords = { lat: spot.lat, lng: spot.lng };
                  if (!start) {
                    setStart(coords);
                    setStartAddress(spot.address);
                    clearPolylines(polylinesRef);
                    setSunData(null);
                    setSavedRouteName(null);
                    setRouteSaved(false);
                  } else {
                    setEnd(coords);
                    setEndAddress(spot.address);
                    setSavedRouteName(null);
                    setRouteSaved(false);
                  }
                  mapRef.current?.panTo(coords);
                }}
                style={{
                  display: "flex", alignItems: "center", gap: "5px",
                  padding: "4px 10px", borderRadius: "999px", whiteSpace: "nowrap",
                  fontSize: "0.75em", fontWeight: 700,
                  background: colors.accentGlow, border: `1.5px solid ${colors.accentFaint}`,
                  color: colors.text, flexShrink: 0, boxShadow: "none",
                }}
              >
                <FontAwesomeIcon icon={spotIcon(spot.icon)} style={{ fontSize: "11px" }} />
                {spot.name}
              </button>
            ))}
          </div>
        )}
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

      {/* Find Places panel — places mode only */}
      {mode === "places" && (
        <div style={{ marginBottom: "8px", display: "flex", flexDirection: "column", gap: "8px" }}>
          {/* Name search */}
          <Autocomplete
            onLoad={(a) => { placeNameAutocompleteRef.current = a; if (locationBiasRef.current) a.setBounds(locationBiasRef.current); }}
            onPlaceChanged={handlePlaceNameSearch}
          >
            <input
              type="text"
              placeholder="Search by name…"
              value={placeNameQuery}
              onChange={(e) => setPlaceNameQuery(e.target.value)}
            />
          </Autocomplete>

          {/* Place type chips */}
          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
            {PLACE_TYPE_OPTIONS.map(({ key, label }) => {
              const selected = placeTypes.includes(key);
              return (
                <button
                  key={key}
                  onClick={() =>
                    setPlaceTypes((prev) =>
                      prev.includes(key)
                        ? prev.length > 1 ? prev.filter((t) => t !== key) : prev
                        : [...prev, key]
                    )
                  }
                  style={{
                    fontSize: "0.78em", fontWeight: 700, padding: "0.35em 0.9em",
                    borderRadius: "999px", border: `2px solid ${selected ? colors.accent : colors.accentFaint}`,
                    background: selected ? colors.accentGlow : "transparent",
                    color: selected ? colors.text : colors.subtext,
                    cursor: "pointer", boxShadow: "none",
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>

          {/* Search button */}
          <button
            onClick={searchPlaces}
            disabled={placesSearching}
            style={{ fontWeight: 800, fontSize: "0.85em", padding: "0.4em 1.2em", alignSelf: "flex-end" }}
          >
            {placesSearching ? "Searching…" : "Search"}
          </button>

        </div>
      )}

      {(savedRouteName || routeStats || planning) && (
        <div style={{ margin: "0 0 6px", display: mode === "route" ? "flex" : "none", alignItems: "center", justifyContent: "space-between" }}>
          {savedRouteName && (
            <span style={{ fontSize: "13px", color: "#5A8F5A", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
              <FontAwesomeIcon icon={faHeart} /> {savedRouteName}
              <button
                onClick={shareRoute}
                style={{ background: "none", border: "none", cursor: "pointer", padding: "0 2px", boxShadow: "none", color: "#5A8F5A", fontSize: "13px" }}
                title="Share"
              >
                {shareCopied ? <span style={{ fontSize: "0.75em", fontWeight: 700 }}>Copied!</span> : <FontAwesomeIcon icon={faShareNodes} />}
              </button>
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
            background: isNighttime ? colors.surface : "#FFF0ED",
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
      <div style={{ flex: 1, minHeight: 0, position: "relative", overflow: "hidden" }}>
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
                      background: preference === "shade" ? "#5E8FAD" : "#FFD700",
                      display: "inline-block",
                      borderRadius: 2,
                    }}
                  />
                  {preference === "shade" ? "Shaded" : "Sunny"}
                </span>
                <span
                  style={{ display: "flex", alignItems: "center", gap: "4px" }}
                >
                  <span
                    style={{
                      width: 14,
                      height: 4,
                      background: preference === "shade" ? "#C8D8E4" : "#C8C8A0",
                      display: "inline-block",
                      borderRadius: 2,
                    }}
                  />
                  {preference === "shade" ? "Sunny" : "Shaded"}
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
          {selectedPlace && (
            <div
              onClick={!panelExpanded ? () => setPanelExpanded(true) : undefined}
              style={{
                position: "absolute", bottom: "20px", left: "50%", transform: "translateX(-50%)",
                background: colors.surface, borderRadius: "20px",
                border: `2px solid ${colors.accent}`, boxShadow: `0 4px 20px ${colors.accentGlow}`,
                zIndex: 10, width: "min(340px, 90vw)",
                height: panelExpanded ? "calc(100% - 44px)" : "118px",
                overflow: "hidden", display: "flex", flexDirection: "column",
                transition: "height 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
                cursor: panelExpanded ? "default" : "pointer",
              }}
            >
              {/* Drag handle */}
              <div
                onTouchStart={(e) => { touchStartYRef.current = e.touches[0].clientY; }}
                onTouchEnd={(e) => {
                  const delta = e.changedTouches[0].clientY - touchStartYRef.current;
                  if (delta < -40) setPanelExpanded(true);
                  else if (delta > 40) panelExpanded ? setPanelExpanded(false) : setSelectedPlace(null);
                }}
                style={{ display: "flex", justifyContent: "center", padding: "8px 0 4px", flexShrink: 0 }}
              >
                <div style={{ width: "36px", height: "4px", borderRadius: "2px", background: colors.accentFaint }} />
              </div>

              {/* Sticky header: always visible — name, compact preview, close */}
              <div
                onTouchStart={(e) => { touchStartYRef.current = e.touches[0].clientY; }}
                onTouchEnd={(e) => {
                  const delta = e.changedTouches[0].clientY - touchStartYRef.current;
                  if (delta < -40) setPanelExpanded(true);
                  else if (delta > 40) panelExpanded ? setPanelExpanded(false) : setSelectedPlace(null);
                }}
                style={{ padding: "0 16px 10px", display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexShrink: 0 }}
              >
                <div style={{ minWidth: 0, flex: 1 }}>
                  <strong style={{ fontSize: "0.95em", color: colors.text, display: "block",
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {selectedPlace.name}
                  </strong>
                  <div style={{ display: "flex", alignItems: "center", marginTop: "2px", gap: "6px" }}>
                    <span style={{ fontSize: "0.73em", color: colors.subtext,
                      overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1, minWidth: 0 }}>
                      {selectedPlace.address}{placeDetails?.postal_code ? `, ${placeDetails.postal_code}` : ""}
                    </span>
                    {(placeDetails?.rating ?? selectedPlace.rating) != null && (
                      <span style={{ fontSize: "0.73em", color: colors.text, fontWeight: 600, flexShrink: 0, whiteSpace: "nowrap" }}>
                        ★ {placeDetails?.rating ?? selectedPlace.rating}
                        {placeDetails?.user_ratings_total != null &&
                          <span style={{ fontWeight: 400, color: colors.subtext }}> ({placeDetails.user_ratings_total.toLocaleString()})</span>}
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); setSelectedPlace(null); }}
                  style={{ background: "none", border: "none", cursor: "pointer", fontSize: "1.1em",
                    color: colors.subtext, padding: "0 0 0 10px", boxShadow: "none", flexShrink: 0, lineHeight: 1, alignSelf: "flex-start" }}>
                  ×
                </button>
              </div>

              {/* Scrollable body — revealed on expand */}
              <div style={{ overflowY: "auto", flex: 1 }}>
                {/* Photo carousel */}
                {placeDetails?.photo_references?.length > 0 && (
                  <div style={{
                    display: "flex", gap: "6px", overflowX: "auto",
                    padding: "0 16px 10px", scrollbarWidth: "none", boxSizing: "border-box",
                  }}>
                    {placeDetails.photo_references.map((ref, i) => (
                      <img key={i}
                        src={`https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photo_reference=${ref}&key=${API_KEY}`}
                        alt=""
                        style={{ height: "110px", minWidth: "150px", width: "150px",
                          objectFit: "cover", borderRadius: "10px", flexShrink: 0 }}
                      />
                    ))}
                  </div>
                )}

                <div style={{ padding: "0 16px 14px" }}>
                  {/* Rating + price + open status + sun/shade */}
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px", flexWrap: "wrap" }}>
                    {(placeDetails?.rating ?? selectedPlace.rating) != null && (
                      <span style={{ fontSize: "0.8em", color: colors.text, fontWeight: 600 }}>
                        ★ {placeDetails?.rating ?? selectedPlace.rating}
                        {placeDetails?.user_ratings_total != null &&
                          <span style={{ fontWeight: 400, color: colors.subtext }}> ({placeDetails.user_ratings_total.toLocaleString()})</span>}
                      </span>
                    )}
                    {placeDetails?.price_level != null && (
                      <span style={{ fontSize: "0.76em", color: colors.subtext }}>{(placeDetails.currency_symbol || "$").repeat(placeDetails.price_level)}</span>
                    )}
                    {placeDetails?.open_now != null && (
                      <span style={{ fontSize: "0.76em", fontWeight: 700,
                        color: placeDetails.open_now ? "#5A8F5A" : "#C0392B" }}>
                        {placeDetails.open_now ? "Open now" : "Closed"}
                      </span>
                    )}
                    {!isNighttime && (() => {
                      const isSunny = selectedPlace.is_sunny ?? selectedPlaceIsSunny;
                      return isSunny != null ? (
                        <span style={{ fontSize: "0.76em", fontWeight: 700,
                          color: isSunny ? "#C8A000" : "#4A7090" }}>
                          {isSunny ? "☀ Sunny now" : "☁ Shaded now"}
                        </span>
                      ) : null;
                    })()}
                  </div>

                  {/* Contact info */}
                  {placeDetails && (placeDetails.formatted_phone_number || placeDetails.website) && (
                    <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginBottom: "10px" }}>
                      {placeDetails.formatted_phone_number && (
                        <a href={`tel:${placeDetails.formatted_phone_number}`}
                          style={{ fontSize: "0.76em", color: colors.subtext, textDecoration: "none" }}>
                          📞 {placeDetails.formatted_phone_number}
                        </a>
                      )}
                      {placeDetails.website && (
                        <a href={placeDetails.website} target="_blank" rel="noopener noreferrer"
                          style={{ fontSize: "0.76em", color: colors.subtext, textDecoration: "none",
                            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "180px" }}>
                          🌐 {new URL(placeDetails.website).hostname.replace("www.", "")}
                        </a>
                      )}
                    </div>
                  )}

                  {/* Loading skeleton */}
                  {placeDetailsLoading && (
                    <div style={{ fontSize: "0.76em", color: colors.subtext, marginBottom: "6px" }}>Loading details…</div>
                  )}

                  {/* Opening hours */}
                  {placeDetails?.weekday_text?.length > 0 && (
                    <details style={{ marginBottom: "10px" }}>
                      <summary style={{ fontSize: "0.78em", color: colors.subtext, cursor: "pointer", listStyle: "none" }}>
                        Hours ▾
                      </summary>
                      <div style={{ marginTop: "4px", display: "flex", flexDirection: "column", gap: "1px" }}>
                        {placeDetails.weekday_text.map((line, i) => (
                          <span key={i} style={{ fontSize: "0.74em", color: colors.subtext }}>{line}</span>
                        ))}
                      </div>
                    </details>
                  )}

                  {/* Reviews */}
                  {placeDetails?.reviews?.length > 0 && (
                    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                      {(showAllReviews ? placeDetails.reviews : placeDetails.reviews.slice(0, 3)).map((r, i) => (
                        <div key={i} style={{ borderTop: `1px solid ${colors.accentFaint}`, paddingTop: "8px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                            <span style={{ fontSize: "0.78em", fontWeight: 700, color: colors.text }}>
                              {r.author_name}
                              {r.rating != null && <span style={{ fontWeight: 400, color: colors.subtext, marginLeft: "5px" }}>{"★".repeat(r.rating)}</span>}
                            </span>
                            <span style={{ fontSize: "0.72em", color: colors.subtext }}>{r.relative_time}</span>
                          </div>
                          <p style={{ margin: "3px 0 0", fontSize: "0.76em", color: colors.text, lineHeight: 1.4,
                            display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                            {r.text}
                          </p>
                        </div>
                      ))}
                      {placeDetails.reviews.length > 3 && (
                        <button
                          onClick={() => setShowAllReviews((v) => !v)}
                          style={{ fontSize: "0.75em", padding: "0.3em 0.8em", alignSelf: "flex-start",
                            background: "transparent", border: `1.5px solid ${colors.accentFaint}`,
                            color: colors.subtext, borderRadius: "999px", cursor: "pointer", boxShadow: "none" }}>
                          {showAllReviews ? "Show fewer" : "Show more reviews"}
                        </button>
                      )}
                    </div>
                  )}

                  {/* Save as Spot + Plan route here */}
                  {(() => {
                    const alreadySaved = spots.some(
                      (s) => s.place_id && s.place_id === selectedPlace.place_id,
                    );
                    return (
                      <div style={{ marginTop: "12px", display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
                        {alreadySaved || placeSaveSuccess === selectedPlace.place_id ? (
                          <span style={{ fontSize: "0.82em", fontWeight: 700, color: "#5A8F5A" }}>
                            {placeSaveSuccess === selectedPlace.place_id ? "Saved to Spots!" : "✓ Saved to Spots"}
                          </span>
                        ) : (
                          <button onClick={() => openSaveSpotModal(selectedPlace)}
                            style={{ fontSize: "0.78em", padding: "0.3em 0.9em" }}>
                            Save as Spot
                          </button>
                        )}
                        <button
                          onClick={() => planRouteToPlace(selectedPlace)}
                          style={{ fontSize: "0.78em", padding: "0.3em 0.9em" }}
                        >
                          Plan route here →
                        </button>
                      </div>
                    );
                  })()}
                </div>
              </div>
            </div>
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
              {weather.uv_index >= 6 && !isNighttime && (
                <span style={{ color: "#C0392B", fontWeight: 700 }}>
                  sunscreen!
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Save as Spot modal */}
      {saveSpotModal && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.3)",
          backdropFilter: "blur(2px)", display: "flex", alignItems: "center",
          justifyContent: "center", zIndex: 2000, padding: "20px",
        }}>
          <div style={{
            background: "var(--color-surface)", border: "2.5px solid #fff",
            borderRadius: "24px", padding: "24px", width: "100%", maxWidth: "340px",
            boxShadow: "6px 6px 0 var(--color-accent-dim)",
            display: "flex", flexDirection: "column", gap: "14px",
          }}>
            <h3 style={{ margin: 0, fontSize: "1.05em", color: colors.text }}>Save as Spot</h3>

            {/* Name */}
            <div>
              <label style={{ fontSize: "0.75em", fontWeight: 800, color: colors.subtext, textTransform: "uppercase", letterSpacing: "0.06em", display: "block", marginBottom: "5px" }}>Name</label>
              <input
                type="text"
                value={saveSpotModal.name}
                onChange={(e) => setSaveSpotModal({ ...saveSpotModal, name: e.target.value })}
              />
            </div>

            {/* Note */}
            <div>
              <label style={{ fontSize: "0.75em", fontWeight: 800, color: colors.subtext, textTransform: "uppercase", letterSpacing: "0.06em", display: "block", marginBottom: "5px" }}>Note <span style={{ fontWeight: 400, textTransform: "none" }}>(optional)</span></label>
              <textarea
                value={saveSpotModal.note}
                onChange={(e) => setSaveSpotModal({ ...saveSpotModal, note: e.target.value })}
                placeholder="Add a note to yourself…"
                rows={2}
                style={{
                  display: "block", width: "100%", boxSizing: "border-box",
                  background: "var(--color-input-bg)", border: "2px solid #fff",
                  borderRadius: "10px", padding: "8px 12px", fontSize: "15px",
                  fontFamily: "Nunito, sans-serif", fontWeight: 500,
                  color: "var(--color-text)", outline: "none", resize: "none",
                  boxShadow: "2px 2px 0 var(--color-accent-dim)",
                }}
              />
            </div>

            {/* Icon */}
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: saveSpotIconOpen ? "10px" : 0 }}>
                <div style={{
                  width: "36px", height: "36px", borderRadius: "50%",
                  background: "var(--color-accent)", display: "flex",
                  alignItems: "center", justifyContent: "center", flexShrink: 0,
                }}>
                  <FontAwesomeIcon icon={spotIcon(saveSpotModal.icon)} style={{ color: "var(--color-text)", fontSize: "15px" }} />
                </div>
                <button
                  onClick={() => setSaveSpotIconOpen((v) => !v)}
                  style={{ fontSize: "0.75em", padding: "0.3em 0.8em", background: "transparent", border: `1.5px solid ${colors.accentFaint}`, color: colors.subtext, boxShadow: "none" }}
                >
                  {saveSpotIconOpen ? "Close" : "Change"}
                </button>
              </div>
              {saveSpotIconOpen && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                  {SPOT_ICONS.map(({ key, icon }) => (
                    <button
                      key={key}
                      onClick={() => { setSaveSpotModal({ ...saveSpotModal, icon: key }); setSaveSpotIconOpen(false); }}
                      style={{
                        width: "36px", height: "36px", borderRadius: "50%", padding: 0,
                        border: saveSpotModal.icon === key ? "2.5px solid var(--color-text)" : "2px solid var(--color-accent-dim)",
                        background: saveSpotModal.icon === key ? "var(--color-accent)" : "transparent",
                        cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "none",
                      }}
                    >
                      <FontAwesomeIcon icon={icon} style={{ color: "var(--color-text)", fontSize: "14px" }} />
                    </button>
                  ))}
                </div>
              )}
            </div>

            {saveSpotError && <p style={{ margin: 0, color: "#C0392B", fontSize: "0.82em", fontWeight: 700 }}>{saveSpotError}</p>}

            <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
              <button
                onClick={() => setSaveSpotModal(null)}
                style={{ fontSize: "0.82em", background: "transparent", border: `1.5px solid ${colors.accentFaint}`, color: colors.subtext, boxShadow: "none" }}
              >
                Cancel
              </button>
              <button onClick={confirmSaveSpot} style={{ fontSize: "0.82em" }}>
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

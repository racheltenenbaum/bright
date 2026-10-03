import { useEffect, useState } from "react";
import { getCurrentPosition } from "./geolocation";
import api from "../api";
import { isCovered } from "./coverage";

// "checking"/"unknown" both render the app as usable — we only ever gate on
// a *positive* out-of-bounds match, since we'd rather show a working map to
// someone geolocation failed for than wrongly block them.
export function useServiceArea() {
  const [status, setStatus] = useState("checking");
  const [regions, setRegions] = useState([]);

  useEffect(() => {
    let cancelled = false;

    api.get("/regions").then(({ data }) => {
      if (cancelled) return;
      setRegions(data.regions);

      function handlePosition(lat, lng) {
        if (cancelled) return;
        setStatus(isCovered(lat, lng, data.regions) ? "supported" : "unsupported");
      }

      getCurrentPosition({ timeout: 5000 })
        .then((pos) => handlePosition(pos.coords.latitude, pos.coords.longitude))
        .catch(() => {
          if (!cancelled) setStatus("unknown");
        });
    }).catch(() => {
      if (!cancelled) setStatus("unknown");
    });

    return () => { cancelled = true; };
  }, []);

  return { status, regions };
}

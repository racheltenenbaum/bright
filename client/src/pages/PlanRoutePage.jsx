import { useNavigate } from "react-router-dom";
import RouteMap from "../components/RouteMap";

export default function PlanRoutePage() {
  const navigate = useNavigate();

  return (
    <div>
      <button onClick={() => navigate("/")}>← Back</button>
      <h2>Plan a route</h2>
      <RouteMap />
    </div>
  );
}

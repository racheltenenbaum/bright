import RouteMap from "../components/RouteMap";
import { useServiceArea } from "../utils/useServiceArea";

export default function PlanRoutePage() {
  const { regions } = useServiceArea();

  return (
    <div className="plan-layout">
      <RouteMap regions={regions} />
    </div>
  );
}

import RouteMap from "../components/RouteMap";
import UnsupportedAreaNotice from "../components/UnsupportedAreaNotice";
import { useServiceArea } from "../utils/useServiceArea";

export default function PlanRoutePage() {
  const { status, regions } = useServiceArea();

  if (status === "unsupported") {
    return <UnsupportedAreaNotice regions={regions} />;
  }

  return (
    <div className="plan-layout">
      <RouteMap regions={regions} />
    </div>
  );
}

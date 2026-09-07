import PropTypes from "prop-types";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faMapLocationDot } from "@fortawesome/free-solid-svg-icons";

export default function UnsupportedAreaNotice({ regions }) {
  return (
    <div className="page-container" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ maxWidth: 440, textAlign: "center", padding: "0 24px" }}>
        <FontAwesomeIcon icon={faMapLocationDot} style={{ fontSize: "2.4em", color: "var(--color-accent)", marginBottom: 18 }} />
        <h2 style={{ margin: "0 0 10px" }}>bright isn&apos;t in your area yet</h2>
        <p style={{ color: "var(--color-subtext)", margin: "0 0 22px", lineHeight: 1.5 }}>
          We&apos;re currently mapping sun and shade in a handful of cities. Come back next time you&apos;re visiting one of these:
        </p>
        <ul style={{ listStyle: "none", padding: 0, margin: "0 0 22px", display: "flex", flexWrap: "wrap", gap: 10, justifyContent: "center" }}>
          {regions.map((region) => (
            <li
              key={region.id}
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                borderRadius: 10,
                padding: "6px 16px",
                fontWeight: 600,
                fontSize: "0.9em",
              }}
            >
              {region.name}
            </li>
          ))}
        </ul>
        <p style={{ color: "var(--color-subtext)", fontSize: "0.85em", margin: 0 }}>
          More cities are on the way.
        </p>
      </div>
    </div>
  );
}

UnsupportedAreaNotice.propTypes = {
  regions: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      name: PropTypes.string.isRequired,
    }),
  ).isRequired,
};

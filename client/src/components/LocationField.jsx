import { useState } from "react";
import PropTypes from "prop-types";
import { Autocomplete } from "@react-google-maps/api";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faClockRotateLeft, faXmark } from "@fortawesome/free-solid-svg-icons";
import { spotIcon } from "../pages/MySpotsPage";

const MY_LOCATION_LABEL = "Your location";

// The same yellow dot as the live-location marker on the map, so "Your
// location" in the field visibly means that dot.
function LocationDot() {
  return <span className="location-field-dot" aria-hidden="true" />;
}

/**
 * One route endpoint input (start or destination). When focused while empty
 * — or while showing "Your location" — it opens a quick-pick list: Your
 * location, then Home/Work spots, then recent searches. As soon as the user
 * types, Google's own address suggestions take over.
 */
export default function LocationField({
  value,
  isMyLocation,
  placeholder,
  onAutocompleteLoad,
  onPlaceChanged,
  onType,
  onClear,
  myLocationAvailable,
  onPickMyLocation,
  quickSpots,
  onPickSpot,
  recents,
  onPickRecent,
  onDeleteRecent,
  onClearRecents,
}) {
  const [focused, setFocused] = useState(false);

  const showList = focused && (isMyLocation || !value);
  const hasRows = myLocationAvailable || quickSpots.length > 0 || recents.length > 0;

  // Rows use onMouseDown + preventDefault so the input doesn't blur (and
  // close the list) before the pick registers.
  const pick = (fn) => (e) => {
    e.preventDefault();
    fn();
    setFocused(false);
    e.currentTarget.closest(".location-field")?.querySelector("input")?.blur();
  };

  return (
    <div className="location-field" style={{ position: "relative" }}>
      <Autocomplete onLoad={onAutocompleteLoad} onPlaceChanged={onPlaceChanged}>
        <input
          type="text"
          className={`address-input${isMyLocation ? " address-input--mine" : ""}`}
          value={isMyLocation ? MY_LOCATION_LABEL : value}
          onChange={(e) => onType(e.target.value)}
          onFocus={(e) => {
            setFocused(true);
            // Typing over "Your location" should replace it, like Google Maps.
            if (isMyLocation) e.target.select();
          }}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          style={{ paddingRight: value || isMyLocation ? "28px" : undefined, paddingLeft: isMyLocation ? "30px" : undefined }}
        />
      </Autocomplete>
      {isMyLocation && (
        <span style={{ position: "absolute", left: "11px", top: "50%", transform: "translateY(-50%)", display: "flex", pointerEvents: "none" }}>
          <LocationDot />
        </span>
      )}
      {(value || isMyLocation) && (
        <button
          type="button"
          aria-label="Clear"
          onMouseDown={(e) => e.preventDefault()}
          onClick={onClear}
          className="location-field-clear"
        >
          ×
        </button>
      )}

      {showList && hasRows && (
        <div className="location-field-list" role="listbox">
          {myLocationAvailable && !isMyLocation && (
            <button type="button" className="location-field-row" onMouseDown={pick(onPickMyLocation)}>
              <span className="location-field-row-icon"><LocationDot /></span>
              <span className="location-field-row-text location-field-row-text--mine">{MY_LOCATION_LABEL}</span>
            </button>
          )}
          {quickSpots.map((spot) => (
            <button key={`spot-${spot.id}`} type="button" className="location-field-row" onMouseDown={pick(() => onPickSpot(spot))}>
              <span className="location-field-row-icon"><FontAwesomeIcon icon={spotIcon(spot.icon)} /></span>
              <span className="location-field-row-text">
                <strong>{spot.name}</strong>
                {spot.address && <small>{spot.address}</small>}
              </span>
            </button>
          ))}
          {recents.length > 0 && (
            <>
              <div className="location-field-heading">
                <span>Recent</span>
                <button type="button" onMouseDown={pick(onClearRecents)}>Clear all</button>
              </div>
              {recents.map((r) => (
                <div key={`recent-${r.lat}-${r.lng}`} className="location-field-row location-field-row--recent">
                  <button type="button" className="location-field-row-main" onMouseDown={pick(() => onPickRecent(r))}>
                    <span className="location-field-row-icon"><FontAwesomeIcon icon={faClockRotateLeft} /></span>
                    <span className="location-field-row-text">
                      <strong>{r.name}</strong>
                      {r.address && r.address !== r.name && <small>{r.address}</small>}
                    </span>
                  </button>
                  <button
                    type="button"
                    className="location-field-row-delete"
                    aria-label={`Remove ${r.name} from recent searches`}
                    // Deleting keeps the list open so several can be removed in a row.
                    onMouseDown={(e) => { e.preventDefault(); onDeleteRecent(r); }}
                  >
                    <FontAwesomeIcon icon={faXmark} />
                  </button>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

const placeShape = PropTypes.shape({
  name: PropTypes.string,
  address: PropTypes.string,
  lat: PropTypes.number.isRequired,
  lng: PropTypes.number.isRequired,
});

LocationField.propTypes = {
  value: PropTypes.string.isRequired,
  isMyLocation: PropTypes.bool.isRequired,
  placeholder: PropTypes.string.isRequired,
  onAutocompleteLoad: PropTypes.func.isRequired,
  onPlaceChanged: PropTypes.func.isRequired,
  onType: PropTypes.func.isRequired,
  onClear: PropTypes.func.isRequired,
  myLocationAvailable: PropTypes.bool.isRequired,
  onPickMyLocation: PropTypes.func.isRequired,
  quickSpots: PropTypes.arrayOf(PropTypes.shape({ id: PropTypes.number.isRequired, name: PropTypes.string, address: PropTypes.string, icon: PropTypes.string })).isRequired,
  onPickSpot: PropTypes.func.isRequired,
  recents: PropTypes.arrayOf(placeShape).isRequired,
  onPickRecent: PropTypes.func.isRequired,
  onDeleteRecent: PropTypes.func.isRequired,
  onClearRecents: PropTypes.func.isRequired,
};

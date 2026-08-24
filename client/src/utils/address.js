export function addressFromComponents(components) {
  if (!components) return null;
  const get = (type) => components.find((c) => c.types.includes(type))?.long_name;

  const streetNumber = get("street_number");
  const route = get("route");
  const locality = get("postal_town") || get("locality");
  const postalCode = get("postal_code");

  const parts = [];
  if (route) parts.push(streetNumber ? `${streetNumber} ${route}` : route);
  if (locality) parts.push(locality);
  if (postalCode) parts.push(postalCode);

  return parts.length ? parts.join(", ") : null;
}

export function addressFromGeocodeResult(result) {
  return (
    addressFromComponents(result?.address_components) ||
    result?.formatted_address ||
    null
  );
}

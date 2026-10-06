#!/usr/bin/env bash
# Builds the "bright stg" iOS app — a separate app (own bundle ID, own icon
# name) that talks to the staging Railway environment — and installs it on a
# connected iPhone, next to the real bright app.
#
#   cd client && scripts/ios-staging.sh            # first connected iPhone
#   cd client && scripts/ios-staging.sh <device-id> # from `xcrun devicectl list devices`
#
# The web bundle copied into the Xcode project is put back to the production
# build afterwards (even on failure), so a normal Xcode build/archive can never
# ship staging by accident.
set -euo pipefail
cd "$(dirname "$0")/.."

BUNDLE_ID="com.racheltenenbaum.bright.staging"
GOOGLE_IOS_CLIENT_ID="$(sed -n 's/^GOOGLE_IOS_CLIENT_ID_STAGING=//p' .env.staging)"
[ -n "$GOOGLE_IOS_CLIENT_ID" ] || { echo "GOOGLE_IOS_CLIENT_ID_STAGING missing from .env.staging"; exit 1; }
DEVICE="${1:-$(xcrun devicectl list devices 2>/dev/null | awk '/available \(paired\)/ {print $3; exit}')}"
[ -n "$DEVICE" ] || { echo "No connected iPhone found (xcrun devicectl list devices)"; exit 1; }
BUILD_DIR="$(mktemp -d)"

restore_production() {
  echo "→ Restoring the production web bundle in the Xcode project"
  npm run build >/dev/null && npx cap sync ios >/dev/null
}
trap restore_production EXIT

echo "→ Building the web app for staging"
npx vite build --mode staging >/dev/null
npx cap sync ios >/dev/null

# The Google plugin reads its iOS client from the copied capacitor config.
node -e '
  const fs = require("fs"), p = "ios/App/App/capacitor.config.json";
  const c = JSON.parse(fs.readFileSync(p));
  c.plugins.GoogleAuth.iosClientId = process.argv[1];
  fs.writeFileSync(p, JSON.stringify(c, null, 2));
' "$GOOGLE_IOS_CLIENT_ID"
REVERSED="com.googleusercontent.apps.${GOOGLE_IOS_CLIENT_ID%.apps.googleusercontent.com}"

echo "→ Building bright stg"
xcodebuild -workspace ios/App/App.xcworkspace -scheme App -configuration Release \
  -destination "generic/platform=iOS" -derivedDataPath "$BUILD_DIR" -allowProvisioningUpdates -quiet \
  BRIGHT_BUNDLE_ID="$BUNDLE_ID" \
  BRIGHT_DISPLAY_NAME="bright stg" \
  BRIGHT_APPLINKS_DOMAIN="brightfe-staging.up.railway.app" \
  GOOGLE_IOS_REVERSED_CLIENT_ID="$REVERSED"

echo "→ Installing on $DEVICE"
# The wireless device link drops often; a retry usually goes through.
for attempt in 1 2 3; do
  xcrun devicectl device install app --device "$DEVICE" "$BUILD_DIR/Build/Products/Release-iphoneos/App.app" >/dev/null && break
  [ "$attempt" = 3 ] && { echo "Install failed — unlock the iPhone, keep it nearby, and rerun"; exit 1; }
  echo "  install attempt $attempt failed, retrying…"; sleep 5
done
xcrun devicectl device process launch --device "$DEVICE" "$BUNDLE_ID" >/dev/null || true
echo "✓ bright stg installed"

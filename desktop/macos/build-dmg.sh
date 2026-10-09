#!/bin/bash
# Build ThaiCustoms.app + DMG installer (runs on macOS only).
# The .app is a tiny launcher that opens the web app in the default browser.
#
# Usage (CI does this on macos-latest):
#   bash build-dmg.sh 1.0.0
# Output: dist/ThaiCustoms-<version>-mac.dmg
#
# NOTE: the app URL is duplicated in desktop/windows/installer.iss -
# update both files if the gateway URL ever changes.
set -euo pipefail

VERSION="${1:-1.0.0}"
APP_URL="https://gateway-1008099094873.asia-southeast1.run.app"
APP_NAME="ThaiCustoms"
EXEC_NAME="ThaiCustoms"
BUNDLE_ID="com.thaicustoms.webapp"

HERE="$(cd "$(dirname "$0")" && pwd)"
ASSETS="$HERE/../assets"
WORK="$HERE/build"
DIST="$HERE/dist"
APP="$WORK/$APP_NAME.app"

rm -rf "$WORK" "$DIST"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" "$DIST"

# --- icon (.png -> .icns via iconutil) ---
ICONSET="$WORK/icon.iconset"
mkdir -p "$ICONSET"
sips -z 16 16     "$ASSETS/logo-1024.png" --out "$ICONSET/icon_16x16.png" >/dev/null
sips -z 32 32     "$ASSETS/logo-1024.png" --out "$ICONSET/icon_16x16@2x.png" >/dev/null
sips -z 32 32     "$ASSETS/logo-1024.png" --out "$ICONSET/icon_32x32.png" >/dev/null
sips -z 64 64     "$ASSETS/logo-1024.png" --out "$ICONSET/icon_32x32@2x.png" >/dev/null
sips -z 128 128   "$ASSETS/logo-1024.png" --out "$ICONSET/icon_128x128.png" >/dev/null
sips -z 256 256   "$ASSETS/logo-1024.png" --out "$ICONSET/icon_128x128@2x.png" >/dev/null
sips -z 256 256   "$ASSETS/logo-1024.png" --out "$ICONSET/icon_256x256.png" >/dev/null
sips -z 512 512   "$ASSETS/logo-1024.png" --out "$ICONSET/icon_256x256@2x.png" >/dev/null
sips -z 512 512   "$ASSETS/logo-1024.png" --out "$ICONSET/icon_512x512.png" >/dev/null
sips -z 1024 1024 "$ASSETS/logo-1024.png" --out "$ICONSET/icon_512x512@2x.png" >/dev/null
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/logo.icns"

# --- launcher (opens the URL, nothing else) ---
cat > "$APP/Contents/MacOS/$EXEC_NAME" <<EOF
#!/bin/sh
exec open "$APP_URL"
EOF
chmod +x "$APP/Contents/MacOS/$EXEC_NAME"

# --- bundle metadata ---
cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>$EXEC_NAME</string>
  <key>CFBundleIconFile</key>
  <string>logo</string>
  <key>CFBundleIdentifier</key>
  <string>$BUNDLE_ID</string>
  <key>CFBundleName</key>
  <string>$APP_NAME</string>
  <key>CFBundleDisplayName</key>
  <string>$APP_NAME</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>$VERSION</string>
  <key>CFBundleVersion</key>
  <string>$VERSION</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
EOF

# NOTE: intentionally NOT codesigned (unsigned distribution).
# First launch needs right-click -> Open (see desktop/README.md).

# --- DMG with drag-to-Applications install ---
STAGE="$WORK/stage"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
DMG="$DIST/ThaiCustoms-$VERSION-mac.dmg"
hdiutil create -volname "$APP_NAME" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
hdiutil verify "$DMG" >/dev/null

echo "built $DMG ($(du -h "$DMG" | cut -f1))"

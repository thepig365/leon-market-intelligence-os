#!/usr/bin/env bash
set -euo pipefail

lmio_repo_root="$(cd "$(dirname "$0")/.." && pwd)"
lmio_source_script="$lmio_repo_root/tools/macos/LMIO-TWS-Launcher.applescript"
lmio_install_root="$HOME/Applications"
lmio_destination="$lmio_install_root/LMIO TWS Launcher.app"
lmio_temporary_root="$(mktemp -d)"
lmio_compiled_app="$lmio_temporary_root/LMIO TWS Launcher.app"
lmio_bundle_identifier="com.bayviewenterprise.lmio-tws-launcher"

cleanup_lmio_launcher() {
  rm -rf "$lmio_temporary_root"
}
trap cleanup_lmio_launcher EXIT

if [[ -e "$lmio_destination" ]]; then
  lmio_existing_identifier="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$lmio_destination/Contents/Info.plist" 2>/dev/null || true)"
  if [[ "$lmio_existing_identifier" != "$lmio_bundle_identifier" ]]; then
    echo "Refusing to replace an application not owned by LMIO: $lmio_destination" >&2
    exit 1
  fi
fi

osacompile -o "$lmio_compiled_app" "$lmio_source_script"
plutil -insert CFBundleURLTypes -json \
  '[{"CFBundleURLName":"com.bayviewenterprise.lmio-tws","CFBundleURLSchemes":["lmio-tws"]}]' \
  "$lmio_compiled_app/Contents/Info.plist"
plutil -replace CFBundleIdentifier -string "$lmio_bundle_identifier" \
  "$lmio_compiled_app/Contents/Info.plist"
codesign --force --deep --sign - "$lmio_compiled_app"
mkdir -p "$lmio_install_root"
ditto "$lmio_compiled_app" "$lmio_destination"
codesign --force --deep --sign - "$lmio_destination"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
  -f "$lmio_destination"

echo "Installed or updated LMIO TWS Launcher at $lmio_destination"

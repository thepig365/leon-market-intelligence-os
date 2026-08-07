#!/usr/bin/env bash
set -euo pipefail

lmio_repo_root="$(cd "$(dirname "$0")/.." && pwd)"
lmio_source_script="$lmio_repo_root/tools/macos/LMIO-TWS-Launcher.applescript"
lmio_install_root="$HOME/Applications"
lmio_destination="$lmio_install_root/LMIO TWS Launcher.app"
lmio_temporary_root="$(mktemp -d)"
lmio_compiled_app="$lmio_temporary_root/LMIO TWS Launcher.app"

cleanup_lmio_launcher() {
  rm -rf "$lmio_temporary_root"
}
trap cleanup_lmio_launcher EXIT

if [[ -e "$lmio_destination" ]]; then
  echo "Refusing to overwrite the existing launcher: $lmio_destination" >&2
  exit 1
fi

osacompile -o "$lmio_compiled_app" "$lmio_source_script"
plutil -insert CFBundleURLTypes -json \
  '[{"CFBundleURLName":"com.bayviewenterprise.lmio-tws","CFBundleURLSchemes":["lmio-tws"]}]' \
  "$lmio_compiled_app/Contents/Info.plist"
plutil -replace CFBundleIdentifier -string "com.bayviewenterprise.lmio-tws-launcher" \
  "$lmio_compiled_app/Contents/Info.plist"
codesign --force --deep --sign - "$lmio_compiled_app"
mkdir -p "$lmio_install_root"
ditto "$lmio_compiled_app" "$lmio_destination"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
  -f "$lmio_destination"

echo "Installed LMIO TWS Launcher at $lmio_destination"

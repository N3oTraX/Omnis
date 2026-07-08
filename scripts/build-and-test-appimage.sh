#!/usr/bin/env bash
# Build the Omnis AppImage from the current checkout and smoke-test it before
# tagging a public release. The smoke test runs headless (offscreen) and fails
# if the config is not found or the privileged engine dies (the two regressions
# that previously shipped in a public tag).
#
# Usage (on the build/test host, e.g. VM700):
#   ./scripts/build-and-test-appimage.sh
#
# Exit code 0 = AppImage built and smoke test passed.
set -euo pipefail

export NIX_CONFIG="experimental-features = nix-command flakes"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="$(nix eval --raw .#omnis.version 2>/dev/null || echo dev)"
OUT="omnis-${VERSION}-x86_64.AppImage"

echo "==> Build AppImage: $OUT"
nix bundle --bundler .#appimage .#omnis -o "$OUT"
sha256sum "$OUT" | tee "${OUT}.sha256"
ls -lh "$OUT"

APP_ABS="$ROOT/$OUT"

echo "==> Warm-up + binaire lancable (--version)"
VER_OUT="$(timeout 180 "$APP_ABS" --version)"
echo "$VER_OUT"
case "$VER_OUT" in
  *"$VERSION"*) ;;
  *) echo "ATTENTION: --version ($VER_OUT) ne correspond pas au build ($VERSION) : __version__ desynchronise" ;;
esac

# Two smoke layers. Offscreen (headless/CI) validates config + launcher but
# NEVER exercises real rendering: a broken GL/EGL/GLX stack only surfaces on a
# real windowing session. So we also render on wayland when one is available.
FAILED=0

check_log() {
  local log="$1" f=0
  grep -q "No configuration file found" "$log" && { echo "  ECHEC: config introuvable"; f=1; }
  grep -qiE "Engine process died|Error starting engine" "$log" \
    && { echo "  ECHEC: moteur privilegie mort"; f=1; }
  grep -qiE "Failed to initialize graphics backend|Failed to create RHI|Could not initialize GLX|Failed to create (temporary )?context" "$log" \
    && { echo "  ECHEC: rendu KO (GL/EGL/GLX indispo, backend logiciel non actif ?)"; f=1; }
  grep -qi "Applied theme overlay" "$log" || { echo "  ECHEC: overlay theme non applique"; f=1; }
  return $f
}

# Run from an empty dir so the AppImage uses its bundled config (mimics
# launching from ~/Downloads); running from the repo would fall back to ./config.
echo "==> Smoke offscreen (hors arbre source)"
LOG1="$(mktemp)"; D1="$(mktemp -d)"
set +e
( cd "$D1" && QT_QPA_PLATFORM=offscreen timeout 40 "$APP_ABS" --debug ) >"$LOG1" 2>&1
echo "  (code: $?)"
set -e
rmdir "$D1" 2>/dev/null || true
grep -iE "backend|RHI|GLX|EGL|error|died|No configuration" "$LOG1" | head -15 || true
check_log "$LOG1" || FAILED=1
rm -f "$LOG1"

# Real render on wayland if a graphical session exists: the only layer that
# proves the window actually draws (software backend vs broken GL).
WL=""
for _s in "/run/user/$(id -u)"/wayland-[0-9]*; do
  [ -S "$_s" ] && { WL="$(basename "$_s")"; break; }
done
if [ -n "$WL" ]; then
  echo "==> Smoke rendu wayland ($WL)"
  LOG2="$(mktemp)"; D2="$(mktemp -d)"
  set +e
  ( cd "$D2" && XDG_RUNTIME_DIR="/run/user/$(id -u)" WAYLAND_DISPLAY="$WL" \
      QT_QPA_PLATFORM=wayland timeout 20 "$APP_ABS" --debug ) >"$LOG2" 2>&1
  echo "  (code: $?)"
  set -e
  rmdir "$D2" 2>/dev/null || true
  grep -iE "backend|RHI|GLX|EGL|context|Omnis Installer started" "$LOG2" | head -15 || true
  check_log "$LOG2" || FAILED=1
  rm -f "$LOG2"
else
  echo "==> (pas de session wayland : rendu reel non couvert ;"
  echo "     relancer ce script DANS la session graphique pour le valider)"
fi

if [ "$FAILED" = "1" ]; then
  echo "==> SMOKE TEST ECHOUE — ne pas tagger"
  exit 1
fi
echo "==> SMOKE TEST OK: $OUT lancable (config + theme + moteur integre + rendu)"

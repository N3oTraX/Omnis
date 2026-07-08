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

echo "==> Warm-up + binaire lancable (--version)"
timeout 180 "./$OUT" --version

echo "==> Smoke test (offscreen)"
LOG="$(mktemp)"
set +e
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LIBGL_ALWAYS_SOFTWARE=1 \
  timeout 40 "./$OUT" --debug >"$LOG" 2>&1
rc=$?
set -e

echo "--- journal (extrait) ---"
grep -iE "config|theme|engine|qml|error|died|traceback" "$LOG" | head -30 || true
echo "--- (code de sortie: $rc) ---"

fail=0
grep -q "No configuration file found" "$LOG" && { echo "ECHEC: config introuvable"; fail=1; }
grep -qiE "Engine process died|Error starting engine" "$LOG" && {
  echo "ECHEC: moteur privilegie mort (fork pkexec incompatible AppImage ?)"; fail=1; }
grep -qi "Applied theme overlay" "$LOG" || {
  echo "ECHEC: overlay theme non applique (UI non initialisee)"; fail=1; }

# 124 = tue par timeout tout en tournant (bon signe) ; 0 = sortie propre.
if [ "$rc" != "124" ] && [ "$rc" != "0" ]; then
  echo "ATTENTION: code de sortie inattendu ($rc) hors timeout/sortie propre"
fi

rm -f "$LOG"
if [ "$fail" = "1" ]; then
  echo "==> SMOKE TEST ECHOUE — ne pas tagger"
  exit 1
fi

echo "==> SMOKE TEST OK: $OUT lancable (config + theme + moteur integre)"
echo
echo "Validation visuelle reelle (session graphique, en root pour les etapes privilegiees) :"
echo "  sudo XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=\$(ls /run/user/1000 | grep -m1 '^wayland-[0-9]') \\"
echo "    QT_QPA_PLATFORM=wayland QT_QUICK_BACKEND=software ./$OUT"

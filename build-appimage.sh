#!/usr/bin/env bash
# Build AppImage for 9Router TUI (Linux)
# Requires: python3, pip, PyInstaller, appimagetool (auto-downloaded if missing)
# Usage: ./build-appimage.sh  (or bash build-appimage.sh on Windows/WSL)
# Output: dist/9Router-TUI-1.0.0-x86_64.AppImage
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
VERSION="$(cat "$ROOT/VERSION" 2>/dev/null | tr -d ' \n\r' || echo "1.0.0")"
ARCH="$(uname -m 2>/dev/null || echo x86_64)"
APP_NAME="9Router-TUI"
APPDIR="$ROOT/dist/AppDir"
APPIMAGE="$ROOT/dist/${APP_NAME}-${VERSION}-${ARCH}.AppImage"

echo "[INFO] Building AppImage v${VERSION} for ${ARCH}..."

# 1. Build Linux binary via PyInstaller
echo "[1/4] PyInstaller..."
python3 -m pip install --quiet -r "$ROOT/requirements.txt" 2>&1 | tail -5 || true
python3 -m pip install --quiet pyinstaller 2>&1 | tail -3 || true
python3 -m PyInstaller "$ROOT/9Router-TUI.spec" --noconfirm --distpath "$ROOT/dist" --workpath "$ROOT/build" 2>&1 | tail -20

BIN="$ROOT/dist/9Router-TUI"
if [ ! -f "$BIN" ] && [ -f "$ROOT/dist/9Router-TUI.exe" ]; then
  BIN="$ROOT/dist/9Router-TUI.exe"
fi
if [ ! -f "$BIN" ]; then
  echo "[ERROR] Binary not found at $BIN"
  ls -la "$ROOT/dist/" || true
  exit 1
fi
chmod +x "$BIN"

# 2. Prepare AppDir
echo "[2/4] Preparing AppDir..."
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp "$BIN" "$APPDIR/usr/bin/9Router-TUI"
cp "$ROOT/9Router-TUI.desktop" "$APPDIR/9Router-TUI.desktop"
cp "$ROOT/9Router-TUI.desktop" "$APPDIR/usr/share/applications/9Router-TUI.desktop"
# Icon: use a simple placeholder if no icon exists
if [ -f "$ROOT/icon.png" ]; then
  cp "$ROOT/icon.png" "$APPDIR/9router-tui.png"
  cp "$ROOT/icon.png" "$APPDIR/.DirIcon"
  cp "$ROOT/icon.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/9router-tui.png"
elif [ -f "$ROOT/icon.ico" ]; then
  # try convert via Python if available
  python3 -c "from PIL import Image; Image.open('$ROOT/icon.ico').save('$APPDIR/9router-tui.png')" 2>/dev/null || cp "$ROOT/icon.ico" "$APPDIR/9router-tui.png" || true
  cp "$APPDIR/9router-tui.png" "$APPDIR/.DirIcon" 2>/dev/null || true
else
  # generate a minimal 256x256 placeholder via Python
  python3 -c "
from PIL import Image, ImageDraw
im = Image.new('RGB', (256,256), (15,23,42))
d = ImageDraw.Draw(im)
d.rectangle([32,32,224,224], fill=(56,189,248), outline=(255,255,255), width=4)
d.text((64,110), '9R', fill=(255,255,255))
im.save('$APPDIR/9router-tui.png')
im.save('$APPDIR/.DirIcon')
im.save('$APPDIR/usr/share/icons/hicolor/256x256/apps/9router-tui.png')
" 2>/dev/null || {
    echo "[WARN] No PIL, creating empty icon placeholder"
    touch "$APPDIR/9router-tui.png" "$APPDIR/.DirIcon"
  }
fi

# AppRun
cat > "$APPDIR/AppRun" <<'APPRUN'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/9Router-TUI" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

# 3. Get appimagetool
echo "[3/4] appimagetool..."
TOOL="$ROOT/dist/appimagetool"
if [ ! -x "$TOOL" ]; then
  # try download
  URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
  echo "[INFO] Downloading appimagetool from $URL"
  if command -v curl >/dev/null 2>&1; then
    curl -L -o "$TOOL" "$URL" || wget -O "$TOOL" "$URL" || true
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$TOOL" "$URL" || true
  fi
  chmod +x "$TOOL" 2>/dev/null || true
fi

# 4. Build AppImage
echo "[4/4] Building AppImage..."
if [ -x "$TOOL" ]; then
  ARCH="$ARCH" "$TOOL" "$APPDIR" "$APPIMAGE" 2>&1 | tail -20
else
  echo "[WARN] appimagetool not available, trying docker fallback..."
  if command -v docker >/dev/null 2>&1; then
    docker run --rm -v "$ROOT:/work" -w /work ubuntu:22.04 bash -c "
      apt-get update -qq && apt-get install -y -qq wget file &&
      wget -q -O /tmp/appimagetool https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage &&
      chmod +x /tmp/appimagetool && ARCH=${ARCH} /tmp/appimagetool /work/dist/AppDir /work/dist/${APP_NAME}-${VERSION}-${ARCH}.AppImage
    " 2>&1 | tail -20
  else
    echo "[ERROR] Cannot build AppImage: appimagetool not found and docker not available."
    echo "AppDir is ready at $APPDIR — you can run: ARCH=$ARCH appimagetool $APPDIR $APPIMAGE"
    exit 1
  fi
fi

if [ -f "$APPIMAGE" ]; then
  chmod +x "$APPIMAGE"
  echo "[OK] AppImage built: $APPIMAGE"
  ls -lh "$APPIMAGE"
else
  echo "[ERROR] AppImage not created"
  exit 1
fi

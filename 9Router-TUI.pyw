"""9Router TUI — Double-click launcher (.pyw, zero-config)

Di Windows, file .pyw bisa double-click langsung tanpa buka PowerShell/cmd.
Windows akan pakai pythonw.exe (tanpa console hitam) — tapi untuk TUI kita
butuh console, jadi launcher ini akan spawn console baru via `python app.py`.

Tanpa config awal pun akan muncul Server Picker di TUI (zero-config).
Jika deps belum ada, auto pip install dulu.

Cara pakai: double-click file ini di Explorer.
Pastikan Python terinstall dan .pyw terasosiasi ke Python Launcher (pyw).
Jika tidak jalan, pakai 9Router-TUI.bat atau build .exe via PyInstaller.
"""
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(ROOT, "app.py")
REQ = os.path.join(ROOT, "requirements.txt")

def _find_python():
    import shutil
    for cand in ("python", "py", "python3"):
        if shutil.which(cand):
            return cand
    return None

def _ensure_deps(py):
    try:
        subprocess.run([py, "-c", "import textual"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        pass
    # auto-install
    try:
        subprocess.run([py, "-m", "pip", "install", "--disable-pip-version-check", "-r", REQ], check=False)
        subprocess.run([py, "-c", "import textual"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

PY = _find_python()
if not PY:
    if os.name == "nt":
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "Python tidak ditemukan! Install Python 3.10+ dan centang 'Add to PATH'.\n\nAlternatif: pakai dist\\9Router-TUI.exe (standalone, tanpa Python).", "9Router TUI", 0x10)
    sys.exit(1)

# ensure deps before spawning TUI (so first double-click works)
_ensure_deps(PY)

# Pakai `python` (bukan pythonw) agar console muncul untuk TUI
# Di Windows, `py` launcher akan handle ini
candidates = [PY, "py", "python", "python3"]
# dedup preserve order
seen = set()
cands = []
for c in candidates:
    if c not in seen:
        seen.add(c)
        cands.append(c)

for cmd in cands:
    try:
        if os.name == "nt":
            subprocess.Popen([cmd, APP], cwd=ROOT, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([cmd, APP], cwd=ROOT)
        break
    except FileNotFoundError:
        continue
else:
    if os.name == "nt":
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "Python tidak ditemukan! Install Python 3.10+ dan centang 'Add to PATH'.", "9Router TUI", 0x10)

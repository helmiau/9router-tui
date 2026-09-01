<p align="center">
  <img src="icons/9tui-icon.png" width="160" alt="9Router TUI Icon" />
</p>

<h1 align="center">9Router TUI — Terminal Dashboard (Standalone)</h1>

<p align="center">
  <b>Indonesia</b> • <a href="README.md">English</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.2.5-blue" alt="Version" />
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey" alt="Platform" />
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python" />
</p>

Terminal UI standalone untuk **9Router** (`9router-master` v0.5.55) — **sepenuhnya independen, tanpa `omnexsync` atau dependensi eksternal lain**. Hanya butuh `NINEROUTER_URL` + `NINEROUTER_KEY` untuk terhubung ke instance 9Router yang sedang berjalan.

Mencerminkan dashboard web resmi (`http://localhost:20128/dashboard`) di terminal: health, providers, nodes, combos, models, keys, usage, settings — semua via REST API `src/app/api/*` yang sama. Proyek ini terpisah dan mandiri — tidak mengimpor, membundel, atau membutuhkan `omnexsync`.

## Screenshot

<div align="center">

<table>
<tr>
<td align="center"><b>Overview</b><br><img src="docs/screenshots/overview.png" width="320" alt="Overview" /></td>
<td align="center"><b>Providers</b><br><img src="docs/screenshots/providers-main.png" width="320" alt="Providers" /></td>
<td align="center"><b>Nodes</b><br><img src="docs/screenshots/nodes-main.png" width="320" alt="Nodes" /></td>
</tr>
<tr>
<td align="center"><b>Nodes — Edit</b><br><img src="docs/screenshots/nodes-edit.png" width="320" alt="Nodes Edit" /></td>
<td align="center"><b>Nodes — Edit UID</b><br><img src="docs/screenshots/nodes-edit-uid.png" width="320" alt="Nodes Edit UID" /></td>
<td align="center"><b>Combos</b><br><img src="docs/screenshots/combos-main.png" width="320" alt="Combos" /></td>
</tr>
<tr>
<td align="center"><b>Models</b><br><img src="docs/screenshots/models-main.png" width="320" alt="Models" /></td>
<td align="center"><b>Keys</b><br><img src="docs/screenshots/keys-main.png" width="320" alt="Keys" /></td>
<td align="center"><b>Usage</b><br><img src="docs/screenshots/usage-main.png" width="320" alt="Usage" /></td>
</tr>
<tr>
<td align="center"><b>Usage — Days</b><br><img src="docs/screenshots/usage-list-days.png" width="320" alt="Usage Days" /></td>
<td align="center"><b>Updater</b><br><img src="docs/screenshots/updater-main.png" width="320" alt="Updater" /></td>
<td align="center"><b>Lainnya…</b><br><em>11 tabs + modals</em></td>
</tr>
</table>

</div>

## Fitur

| Halaman | API | Deskripsi |
|---|---|---|
| **Overview** | `GET /api/health`, `GET /api/settings`, `GET /api/version`, `GET /api/provider-nodes`, `GET /api/providers`, `GET /api/combos` | Health, version, ringkasan providers/nodes/combos, test all |
| **Providers** | `GET /api/providers`, `POST /api/providers/test-batch`, `PUT/DELETE /api/providers/:id` | Tabel connections, filter, detail, test batch, test selected, toggle active, delete |
| **Nodes** | `GET /api/provider-nodes`, `POST/PUT/DELETE /api/provider-nodes` | Tabel nodes, filter, detail, Add/Edit/Delete, **Edit UID** (gabung di Edit, suffix custom seperti `cutad`, `hcnsec`) |
| **Combos** | `GET /api/combos`, `POST/PUT/DELETE /api/combos` | Tabel combos, detail, Add/Edit/Delete, selector model dengan filter |
| **Models** | `GET /api/models`, `GET /v1/models` | Tabel models (model, provider, alias, caps), filter |
| **Keys** | `GET /api/keys`, `POST/PUT/DELETE /api/keys` | Tabel dashboard keys, Create/Edit/Delete, toggle active, masked |
| **Usage** | `GET /api/usage/stats`, `GET /api/usage/history` | Stats per period, history table |
| **Settings** | `GET /api/settings`, `PATCH /api/settings` | View + editor multi-config (form + Raw JSON), **TUI Config** (auto_login, theme, dll), **Manage Servers** (add/edit/delete/reorder) |
| **Pools** | `GET /api/proxy-pools` | Tabel proxy pools, detail |
| **Logs** | `GET /api/usage/logs` | Tabel request logs, detail |
| **Update** | `GET /api/version` + npm registry, `updater.py` | Version check, update (npm/source/docker — local & remote via SSH), Docker status/logs/pull/restart, **Backup/Restore** (`data.sqlite` + history) |

## Quick Start

```bash
cd 9router-tui
pip install -r requirements.txt

# Tanpa konfigurasi? Langsung jalan — TUI akan tampilkan picker server interaktif
python app.py
# → Pilih: Local (http://localhost:20128) / Tunnel / Custom URL + API key
# → Connect / Save & Connect (simpan ke servers.json)

# Atau set env dulu
export NINEROUTER_URL="http://localhost:20128"
export NINEROUTER_KEY="sk-..."  # hanya jika requireApiKey=true
python app.py

# CLI (Rich, non-interactive)
python cli.py health
python cli.py providers --filter hcn
python cli.py nodes
python cli.py combos
python cli.py models --filter gpt
python cli.py keys
python cli.py usage --period 7d
python cli.py settings
python cli.py test --mode all
python cli.py v1-models

# Kelola multi-server (tanpa config file)
python cli.py servers                    # list saved servers
python cli.py servers --probe            # + health probe

# Update & Docker (local only — remote hanya tampilkan info)
python cli.py version                    # GET /api/version + npm latest
python cli.py version --json
python cli.py update --dry-run           # lihat plan (npm/source/docker auto-detect)
python cli.py update --method docker --dry-run
python cli.py update --yes               # eksekusi (konfirmasi y/N jika tanpa --yes)
python cli.py docker status              # docker ps + images + compose
python cli.py docker logs --tail 100
python cli.py docker pull --image decolua/9router:latest
python cli.py docker restart --container 9router
python cli.py docker update --dry-run    # compose pull + up -d
python cli.py server-add https://my-9router.example.com --name "My VPS" --api-key sk-...
python cli.py server-use                 # picker interaktif
python cli.py server-use "My VPS"        # langsung pakai
python cli.py server-remove "My VPS"

# Custom URL/key per-command
python cli.py --url https://distribute-jimmy-church-audit.trycloudflare.com --api-key sk-... providers
python app.py --url http://localhost:20128 --api-key sk-...
```

## Download (Release)

Binary jadi — tanpa Python:

| Platform | File | Cara Jalan |
|---|---|---|
| **Windows** | `9Router-TUI-1.0.0-windows-x86_64.exe` | Double-click |
| **Linux** | `9Router-TUI-1.0.0-x86_64.AppImage` | `chmod +x *.AppImage && ./9Router-TUI-*.AppImage` |

Ambil di **GitHub Releases** (tag `v1.0.0`). Juga tersedia sebagai `9Router-TUI.exe` / `9Router-TUI` tanpa suffix versi.

```bash
# Linux AppImage
chmod +x 9Router-TUI-1.0.0-x86_64.AppImage
./9Router-TUI-1.0.0-x86_64.AppImage --help
./9Router-TUI-1.0.0-x86_64.AppImage --version

# Windows
9Router-TUI-1.0.0-windows-x86_64.exe --version
```

> Versi ada di `VERSION` (single source of truth). `app.py --version` dan `cli.py --version` baca dari situ. Naikkan `VERSION` dan tag `v1.0.1` untuk trigger release baru.

## Double-Click — Jalankan Tanpa PowerShell / Terminal

Tidak perlu buka PowerShell atau ketik `python app.py` — cukup **klik 2x**.

### Opsi 1: `.exe` / `.AppImage` Standalone (Rekomendasi) ✅

Hasil build PyInstaller — **tidak butuh Python**.

| Platform | Build | Output |
|---|---|---|
| Windows | `python -m PyInstaller 9Router-TUI.spec --noconfirm` | `dist/9Router-TUI.exe` |
| Linux | `bash build-appimage.sh` | `dist/9Router-TUI-1.0.0-x86_64.AppImage` |

- `console=True` di `9Router-TUI.spec` jadi double-click otomatis buka jendela console untuk TUI.
- Sudah dites: `dist\9Router-TUI.exe --version` → `1.0.0`.
- Spec di `9Router-TUI.spec` sudah handle `textual` + `rich` (collect_all) dan bundle `VERSION` + `_version.py`.
- `build/` dan `dist/` sudah di-`.gitignore` (hanya `9Router-TUI.spec` yang di-track).

**Shortcut Desktop (Windows):** klik kanan `dist\9Router-TUI.exe` → `Send to` → `Desktop (create shortcut)` → rename jadi "9Router TUI".

**Linux Desktop Entry:** `9Router-TUI.desktop` sudah ada — copy ke `~/.local/share/applications/` dan jadikan AppImage executable.

**Tambah Icon:** taruh `icon.ico` / `icon.png` di root, ubah `icon=None` jadi `icon='icon.ico'` di `9Router-TUI.spec`, lalu rebuild. `build-appimage.sh` akan pakai `icon.png`/`icon.ico` otomatis.

**Perkecil Ukuran:** `upx=True` sudah aktif. Alternatif: build `--onedir` lalu zip, atau exclude `numpy`/`PIL` jika tidak dipakai. Untuk installer Start Menu, bungkus `.exe` dengan Inno Setup.

### Opsi 2: `9Router-TUI.bat` / `9Router-TUI.cmd` (butuh Python, Windows)

Double-click `9Router-TUI.bat` — otomatis `pip install -r requirements.txt` jika `textual` belum ada, lalu `python app.py`. Jika `.ps1` buka di Notepad (rusak `ftype`), double-click `9Router-TUI.cmd` sebagai gantinya (bypass asosiasi).

### Opsi 3: `9Router-TUI.pyw` (butuh Python, Windows)

File `.pyw` terasosiasi ke `pythonw` — double-click akan spawn console baru via `CREATE_NEW_CONSOLE` dan jalankan `app.py`. Fallback jika `.bat` diblokir.

### Opsi 4: `9Router-TUI.ps1` (butuh Python, Windows)

`powershell -ExecutionPolicy Bypass -File 9Router-TUI.ps1` — auto-install deps. Jika double-click buka Notepad, fix: `ftype Microsoft.PowerShellScript.1="C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" "%1" %*` (admin).

| File | Butuh Python? | Cara Pakai |
|---|---|---|
| `dist/9Router-TUI.exe` | Tidak | Double-click langsung (Windows) |
| `dist/*.AppImage` | Tidak | `chmod +x` + double-click / `./*.AppImage` (Linux) |
| `9Router-TUI.bat` | Ya | Double-click (Windows) |
| `9Router-TUI.cmd` | Ya | Double-click — fix `.ps1` Notepad issue |
| `9Router-TUI.pyw` | Ya | Double-click (asosiasi `.pyw` ke Python Launcher) |
| `9Router-TUI.ps1` | Ya | `powershell -ExecutionPolicy Bypass -File 9Router-TUI.ps1` |
| `9Router-TUI.spec` | Untuk build | `pyinstaller 9Router-TUI.spec` |
| `build-appimage.sh` | Untuk build | `bash build-appimage.sh` (Linux) |

## Konfigurasi

**Precedence:** `CLI --url/--api-key` > `env NINEROUTER_URL/NINEROUTER_KEY` > `config.toml [server]` / `servers.json` / `config.toml [[servers]]` > default `http://localhost:20128`

**Tanpa konfigurasi:** `python app.py` langsung tampilkan **Server Picker** — pilih `Local` / `Tunnel` / `Custom` (isi URL + API key), lalu `Connect` atau `Save & Connect` (simpan ke `servers.json`).

**Multi-server:** Simpan banyak 9Router (Local, Tunnel, VPS) di `servers.json` atau `config.toml [[servers]]` — TUI bisa switch kapan saja dengan `s`.

```bash
# .env
NINEROUTER_URL=http://localhost:20128
NINEROUTER_KEY=sk-fa5f...
NINEROUTER_PASSWORD=  # jika dashboard pakai password

# config.toml
[server]
url = "http://localhost:20128"
api_key = ""
timeout = 15

# Multi-server (opsional)
# [[servers]]
# name = "Local"
# url = "http://localhost:20128"
# api_key = ""
# description = "Local 9Router (npm run dev)"
#
# [[servers]]
# name = "Tunnel"
# url = "https://distribute-jimmy-church-audit.trycloudflare.com"
# api_key = "sk-..."
# description = "Cloudflare Tunnel"
#
# [[servers]]
# name = "VPS"
# url = "https://9router.example.com"
# api_key = "sk-..."
# description = "My VPS"

# servers.json (alternatif, lihat servers.json.example)
# [
#   {"name":"Local","url":"http://localhost:20128","api_key":"","description":"Local"},
#   {"name":"VPS","url":"https://9router.example.com","api_key":"sk-...","description":"My VPS"}
# ]

[ui]
theme = "dark"
refresh_interval = 30
default_page = "dashboard"
```

Lihat `config.toml.example`, `servers.json.example`, dan `.env.example`.

## TUI Keybindings

| Key | Aksi |
|---|---|
| `q` | Quit |
| `r` | Refresh halaman aktif |
| `s` | **Switch Server** — buka picker (Local / Tunnel / Custom) |
| `1` | Overview |
| `2` | Providers |
| `3` | Nodes |
| `4` | Combos |
| `5` | Models |
| `6` | Keys |
| `7` | Usage |
| `8` | Settings |
| `9` | **Update** — version, update, Docker |
| `↑/↓` | Navigasi tabel |
| `Enter` | Lihat detail JSON baris terpilih / Connect di picker |
| `Tab` | Ganti tab |

## Lokasi 9Router

| Lokasi | URL |
|---|---|
| Localhost | `http://localhost:20128` (default, `npm run dev` di `9router-master/`) |
| Tunnel | `https://distribute-jimmy-church-audit.trycloudflare.com` (dari backup `tunnelUrl`) |
| VPS | `https://9router.example.com` |
| Docker | `http://9router:20128` |

## API Reference (yang dipakai TUI)

Semua via `client.py` — tidak tulis SQLite langsung.

| Method | Path | Deskripsi |
|---|---|---|
| `GET` | `/api/health` | `{ok:true}` |
| `GET` | `/api/providers` | List connections |
| `POST` | `/api/providers/test-batch` | Test batch |
| `GET` | `/api/provider-nodes` | List nodes |
| `GET` | `/api/combos` | List combos |
| `GET` | `/api/models` | Models + aliases |
| `GET` | `/v1/models` | OpenAI-compatible models |
| `GET` | `/api/keys` | Dashboard keys |
| `GET` | `/api/settings` | Settings |
| `GET` | `/api/usage/stats?period=7d` | Usage stats |
| `GET` | `/api/usage/history?limit=50` | History |
| `GET` | `/api/version` | Version |

## Troubleshooting

| Error | Fix |
|---|---|
| `Cannot reach 9Router at http://localhost:20128` | Pastikan 9Router jalan: `cd 9router-master/9router-master && npm run dev` (PORT=20128) |
| `401 Unauthorized` | Set `NINEROUTER_KEY` (Dashboard → Keys → copy `sk-...`) jika `requireApiKey=true` |
| `No module named 'textual'` | `pip install -r requirements.txt` |
| `No module named 'rich'` | `pip install rich` |
| Double-click `.exe` langsung close | Jalankan via `cmd` untuk lihat error: `dist\9Router-TUI.exe` — biasanya port/config salah |
| `.pyw` tidak jalan | Pastikan `.pyw` terasosiasi ke Python Launcher (`pyw`). Jika tidak, pakai `.bat` atau `.exe` |

## Update & Docker (Local & Remote VPS)

- **Version:** `GET /api/version` (current + latest dari npm `9router`, `hasUpdate`) + fallback `package.json` lokal + `https://registry.npmjs.org/9router/latest`
- **Update:** auto-detect `npm` / `source` (git pull + npm install + build) / `docker` (compose pull + up -d atau docker pull). **Local** langsung eksekusi, **remote VPS** via SSH (jika `ssh_host` diisi di `servers.json`).
- **Docker:** `docker ps` (containers), `docker images`, `docker logs --tail`, `docker pull`, `docker restart` / `compose restart`, `docker update` (pull + up -d) — semua bisa **local atau remote via SSH**.

**Remote VPS via SSH:** Tambahkan `ssh_host`/`ssh_user`/`ssh_key`/`compose_path` di `servers.json` atau `config.toml [[servers]]` — maka `update` & `docker` otomatis via `ssh user@host "docker ..."`.

```json
{
  "name": "VPS",
  "url": "https://9router.example.com",
  "api_key": "sk-...",
  "ssh_host": "1.2.3.4",
  "ssh_user": "root",
  "ssh_key": "~/.ssh/id_rsa",
  "compose_path": "/opt/9router/docker-compose.yml",
  "install_method": "docker"
}
```

```bash
# CLI — remote via SSH
python cli.py --server VPS version
python cli.py --server VPS update --dry-run
python cli.py --server VPS update --yes
python cli.py --server VPS docker status
python cli.py --server VPS docker logs --tail 100
python cli.py --server VPS docker restart
python cli.py --server VPS docker update --dry-run
```

TUI tab **Update** (key `9`): Check Version, Update (dry-run / now), Docker Status/Logs/Pull/Restart/Update — semua via `updater.py`. Jika server aktif adalah VPS dengan `ssh_host`, semua tombol otomatis via SSH (label `(remote)`).

## Docker

Alpine-based (`python:3.12-alpine`), image `helmiau/9router-tui` — repo `https://github.com/helmiau/9router-tui`.

```bash
# Build lokal
docker build -t helmiau/9router-tui:latest .

# TUI (interaktif)
docker run -it --rm \
  -e NINEROUTER_URL=http://host.docker.internal:20128 \
  -e NINEROUTER_KEY=sk-... \
  --add-host host.docker.internal:host-gateway \
  helmiau/9router-tui

# CLI
docker run --rm helmiau/9router-tui python cli.py health
docker run --rm helmiau/9router-tui python cli.py providers
docker run --rm -e NINEROUTER_URL=https://9router.example.com helmiau/9router-tui python cli.py version

# Dengan servers.json & SSH (untuk VPS Docker via SSH)
docker run -it --rm \
  -v ./servers.json:/app/servers.json:ro \
  -v ~/.ssh:/home/appuser/.ssh:ro \
  helmiau/9router-tui

# Compose
docker compose run --rm 9router-tui
docker compose run --rm 9router-tui python cli.py health
```

**GHCR & Docker Hub:** Workflow `.github/workflows/docker-publish.yml` build multi-arch (`linux/amd64`, `linux/arm64`) dan push ke `docker.io/helmiau/9router-tui` & `ghcr.io/helmiau/9router-tui` pada push ke `main`/`master` atau tag `v*`. Butuh secrets `DOCKERHUB_USERNAME` + `DOCKERHUB_TOKEN` (Docker Hub) — GHCR pakai `GITHUB_TOKEN` otomatis.

## Struktur

```
9router-tui/
  app.py              # Textual TUI (9 tabs: Overview, Providers, Nodes, Combos, Models, Keys, Usage, Settings, Update)
  cli.py              # Rich CLI (health, providers, nodes, combos, models, keys, usage, settings, test, dashboard, servers, version, update, docker)
  client.py           # NinerouterClient (semua REST API) + ServerProfile / probe
  updater.py          # Version check, update (npm/source/docker), docker status/logs/pull/restart
  9Router-TUI.spec    # PyInstaller spec — build double-click .exe (dist/9Router-TUI.exe)
  9Router-TUI.bat     # Double-click launcher (butuh Python) — auto pip install + python app.py
  9Router-TUI.pyw     # Double-click launcher .pyw (butuh Python) — spawn console baru
  Dockerfile          # Alpine (python:3.12-alpine) → helmiau/9router-tui
  docker-compose.yml  # TUI + CLI via compose
  .github/workflows/docker-publish.yml  # Build & push multi-arch
  requirements.txt
  config.toml.example
  servers.json.example
  .env.example
  README.md           # English (default)
  README_ID.md        # Indonesia
```

## Kebutuhan Sistem Minimum

| Komponen | Minimum | Rekomendasi |
|---|---|---|
| **OS** | Windows 10 / Ubuntu 20.04 / Debian 11 / macOS 12 | Windows 11 / Ubuntu 22.04+ / Debian 12+ |
| **CPU** | 1 vCPU (x64 atau ARM64) | 2 vCPU+ |
| **RAM** | 256 MB kosong (TUI ~60–120 MB) | 512 MB+ kosong |
| **Disk** | 150 MB (exe ~40 MB + deps Python) | 500 MB (dengan backup) |
| **Python** | 3.10+ (untuk `python app.py` / `cli.py`) | 3.12+ |
| **Terminal** | Mendukung UTF-8 + 80×24 | Windows Terminal / WezTerm / kitty / Alacritty (untuk clipboard OSC 52) |
| **Jaringan** | HTTP ke 9Router (`:20128`) | Latensi rendah ke host 9Router |
| **Docker** | Opsional — untuk image `helmiau/9router-tui` | Docker 24+ dengan Buildx (untuk multi-arch) |

> **Exe/AppImage standalone:** Tidak butuh Python — cukup double-click. Kebutuhan RAM/disk sama. AppImage butuh `libfuse2` di distro lama (`sudo apt install libfuse2`).

## Lisensi

Standalone dan independen — tanpa ketergantungan ke `omnexsync` atau proyek eksternal lain. Ikuti lisensi `9router-master` (MIT).

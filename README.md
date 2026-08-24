# 9Router TUI — Terminal Dashboard (Standalone)

Terminal UI untuk **9Router** (`9router-master` v0.5.55) — **tidak ada hubungan dengan `omnexsync`**. Standalone, hanya butuh `NINEROUTER_URL` + `NINEROUTER_KEY`.

Mencerminkan dashboard web resmi (`http://localhost:20128/dashboard`) di terminal: health, providers, nodes, combos, models, keys, usage, settings — semua via REST API `src/app/api/*` yang sama.

## Fitur

| Halaman | API | Deskripsi |
|---|---|---|
| **Overview** | `GET /api/health`, `GET /api/settings`, `GET /api/version`, `GET /api/provider-nodes`, `GET /api/providers`, `GET /api/combos` | Health, version, ringkasan providers/nodes/combos, test all |
| **Providers** | `GET /api/providers`, `POST /api/providers/test-batch` | Tabel connections (name, provider, priority, active, status), filter, detail JSON, test batch |
| **Nodes** | `GET /api/provider-nodes` | Tabel nodes (name, prefix, type, apiType, baseUrl), filter, detail |
| **Combos** | `GET /api/combos` | Tabel combos (name, kind, models count), detail models |
| **Models** | `GET /api/models`, `GET /v1/models` | Tabel models (model, provider, alias, caps), filter |
| **Keys** | `GET /api/keys` | Tabel dashboard keys (name, masked key, machineId) |
| **Usage** | `GET /api/usage/stats`, `GET /api/usage/history`, `GET /api/usage/chart` | Stats per period (today/24h/7d/30d/all), history table |
| **Settings** | `GET /api/settings` | Dump JSON settings (providerStrategies, tunnel, dll) |
| **Update** | `GET /api/version` + npm registry, `updater.py` | Version check, update (npm/source/docker — local & remote via SSH), Docker status/logs/pull/restart (local & VPS) |

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
# description = "Local 9Router"
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
default_page = "overview"
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
  Dockerfile          # Alpine (python:3.12-alpine) → helmiau/9router-tui
  docker-compose.yml  # TUI + CLI via compose
  .github/workflows/docker-publish.yml  # Build & push multi-arch
  requirements.txt
  config.toml.example
  servers.json.example
  .env.example
  README.md
```

## Lisensi

Standalone, tidak ada ketergantungan ke `omnexsync`. Ikuti lisensi `9router-master` (MIT).

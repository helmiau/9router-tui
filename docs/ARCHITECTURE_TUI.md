# Architecture — 9Router TUI (Modularization Plan)

> Current: `app.py` 2691 lines, `client.py` 477, `cli.py` 792, `updater.py` 590. Goal: split `app.py` into a package without breaking double-click / PyInstaller / AppImage.

## Current Layout

```
9router-tui/
  app.py              # 2691 lines — 11 panes + 8 modals + App
  client.py           # NinerouterClient + ServerProfile + config
  cli.py              # Rich CLI
  updater.py          # version / docker / SSH
  9Router-TUI.spec
  build-appimage.sh
  VERSION / _version.py
```

## Target Layout (modular)

```
9router-tui/
  app.py              # thin re-export: from tui.app import NineRouterTUI; app.run()
  tui/
    __init__.py
    app.py            # NineRouterTUI (App, BINDINGS, clipboard, _detail_plain)
    helpers.py        # mask_key, fmt_time, _store_plain, status_style, UID helpers
    panes/
      __init__.py
      overview.py     # OverviewPane
      endpoints.py    # EndpointsPane (Endpoint & Keys > Endpoints)
      provider_connections.py # ProviderConnectionsPane (Providers > Manage API Key)
      provider_models.py # ProviderModelsPane (Providers > Available Models)
      providers.py    # ProvidersPane (legacy, retained)
      nodes.py        # NodesPane
      combos.py       # CombosPane
      models.py       # ModelsPane
      keys.py         # KeysPane
      usage.py        # UsagePane
      settings.py     # SettingsPane + EDITABLE_FIELDS
      pools.py        # ProxyPoolsPane
      logs.py         # LogsPane
      update.py       # UpdatePane
    screens/
      __init__.py
      picker.py       # ServerPickerScreen
      settings_edit.py # SettingsEditScreen, SettingsRawScreen
      nodes.py        # NodeEditScreen, NodeUidEditScreen
      combos.py       # ComboEditScreen
      keys.py         # KeyCreateScreen, KeyShowScreen
      confirm.py      # ConfirmScreen
      tui_config.py   # TuiConfigScreen
      tui_servers.py  # TuiServersScreen, ServerEditScreen
      provider_strategy.py # ProviderStrategyScreen
      provider_connection_edit.py # ProviderConnectionEditScreen
      custom_model_edit.py # CustomModelEditScreen
      thinking_level.py # ThinkingLevelScreen
    backup.py         # backup/restore helpers (see below)
  client.py           # stays, or split into client/ (api, config, models)
  cli/
    __init__.py
    main.py           # argparse + dispatch
    commands/         # one file per command group
  updater.py          # stays, or split into updater/{version,docker,ssh}.py
```

## Migration Steps

1. **Create `tui/` package** — move helpers + panes + screens verbatim, keep imports relative (`from ..client import ...`, `from .helpers import ...`).
2. **Keep `app.py` as shim** — `from tui.app import NineRouterTUI; from tui.screens.picker import ServerPickerScreen` etc., so `python app.py` and `textual run app.py` still work. PyInstaller spec already collects `tui/**` via `collect_all`.
3. **Update spec** — add `datas` for `tui/` if needed, or rely on `collect_all("tui")`. Test `dist/9Router-TUI.exe --version`.
4. **Split `client.py` later** — `client/api.py` (NinerouterClient), `client/config.py` (ServerProfile, load/save), `client/models.py` (dataclasses). Keep `client.py` as re-export for backward compat.
5. **Split `cli.py`** — `cli/main.py` + `cli/commands/{providers,nodes,combos,keys,usage,settings,pools,logs,backup}.py`.
6. **Verify** — `python -m py_compile tui/**/*.py`, `python app.py --help`, `python cli.py --help`, `pyinstaller 9Router-TUI.spec --noconfirm`.

## Backup & Restore — db.sqlite + History

### Upstream DB (9Router)

- **Location:** `DATA_DIR/db/data.sqlite` (`DATA_DIR` = `~/.9router` or `$DATA_DIR` env, see `9router-master/src/lib/dataDir.js` + `src/lib/db/paths.js`).
- **Schema:** `src/lib/db/schema.js` — tables: `settings`, `providerConnections`, `providerNodes`, `proxyPools`, `apiKeys`, `combos`, `kv` (modelAliases/customModels/mitmAlias/pricing), `usageHistory`, `usageDaily`, `requestDetails`, `_meta`.
- **History:** `usageHistory` (per-request tokens/cost), `usageDaily` (aggregated), `requestDetails` (full request/response, large, excluded from safety backups).
- **Existing backup:** `src/lib/db/backup.js` — `backupDbLite()` via `ATTACH DATABASE` (excludes `requestDetails`), `makeBackupDir()`, `pruneOldBackups()` (keep 3). Triggered before schema migrations (`migrate.js`). No automated restore — manual copy.
- **Export/Import:** `src/lib/db/index.js:exportDb()` / `importDb()` — JSON dump of all tables (used by dashboard backup feature, also seen in `9router-backup/*.json`).

### TUI Backup/Restore Design

**Goal:** From TUI, backup and restore the full 9Router DB including history, without requiring the dashboard.

**APIs (if available):**
- `GET /api/backup` or `POST /api/backup/export` — if 9Router exposes export (check `src/app/api/` — currently no dedicated backup route, but `exportDb()` exists). Fallback: reconstruct via multiple `GET` calls (`/api/providers`, `/api/provider-nodes`, `/api/combos`, `/api/keys`, `/api/proxy-pools`, `/api/settings`, `/api/usage/history`, `/api/usage/logs`).
- `POST /api/backup/import` — if exists, else `POST` per-entity or direct file copy via SSH.

**Local file backup (works even without API):**
- If TUI runs on same host as 9Router (local or SSH), directly copy `data.sqlite`:
  - Local: `shutil.copy2(DATA_FILE, backup_path)` + `usage.json`/`request-details.json` if present.
  - Remote: `scp` or `ssh cat DATA_FILE > backup.sqlite` via `updater._run_remote`.
- Backup dir: `9router-backup/` (already gitignored) or user-chosen path. Naming: `9router-backup-YYYY-MM-DDTHH-MM-SSZ.json` (JSON export) or `.sqlite` (raw DB).

**TUI UI:**
- New **Backup** tab or **Update** sub-section: buttons **Backup Now** (JSON + SQLite), **Restore** (file picker), **List Backups**, **Prune**.
- For remote VPS: backup via SSH, download to local `9router-backup/`.
- Progress + error handling, never overwrite without confirm.

**Implementation sketch (`tui/backup.py`):**

```python
def get_data_file_path(profile: ServerProfile | None) -> str: ...
def backup_local(dest_dir: str) -> str: ...  # copy data.sqlite + export JSON
def backup_remote(profile: ServerProfile, dest_dir: str) -> str: ...  # via SSH
def restore_local(backup_path: str) -> None: ...  # copy back + restart hint
def restore_remote(profile: ServerProfile, backup_path: str) -> None: ...
def export_via_api(client: NinerouterClient) -> dict: ...  # fallback: GET all
def import_via_api(client: NinerouterClient, payload: dict) -> None: ...
```

**Safety:**
- Never auto-restore without explicit confirm + backup of current DB first.
- For `requestDetails` (large), offer "include history" toggle — default exclude for small backups, include for full history.

## Open Questions

- Should TUI also manage `DATA_DIR` location (env var) or just auto-detect?
- For remote restore, should we restart 9Router container automatically?
- Keep `9router-backup/` gitignored or add `9router-backup/*.json` example?

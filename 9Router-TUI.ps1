# 9Router TUI — Double-click launcher (PowerShell, zero-config)
# Klik kanan > Run with PowerShell, atau double-click jika .ps1 terasosiasi
# Tanpa config awal pun akan muncul Server Picker di TUI
# NOTE: Jika double-click membuka Notepad, fix: cmd /c "ftype Microsoft.PowerShellScript.1=`"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`" `"%1`" %*"
Set-Location $PSScriptRoot
$ErrorActionPreference = "Continue"

# ── Cari Python (python / py / python3) ──
$py = $null
foreach ($cand in @("python","py","python3")) {
    try { Get-Command $cand -ErrorAction Stop | Out-Null; $py = $cand; break } catch {}
}
if (-not $py) {
    Write-Host "[ERROR] Python tidak ditemukan! Install Python 3.10+ dari https://python.org" -ForegroundColor Red
    Write-Host "Centang 'Add python.exe to PATH' saat install." -ForegroundColor Yellow
    Write-Host "Alternatif: pakai dist\9Router-TUI.exe (standalone, tanpa Python)" -ForegroundColor Cyan
    Read-Host "Tekan Enter untuk keluar"
    exit 1
}
Write-Host "[INFO] Using $py" -ForegroundColor Cyan
& $py --version

# ── Auto-install deps jika belum ada (zero-config) ──
& $py -c "import textual" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[INFO] Dependencies belum ada — installing..." -ForegroundColor Yellow
    & $py -m pip install --disable-pip-version-check -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARN] pip install gagal, coba manual: $py -m pip install -r requirements.txt" -ForegroundColor Yellow
        Read-Host "Tekan Enter untuk keluar"
        exit 1
    }
}

# ── Jalankan TUI (tanpa config pun akan muncul Server Picker) ──
Write-Host "[INFO] Starting 9Router TUI..." -ForegroundColor Green
& $py app.py @args
$code = $LASTEXITCODE
Write-Host ""
Write-Host "[INFO] TUI exited with code $code" -ForegroundColor DarkGray
if ($code -ne 0) { Read-Host "Error — tekan Enter untuk keluar" }

# deploy.ps1 — Build the Vue frontend and deploy everything to the Pi.
#
# Usage:
#   .\deploy.ps1                  # full deploy
#   .\deploy.ps1 -SkipBuild       # skip npm build (deploy as-is)
#   .\deploy.ps1 -BackendOnly     # skip frontend entirely

param(
    [switch]$SkipBuild,
    [switch]$BackendOnly
)

$PI_USER = "administrator"
$PI_HOST = "192.168.178.240"
$PI_DIR  = "/home/administrator/EventView"
$SSH     = "$PI_USER@$PI_HOST"

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Fail($msg) { Write-Host "    ERROR: $msg" -ForegroundColor Red; exit 1 }

# ── 1. Build frontend ─────────────────────────────────────────────────

if (-not $BackendOnly) {
    if ($SkipBuild) {
        Step "Skipping build (-SkipBuild)"
    } else {
        Step "Building Vue frontend..."
        Push-Location "$PSScriptRoot\EventView.UI"
        npm run build
        if ($LASTEXITCODE -ne 0) { Fail "npm run build failed" }
        Pop-Location
        Ok "Build complete."
    }
}

# ── 2. Copy files in one scp batch ───────────────────────────────────
# Write a temp script that runs on the Pi after the files land.


Step "Copying files to Pi (one connection)..."

# Build the list of things to copy into a temp staging folder,
# then send everything in a single scp -r call.
$stage = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "eventview_deploy")
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory $stage | Out-Null
New-Item -ItemType Directory "$stage\EventScraper" | Out-Null

# Backend files
Copy-Item "$PSScriptRoot\EventScraper\api.py"           "$stage\EventScraper\"
Copy-Item "$PSScriptRoot\EventScraper\base_scraper.py"  "$stage\EventScraper\"
Copy-Item "$PSScriptRoot\EventScraper\models.py"        "$stage\EventScraper\"
Copy-Item "$PSScriptRoot\EventScraper\config.py"        "$stage\EventScraper\"
Copy-Item "$PSScriptRoot\EventScraper\main.py"          "$stage\EventScraper\"
Copy-Item "$PSScriptRoot\EventScraper\requirements.txt" "$stage\EventScraper\"
Copy-Item "$PSScriptRoot\EventScraper\scrapers" "$stage\EventScraper\scrapers" -Recurse

# Frontend
if (-not $BackendOnly) {
    Copy-Item "$PSScriptRoot\EventView.UI\dist" "$stage\EventView.UI" -Recurse
}

# Send everything in one shot
scp -r "$stage\*" "${SSH}:${PI_DIR}/"
if ($LASTEXITCODE -ne 0) { Fail "scp failed" }
Ok "Files copied."

# ── 3. Install deps + restart (one ssh call) ──────────────────────────

Step "Installing deps and restarting service..."
ssh $SSH "cd $PI_DIR/EventScraper && source venv/bin/activate && pip install -q -r requirements.txt && sudo systemctl restart eventview && sleep 2 && systemctl is-active eventview"
if ($LASTEXITCODE -ne 0) { Fail "Remote script failed. Run: ssh $SSH 'journalctl -u eventview -n 30'" }

# ── Cleanup ───────────────────────────────────────────────────────────

Remove-Item $stage -Recurse -Force

Write-Host "`nDeployed to http://${PI_HOST}:8000" -ForegroundColor Green

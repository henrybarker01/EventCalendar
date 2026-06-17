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

# ── 2. Deploy backend ─────────────────────────────────────────────────

Step "Copying backend files..."
scp "$PSScriptRoot\EventScraper\api.py"            "${SSH}:${PI_DIR}/EventScraper/api.py"
scp "$PSScriptRoot\EventScraper\base_scraper.py"   "${SSH}:${PI_DIR}/EventScraper/base_scraper.py"
scp "$PSScriptRoot\EventScraper\models.py"         "${SSH}:${PI_DIR}/EventScraper/models.py"
scp "$PSScriptRoot\EventScraper\config.py"         "${SSH}:${PI_DIR}/EventScraper/config.py"
scp "$PSScriptRoot\EventScraper\main.py"           "${SSH}:${PI_DIR}/EventScraper/main.py"
scp "$PSScriptRoot\EventScraper\requirements.txt"  "${SSH}:${PI_DIR}/EventScraper/requirements.txt"
ssh $SSH "mkdir -p ${PI_DIR}/EventScraper/scrapers"
foreach ($f in (Get-ChildItem "$PSScriptRoot\EventScraper\scrapers" -Filter "*.py")) {
    scp $f.FullName "${SSH}:${PI_DIR}/EventScraper/scrapers/$($f.Name)"
}
if ($LASTEXITCODE -ne 0) { Fail "Backend scp failed" }
Ok "Backend copied."

# ── 3. Deploy frontend ────────────────────────────────────────────────

if (-not $BackendOnly) {
    Step "Copying frontend..."
    # Wipe old dist first, then copy fresh
    ssh $SSH "rm -rf ${PI_DIR}/EventView.UI/dist && mkdir -p ${PI_DIR}/EventView.UI/dist"
    scp -r "$PSScriptRoot\EventView.UI\dist\." "${SSH}:${PI_DIR}/EventView.UI/dist/"
    if ($LASTEXITCODE -ne 0) { Fail "Frontend scp failed" }
    Ok "Frontend copied."
}

# ── 4. Install deps + restart ─────────────────────────────────────────

Step "Installing deps and restarting service..."
ssh $SSH "cd ${PI_DIR}/EventScraper && source venv/bin/activate && pip install -q -r requirements.txt && sudo systemctl restart eventview && sleep 2 && systemctl is-active eventview"
if ($LASTEXITCODE -ne 0) { Fail "Remote script failed. Run: ssh ${SSH} 'journalctl -u eventview -n 30'" }

Write-Host "`nDeployed to http://${PI_HOST}:8000" -ForegroundColor Green

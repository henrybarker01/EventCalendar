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

$PI_USER = "pi"
$PI_HOST = "192.168.178.240"
$PI_DIR  = "/home/pi/EventView"
$SSH     = "$PI_USER@$PI_HOST"

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Fail($msg) { Write-Host "    ERROR: $msg" -ForegroundColor Red; exit 1 }

# ── 1. Build frontend ─────────────────────────────────────────────────

if (-not $BackendOnly) {
    if ($SkipBuild) {
        Step "Skipping build (--SkipBuild)"
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

Step "Deploying backend (EventScraper/)..."
scp "$PSScriptRoot\EventScraper\api.py"          "${SSH}:${PI_DIR}/EventScraper/api.py"
scp "$PSScriptRoot\EventScraper\base_scraper.py" "${SSH}:${PI_DIR}/EventScraper/base_scraper.py"
scp "$PSScriptRoot\EventScraper\models.py"       "${SSH}:${PI_DIR}/EventScraper/models.py"
scp "$PSScriptRoot\EventScraper\config.py"       "${SSH}:${PI_DIR}/EventScraper/config.py"
scp "$PSScriptRoot\EventScraper\main.py"         "${SSH}:${PI_DIR}/EventScraper/main.py"
scp "$PSScriptRoot\EventScraper\requirements.txt" "${SSH}:${PI_DIR}/EventScraper/requirements.txt"
scp -r "$PSScriptRoot\EventScraper\scrapers"     "${SSH}:${PI_DIR}/EventScraper/"
if ($LASTEXITCODE -ne 0) { Fail "Backend scp failed" }
Ok "Backend files copied."

# ── 3. Deploy frontend ────────────────────────────────────────────────

if (-not $BackendOnly) {
    Step "Deploying frontend (EventView.UI/dist/)..."
    # Clear old dist first so removed files don't linger
    ssh $SSH "rm -rf ${PI_DIR}/EventView.UI/dist"
    scp -r "$PSScriptRoot\EventView.UI\dist" "${SSH}:${PI_DIR}/EventView.UI/dist"
    if ($LASTEXITCODE -ne 0) { Fail "Frontend scp failed" }
    Ok "Frontend files copied."
}

# ── 4. Install any new Python deps ───────────────────────────────────

Step "Installing Python dependencies on Pi..."
ssh $SSH "cd ${PI_DIR}/EventScraper && source venv/bin/activate && pip install -q -r requirements.txt"
if ($LASTEXITCODE -ne 0) { Fail "pip install failed" }
Ok "Dependencies up to date."

# ── 5. Restart the service ────────────────────────────────────────────

Step "Restarting eventview service..."
ssh $SSH "sudo systemctl restart eventview"
if ($LASTEXITCODE -ne 0) { Fail "systemctl restart failed" }

# Give it a moment then check status
Start-Sleep -Seconds 2
$status = ssh $SSH "systemctl is-active eventview"
if ($status -eq "active") {
    Ok "Service is running."
} else {
    Fail "Service failed to start. Run: ssh $SSH 'journalctl -u eventview -n 30'"
}

# ── Done ──────────────────────────────────────────────────────────────

Write-Host "`n✓ Deployed to http://${PI_HOST}:8000" -ForegroundColor Green

param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8001
)

$ErrorActionPreference = "Stop"
$backendDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $backendDirectory ".venv\Scripts\python.exe"
$apiUrl = "http://127.0.0.1:$Port"

if (-not (Test-Path $pythonPath)) {
    throw "Backend virtual environment not found. From the backend folder, run: python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt"
}

$listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($listener) {
    try {
        $health = Invoke-RestMethod -Uri "$apiUrl/health" -TimeoutSec 3
        if ($health.status -eq "ok" -and $health.service -eq "research-lens-api") {
            Write-Host "Research Lens API is already running at $apiUrl"
            return
        }
    }
    catch {
        Write-Host "Port $Port is in use, but the Research Lens API did not pass its health check."
    }

    throw "Cannot start Research Lens on port $Port because another process is using it. Stop that process or run: .\start_backend.ps1 -Port <available-port>, then set VITE_API_BASE_URL to http://127.0.0.1:<available-port> and restart Vite."
}

Set-Location $backendDirectory
Write-Host "Starting Research Lens API at $apiUrl"
Write-Host "Keep this PowerShell window open while using the frontend. Press Ctrl+C to stop the backend."
& $pythonPath -m uvicorn app.main:app --host 127.0.0.1 --port $Port

if ($LASTEXITCODE -ne 0) {
    throw "Uvicorn exited with code $LASTEXITCODE. Review the startup error above."
}

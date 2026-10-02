# ==============================================================================
# PROJECT CHLOE 2.0 // One-Click Activation Script for Abhishek
# Starts Ollama, launches FastAPI Gateway, verifies health, and opens Web HUD
# ==============================================================================

param (
    [switch]$Foreground,
    [switch]$NoBrowser
)

$WorkspaceDir = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
Set-Location $WorkspaceDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "       PROJECT CHLOE 2.0 // AGENTIC AI ASSISTANT          " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Environment & Storage Directory Setup
$DataDir = Join-Path $WorkspaceDir "backend\data"
if (!(Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}

# 2. Kill any stale processes on port 8000
Write-Host "`n[*] Ensuring port 8000 is clean and available..." -ForegroundColor Yellow
$staleConns = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($staleConns) {
    $stalePids = $staleConns.OwningProcess | Select-Object -Unique
    foreach ($spid in $stalePids) {
        if ($spid -gt 0) {
            Stop-Process -Id $spid -Force -ErrorAction SilentlyContinue
            Write-Host "[+] Cleared stale process (PID $spid) on port 8000." -ForegroundColor Green
        }
    }
    Start-Sleep -Seconds 1
}

# Stop any duplicate background run.py runners
$oldProcs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*run.py*" }
if ($oldProcs) {
    foreach ($op in $oldProcs) {
        Stop-Process -Id $op.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

# 3. Check & Start Ollama Engine
$OllamaExe = if (Get-Command ollama -ErrorAction SilentlyContinue) { (Get-Command ollama).Source } else { Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe" }
Write-Host "`n[*] Verifying Local Ollama Engine..." -ForegroundColor Yellow
try {
    $ollamaCheck = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
    Write-Host "[+] Ollama active with $($ollamaCheck.models.Count) local models ready." -ForegroundColor Green
} catch {
    if (Test-Path $OllamaExe) {
        Write-Host "[*] Starting local Ollama daemon..." -ForegroundColor Cyan
        Start-Process -FilePath $OllamaExe -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 2
        Write-Host "[+] Ollama engine initialized." -ForegroundColor Green
    } else {
        Write-Host "[!] Ollama executable not found. Proceeding with cloud modes." -ForegroundColor DarkYellow
    }
}

# 4. Resolve Python Virtual Environment
Write-Host "`n[*] Verifying Python Virtual Environment..." -ForegroundColor Yellow
$pyPath = Join-Path $WorkspaceDir ".venv\Scripts\python.exe"
if (Test-Path $pyPath) {
    $pythonCmd = $pyPath
    Write-Host "[+] Python Runtime: .venv ($pyPath)" -ForegroundColor Green
} else {
    $pythonCmd = "python"
    Write-Host "[+] Python Runtime: System Default" -ForegroundColor Yellow
}

# 5. Launch FastAPI Gateway
$runScript = Join-Path $WorkspaceDir "run.py"

if ($Foreground) {
    Write-Host "`n[*] Starting Chloe Gateway in Foreground mode (Ctrl+C to exit)..." -ForegroundColor Green
    & $pythonCmd $runScript
} else {
    Write-Host "`n[*] Launching Project Chloe Gateway in background..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-WindowStyle Hidden -NoExit -Command `"Set-Location '$WorkspaceDir'; & '$pythonCmd' run.py`""
    Write-Host "[+] Gateway persistent background daemon dispatched." -ForegroundColor Green

    # 6. Health-check loop: wait until server responds
    Write-Host "`n[*] Waiting for Chloe Gateway to become ready..." -ForegroundColor Yellow
    $serverReady = $false
    $retries = 0
    $maxRetries = 45

    while (-not $serverReady -and $retries -lt $maxRetries) {
        Start-Sleep -Seconds 1
        $retries++
        try {
            $statusResp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/status" -Method Get -TimeoutSec 2 -ErrorAction Stop
            if ($statusResp.status -eq "online") {
                $serverReady = $true
            }
        } catch {
            Write-Host -NoNewline "."
        }
    }

    if ($serverReady) {
        Write-Host "`n"
        Write-Host "==========================================================" -ForegroundColor Green
        Write-Host "       PROJECT CHLOE 2.0 IS ONLINE AND READY!             " -ForegroundColor Green
        Write-Host "==========================================================" -ForegroundColor Green
        
        Write-Host "`n[+] Web HUD Endpoint : http://localhost:8000" -ForegroundColor Cyan
        Write-Host "[+] WebSocket Stream : ws://localhost:8000/ws/audio" -ForegroundColor Cyan

        $localIps = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" }).IPAddress
        foreach ($ip in $localIps) {
            Write-Host "[+] Mobile / LAN URL : http://${ip}:8000" -ForegroundColor DarkCyan
        }

        Write-Host "`n[*] Cloud Engines    : Gemini 3.5 Flash and Groq 27B" -ForegroundColor White
        Write-Host "[*] Local Models     : Qwen2.5-Coder:7b, Qwen2.5-VL:3b, Qwen3:0.6b" -ForegroundColor White
        Write-Host "[*] Stop Services    : Run .\stop.ps1 at any time" -ForegroundColor Yellow

        if (-not $NoBrowser) {
            Write-Host "`n[*] Opening Web HUD in your default browser..." -ForegroundColor Cyan
            Start-Process "http://localhost:8000"
        }
    } else {
        Write-Host "`n[!] Server did not respond within $maxRetries seconds." -ForegroundColor Red
        Write-Host "[!] Run .\start.ps1 -Foreground to view detailed startup logs." -ForegroundColor Yellow
    }
}

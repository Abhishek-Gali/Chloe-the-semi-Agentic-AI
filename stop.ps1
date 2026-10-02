# ==============================================================================
# PROJECT CHLOE // One-Click Stop Script for Abhishek
# ==============================================================================

Write-Host "==========================================================" -ForegroundColor Red
Write-Host "       🛑 SHUTTING DOWN PROJECT CHLOE 2.0 SERVICES        " -ForegroundColor Red
Write-Host "==========================================================" -ForegroundColor Red

# 1. Stop Python Gateway processes running run.py or listening on port 8000
Write-Host "`n[*] Terminating Project Chloe FastAPI Gateway..." -ForegroundColor Yellow

$portConnections = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($portConnections) {
    $pids = $portConnections.OwningProcess | Select-Object -Unique
    foreach ($procId in $pids) {
        if ($procId -gt 0) {
            try {
                $procName = (Get-Process -Id $procId -ErrorAction SilentlyContinue).ProcessName
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                Write-Host "[+] Stopped process $procName (PID: $procId) listening on port 8000." -ForegroundColor Green
            } catch {
                Write-Host "[!] Could not stop process PID $procId." -ForegroundColor Red
            }
        }
    }
} else {
    Write-Host "[*] No active gateway listener found on port 8000." -ForegroundColor Gray
}

# Stop any python processes explicitly running run.py
$pythonProcs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*run.py*" }
foreach ($p in $pythonProcs) {
    try {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "[+] Stopped Chloe Python runner (PID: $($p.ProcessId))." -ForegroundColor Green
    } catch {}
}

# 2. Stop Ollama Engine background processes
Write-Host "`n[*] Checking Ollama Engine background processes..." -ForegroundColor Yellow
$ollamaProcs = Get-Process -Name "ollama*" -ErrorAction SilentlyContinue
if ($ollamaProcs) {
    foreach ($op in $ollamaProcs) {
        try {
            Stop-Process -Id $op.Id -Force -ErrorAction SilentlyContinue
            Write-Host "[+] Stopped Ollama process ($($op.ProcessName) PID: $($op.Id))." -ForegroundColor Green
        } catch {
            Write-Host "[!] Could not stop Ollama process PID $($op.Id)." -ForegroundColor Red
        }
    }
} else {
    Write-Host "[*] Ollama engine is not running." -ForegroundColor Gray
}

Write-Host "`n==========================================================" -ForegroundColor Red
Write-Host "       ✅ ALL CHLOE 2.0 SERVICES STOPPED CLEANLY          " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Red

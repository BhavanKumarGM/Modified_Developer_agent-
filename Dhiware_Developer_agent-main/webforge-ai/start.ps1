# WebForge AI — Start Script (PowerShell)
Write-Host "Starting WebForge AI..." -ForegroundColor Cyan

# Start backend — binds to 127.0.0.1 by default (see backend/.env / HOST).
# This app has no authentication; do not change HOST to 0.0.0.0 unless you
# understand that exposes it, unauthenticated, to your whole network.
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
  "cd '$PSScriptRoot\backend'; venv\Scripts\python -m app.main" `
  -WindowStyle Normal

Start-Sleep -Seconds 2

# Start frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
  "cd '$PSScriptRoot\frontend'; npm run dev" `
  -WindowStyle Normal

Write-Host ""
Write-Host "WebForge AI is starting up:" -ForegroundColor Green
Write-Host "  Frontend : http://localhost:5173" -ForegroundColor White
Write-Host "  Backend  : http://127.0.0.1:8000 (loopback only, no auth)" -ForegroundColor White
Write-Host "  API Docs : http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "Make sure Ollama is running: ollama serve" -ForegroundColor Yellow

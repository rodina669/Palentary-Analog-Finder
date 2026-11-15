$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "analog-finder"

python -m pip install -r (Join-Path $backend "requirements.txt")
Start-Process python -ArgumentList "run.py" -WorkingDirectory $backend
Start-Process npm -ArgumentList "run","dev" -WorkingDirectory $frontend
Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:5173"
Write-Host "Backend: http://127.0.0.1:8000"
Write-Host "App:     http://127.0.0.1:5173"

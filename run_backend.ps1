Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "Starting Multi-Cloud Disaster Recovery Backend (Python 3.10)" -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Set-Location -Path "$PSScriptRoot\backend"
& "C:\Users\Admin\AppData\Local\Programs\Python\Python310\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload


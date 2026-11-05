Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "Starting Celery Asynchronous Replication Worker (Windows solo pool)" -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Set-Location -Path "$PSScriptRoot\backend"
& "C:\Users\Admin\AppData\Local\Programs\Python\Python310\python.exe" -m celery -A app.workers.celery_app.celery_app worker --loglevel=info -P solo


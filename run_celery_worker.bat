@echo off
echo ====================================================================
echo Starting Celery Asynchronous Replication Worker (Windows solo pool)
echo ====================================================================
cd /d "%~dp0backend"
"C:\Users\Admin\AppData\Local\Programs\Python\Python310\python.exe" -m celery -A app.workers.celery_app.celery_app worker --loglevel=info -P solo
pause


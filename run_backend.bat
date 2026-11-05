@echo off
echo ====================================================================
echo Starting Multi-Cloud Disaster Recovery Backend (Python 3.10)
echo ====================================================================
cd /d "%~dp0backend"
"C:\Users\Admin\AppData\Local\Programs\Python\Python310\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause


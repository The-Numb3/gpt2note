@echo off
set PYTHONUTF8=1
uvicorn server.app:app --reload --port 8000

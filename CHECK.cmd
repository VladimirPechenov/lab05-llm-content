@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -3.12 -m venv .venv
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m ruff check .
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pytest
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m lab05.audit

@echo off
REM ============================================================
REM Ejecuta el pipeline ETL en Windows (por ejemplo, desde el
REM Programador de tareas).
REM
REM Usa la carpeta donde esta este archivo, de modo que el proyecto
REM puede moverse o clonarse en otra ruta sin editarlo.
REM
REM Interprete de Python, en orden de prioridad:
REM   1. Variable de entorno ETL_PYTHON
REM   2. Entorno conda "data_engineering" del usuario
REM   3. "python" del PATH
REM ============================================================
setlocal

cd /d "%~dp0"

if not defined ETL_PYTHON if exist "%USERPROFILE%\anaconda3\envs\data_engineering\python.exe" set "ETL_PYTHON=%USERPROFILE%\anaconda3\envs\data_engineering\python.exe"
if not defined ETL_PYTHON set "ETL_PYTHON=python"

"%ETL_PYTHON%" -m src.ejecutar_pipeline

exit /b %ERRORLEVEL%

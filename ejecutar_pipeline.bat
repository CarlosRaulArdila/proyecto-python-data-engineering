
@echo off

cd /d "C:\Users\User\Documents\proyecto_python_data_engineering"

"C:\Users\User\anaconda3\envs\data_engineering\python.exe" src\ejecutar_pipeline.py

exit /b %ERRORLEVEL%

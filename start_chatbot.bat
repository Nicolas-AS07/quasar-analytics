@echo off
echo Iniciando ChatBot Inteligente...
echo.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m streamlit run main.py
pause
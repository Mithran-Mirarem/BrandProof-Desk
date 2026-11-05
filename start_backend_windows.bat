@echo off
cd /d %~dp0backend
if not exist .venv py -3 -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
if not exist .env copy .env.example .env
echo Open .env to add ADAPTION_API_KEY if available.
python run.py
pause

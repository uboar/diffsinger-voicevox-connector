@echo off
chcp 65001 > nul
cd /d %~dp0\..
set PYTHONPATH=src;%PYTHONPATH%
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe -m diffsinger_engine
) else (
  python -m diffsinger_engine
)
if errorlevel 1 (
  echo.
  echo エラーが発生しました。ログ logs\connector.log を確認してください。
  pause
)

@echo off
chcp 65001 >nul
echo ================================================
echo   A股全历史走势分析工具 v4
echo ================================================
echo.

start http://localhost:6789/?code=600085
python "C:\Users\CRQ\Documents\codex 2\stock_history_server.py"

pause

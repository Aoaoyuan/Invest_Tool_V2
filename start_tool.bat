@echo off
chcp 65001 >nul
echo ================================================
echo   A股全历史走势分析工具
echo ================================================
echo.
echo   正在启动服务器...
echo   浏览器将自动打开
echo.
echo   提示: 关闭本窗口即可停止服务
echo   数据来源: 腾讯证券API
echo ================================================
echo.

start http://localhost:6789/?code=600085
python "C:UsersCRQDocumentscodex 2stock_history_server.py"

pause

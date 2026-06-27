@echo off
cd /d "%~dp0"
echo ========================================
echo   ETF轮动策略回测系统 (Streamlit)
echo   访问: http://localhost:8501/
echo ========================================
echo.
python -m streamlit run streamlit_app.py --server.port 8501 --server.headless true --browser.gatherUsageStats false
pause

@echo off
REM Double-click to run the full pipeline with Anaconda Python (about 5 minutes).
call "%USERPROFILE%\anaconda3\Scripts\activate.bat" "%USERPROFILE%\anaconda3"
cd /d "%~dp0.."
python run_all.py --skip-download
echo.
echo Finished. Results are in output\tables and output\figures. You can close this window.
pause

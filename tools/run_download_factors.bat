@echo off
REM Double-click to download Fama-French + q-factor data (uses Anaconda Python).
call "%USERPROFILE%\anaconda3\Scripts\activate.bat" "%USERPROFILE%\anaconda3"
cd /d "%~dp0.."
python 01_download_factors.py
echo.
echo Finished. You can close this window.
pause

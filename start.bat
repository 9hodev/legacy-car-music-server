@echo off
title Local Music Server & Audio Studio
cd /d "%~dp0"
echo =================================================
echo  Starting Local Music Server ^& Audio Studio...
echo =================================================
python server.py
pause

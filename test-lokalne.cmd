@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 goto python
py -3 demo.py
goto end
:python
python demo.py
:end
if errorlevel 1 echo Pro spusteni potrebujes Python 3.10 nebo novejsi.
pause

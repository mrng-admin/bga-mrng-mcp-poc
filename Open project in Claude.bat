@echo off
setlocal

rem Opent Claude Desktop in Code-modus, gekoppeld aan de map waarin dit .bat-bestand staat.
rem %~dp0 lost altijd de eigen locatie op, dus dit werkt automatisch in elke gedupliceerde projectmap.

set "MAPPAD=%~dp0"
if "%MAPPAD:~-1%"=="\" set "MAPPAD=%MAPPAD:~0,-1%"

echo Project wordt geopend in Claude Desktop...
echo %MAPPAD%

powershell -NoProfile -Command "$p = [System.Uri]::EscapeDataString('%MAPPAD%'); Start-Process ('claude://code/new?folder=' + $p)"

timeout /t 2 >nul

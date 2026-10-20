@echo off
rem Starter fuer das Spec Agent Kit (vom Kit verwaltet, siehe .spec-agent\lock.json).
rem Sucht uv: SAK_UV, PATH, dann bekannte Orte. Reicht den Exit-Code von sak durch.
setlocal EnableExtensions DisableDelayedExpansion
set "SAK_HERE=%~dp0"
set "SAK_FOUND="

if not defined SAK_UV goto :search
if exist "%SAK_UV%" goto :useenv
echo sak: SAK_UV zeigt auf keine Datei: "%SAK_UV%" 1>&2
endlocal
exit /b 127

:useenv
set "SAK_FOUND=%SAK_UV%"
goto :run

:search
for %%P in (uv.exe) do set "SAK_FOUND=%%~$PATH:P"
if defined SAK_FOUND goto :run
if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\uv.exe" set "SAK_FOUND=%LOCALAPPDATA%\Microsoft\WinGet\Links\uv.exe"
if defined SAK_FOUND goto :run
for /d %%D in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_*") do if exist "%%~D\uv.exe" set "SAK_FOUND=%%~D\uv.exe"
if defined SAK_FOUND goto :run
if exist "%USERPROFILE%\.local\bin\uv.exe" set "SAK_FOUND=%USERPROFILE%\.local\bin\uv.exe"
if defined SAK_FOUND goto :run
if exist "%USERPROFILE%\.cargo\bin\uv.exe" set "SAK_FOUND=%USERPROFILE%\.cargo\bin\uv.exe"
if defined SAK_FOUND goto :run
echo sak: uv wurde nicht gefunden. Installation: winget install --id astral-sh.uv -e 1>&2
echo sak: alternativ SAK_UV auf den Pfad von uv.exe setzen. 1>&2
endlocal
exit /b 127

:run
"%SAK_FOUND%" run --project "%SAK_HERE%engine" sak %*
set "SAK_RC=%ERRORLEVEL%"
endlocal & exit /b %SAK_RC%

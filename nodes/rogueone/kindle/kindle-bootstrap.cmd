@echo off
REM B165 — first-logon bootstrap, run by autounattend.xml's FirstLogonCommands off the config CD.
REM Copies the Kindle scripts + injected MinIO creds from the CD to C:\kindle, then runs the setup.
REM %~d0 = the drive letter of THIS batch file = the config CD.
set SRC=%~d0
mkdir C:\kindle 2>nul
copy /y "%SRC%\kindle-vm-setup.ps1" C:\kindle\ >nul
copy /y "%SRC%\kindle-extract.ps1" C:\kindle\ >nul
copy /y "%SRC%\kindle-autorun.ps1" C:\kindle\ >nul
copy /y "%SRC%\kindle-minio.env"  C:\kindle\ >nul 2>nul
powershell -ExecutionPolicy Bypass -File C:\kindle\kindle-vm-setup.ps1 >> C:\kindle\setup.log 2>&1

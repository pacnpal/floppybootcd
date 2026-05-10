@echo off
REM Undo the file-association set by register-fbcd-windows.bat.
REM Removes the per-user .fbcd handler from HKCU. Other applications
REM that have registered themselves for .fbcd in HKCU\Software\Classes
REM are left alone.

echo Removing per-user .fbcd file association for FloppyBootCD...

reg delete "HKCU\Software\Classes\.fbcd" /f >nul 2>&1
reg delete "HKCU\Software\Classes\FloppyBootCD.Project" /f >nul 2>&1

ie4uinit.exe -ClearIconCache >nul 2>&1
ie4uinit.exe -show >nul 2>&1

echo Done. .fbcd files will fall back to whatever else is registered
echo (or to the "Open With..." dialog if nothing else is).
pause
exit /b 0

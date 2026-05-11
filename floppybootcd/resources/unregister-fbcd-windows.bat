@echo off
REM Undo the file-association set by register-fbcd-windows.bat.
REM Per-user (HKCU) only — never touches HKLM.
REM
REM .fbcd handling: only unbind the .fbcd extension when the current
REM default ProgID is FloppyBootCD.Project. If another application
REM has since claimed .fbcd for itself (writing its own ProgID into
REM HKCU\Software\Classes\.fbcd), we leave that alone — unconditional
REM delete used to clobber it. The check uses `reg query /ve` and
REM matches the literal "FloppyBootCD.Project" string with findstr;
REM if the key is missing or owned by someone else, findstr exits
REM non-zero and the && short-circuits before reg delete runs.
REM
REM The FloppyBootCD.Project key itself is uniquely-named, so
REM deleting it unconditionally is safe.

echo Removing per-user .fbcd file association for FloppyBootCD...

reg query "HKCU\Software\Classes\.fbcd" /ve 2>nul ^
    | findstr /c:"FloppyBootCD.Project" >nul ^
    && reg delete "HKCU\Software\Classes\.fbcd" /f >nul 2>&1

reg delete "HKCU\Software\Classes\FloppyBootCD.Project" /f >nul 2>&1

ie4uinit.exe -ClearIconCache >nul 2>&1
ie4uinit.exe -show >nul 2>&1

echo Done. .fbcd files will fall back to whatever else is registered
echo (or to the "Open With..." dialog if nothing else is).
pause
exit /b 0

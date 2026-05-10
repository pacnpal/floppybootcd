@echo off
REM Register .fbcd files as FloppyBootCD projects, current-user scope.
REM
REM Run this from the folder containing floppybootcd.exe (the script
REM uses %~dp0 to resolve to its own directory at run time, so the
REM registry path always matches wherever the user extracted the zip).
REM
REM Why a .bat instead of a .reg file? .reg files store registry
REM values as REG_SZ by default, and REG_SZ values do NOT expand
REM %LOCALAPPDATA% / %~dp0 / any other env vars when Windows looks
REM them up. A registered handler with %LOCALAPPDATA% in a REG_SZ
REM value would launch a literal-path-not-found error on every
REM .fbcd double-click. `reg add /t REG_EXPAND_SZ` writes the
REM correct expandable-string type that Explorer actually expands.
REM
REM Per-user (HKCU) keys — no admin / UAC prompt.

setlocal

REM %~dp0 resolves to the directory holding this .bat *with* a
REM trailing backslash, on every drive (C:\, D:\foo\, \\server\share\,
REM etc.). We deliberately keep that trailing slash and concatenate
REM file names directly — "%INSTALL_DIR%floppybootcd.exe" — to dodge
REM the drive-root edge case: stripping the trailing slash off "C:\"
REM yields "C:", which CMD then resolves as drive-relative ("the
REM current dir on C:") instead of "C:\". Keeping the slash makes
REM "C:\floppybootcd.exe" and "D:\foo\floppybootcd.exe" both correct
REM with the same construction.
set "INSTALL_DIR=%~dp0"

if not exist "%INSTALL_DIR%floppybootcd.exe" (
    echo ERROR: floppybootcd.exe not found in %INSTALL_DIR%.
    echo Place register-fbcd-windows.bat next to floppybootcd.exe and re-run.
    pause
    exit /b 1
)

echo Registering .fbcd file association for the current user...
echo Install path: %INSTALL_DIR%

reg add "HKCU\Software\Classes\.fbcd" /ve /d "FloppyBootCD.Project" /f >nul || goto :err
reg add "HKCU\Software\Classes\FloppyBootCD.Project" /ve /d "FloppyBootCD Project" /f >nul || goto :err
reg add "HKCU\Software\Classes\FloppyBootCD.Project\DefaultIcon" /ve /t REG_EXPAND_SZ /d "\"%INSTALL_DIR%floppybootcd.exe\",0" /f >nul || goto :err
reg add "HKCU\Software\Classes\FloppyBootCD.Project\shell\open" /ve /d "Open with FloppyBootCD" /f >nul || goto :err
reg add "HKCU\Software\Classes\FloppyBootCD.Project\shell\open\command" /ve /t REG_EXPAND_SZ /d "\"%INSTALL_DIR%floppybootcd.exe\" \"%%1\"" /f >nul || goto :err

REM Notify Shell so Explorer refreshes its file-type cache immediately
REM without needing a logout. Best-effort: not all Windows versions
REM expose this, hence the redirect.
ie4uinit.exe -ClearIconCache >nul 2>&1
ie4uinit.exe -show >nul 2>&1

echo.
echo Success. Double-click any .fbcd file in Explorer to open it with FloppyBootCD.
echo To revert, run unregister-fbcd-windows.bat from this same folder.
pause
exit /b 0

:err
echo.
echo Registration failed at "reg add" — check the message above.
pause
exit /b 1

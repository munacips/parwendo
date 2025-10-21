@echo off
REM deploy.bat - simple deploy script: git add, commit with message, push to main
REM Usage: deploy "Commit message"

if "%~1"=="" (
	echo.
	echo Usage: %~nx0 "commit message"
	echo Example: %~nx0 "Added login"
	echo.
	exit /b 1
)

set "MSG=%~1"
echo Committing with message: "%MSG%"

git add .
git commit -m "%MSG%"
if %ERRORLEVEL% neq 0 (
	echo.
	echo git commit failed. Aborting push.
	echo Run: git status  to inspect and fix any issues.
	exit /b %ERRORLEVEL%
)

git push origin main

endlocal 2>nul || rem endlocal for older cmd shells
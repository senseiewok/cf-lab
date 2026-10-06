@echo off
rem Sensei Ewok's CF Lab - setup for Windows. Needs only cmd.exe and Git.
rem
rem   setup.cmd            clone cf-skills and cf-research if missing, make the cf-lab-files folder
rem   setup.cmd /nopause   the same, without waiting for a key when started by double-click
rem
rem Layout it creates next to this checkout (the "root" folder):
rem   <root>\cf-lab  (this repo)   <root>\cf-skills   <root>\cf-research   <root>\cf-lab-files
rem The cf-lab-files folder is not a git repository and is never published. The workspace file,
rem cf-lab.code-workspace, is tracked in this repo and is not generated. Exit codes: 0 done, 1 failed, 2 usage error.
rem
rem Written without parenthesised blocks on purpose: a path such as "C:\Program Files (x86)\..." would
rem end a block early.
setlocal EnableExtensions DisableDelayedExpansion

rem Resolve the script folder first: SHIFT in the argument loop also shifts %0, which would break %~dp0.
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
rem Windows tools by full path: with Git for Windows usr\bin on PATH, a bare find or more is the GNU one and behaves differently.
set "SYS=%SystemRoot%\System32"
set "NOPAUSE=%LAB_NO_PAUSE%"
:args
if "%~1"=="" goto args_done
if /i "%~1"=="/nopause" set "NOPAUSE=1" & shift & goto args
echo usage: setup.cmd [/nopause]
set "RC=2" & goto finish
:args_done

set "ORG=senseiewok"
set "FILES=%ROOT%\cf-lab-files"

rem LAB_GIT is a test seam: the self-test points it at a stub. Unset, plain git is used and must exist.
if defined LAB_GIT goto have_git
"%SYS%\where.exe" git >nul 2>&1
if errorlevel 1 echo error: Git is required and was not found. Install it with: winget install --id Git.Git -e & set "RC=1" & goto finish
set "LAB_GIT=git"
:have_git

echo Setting up Sensei Ewok's CF Lab...
call :ensure_repo cf-skills
if errorlevel 1 set "RC=1" & goto finish
call :ensure_repo cf-research
if errorlevel 1 set "RC=1" & goto finish
call :ensure_files
if errorlevel 1 set "RC=1" & goto finish

echo.
echo Done. Open cf-lab.code-workspace in this checkout in VS Code.
set "RC=0" & goto finish

:ensure_repo
set "DIR=%ROOT%\%~1"
if not exist "%DIR%" goto clone_repo
if not exist "%DIR%\.git" echo error: %~1 exists but is not a git checkout; no files were overwritten. & exit /b 1
echo - %~1 already present
exit /b 0
:clone_repo
echo - Cloning %ORG%/%~1 ...
%LAB_GIT% clone "https://github.com/%ORG%/%~1" "%DIR%"
if errorlevel 1 echo error: Failed to clone %ORG%/%~1. & exit /b 1
exit /b 0

:ensure_files
if exist "%FILES%" if not exist "%FILES%\" echo error: "%FILES%" exists but is a file. & exit /b 1
if exist "%FILES%\" goto files_present
md "%FILES%"
if errorlevel 1 echo error: could not create the cf-lab-files folder. & exit /b 1
echo - Created cf-lab-files
goto files_subdirs
:files_present
echo - cf-lab-files already present
:files_subdirs
for %%D in (memory scratch) do if not exist "%FILES%\%%D\" md "%FILES%\%%D"
if exist "%FILES%\README.md" exit /b 0
> "%FILES%\README.md" echo cf-lab-files
>> "%FILES%\README.md" echo This folder is local to this machine. It is not a git repository and is never published.
>> "%FILES%\README.md" echo memory/   handoff.md (session notes), machine.md (paths, local model), observations.md (dated candidates)
>> "%FILES%\README.md" echo scratch/  disposable; search skips it
>> "%FILES%\README.md" echo Never put here: API keys or .env files, patient data or any patient-level rows, private site or deploy details,
>> "%FILES%\README.md" echo transcripts or raw model output, third-party instructions, personal email addresses.
>> "%FILES%\README.md" echo Nothing here is the only copy of anything you cannot lose: there is no history and no backup.
>> "%FILES%\README.md" echo Rules and lessons live in the repos (AGENTS.md, skills, tasks/board.json), not here. If this disagrees with the board, the board wins.
exit /b 0

:finish
rem Pause only when started by double-click (cmd.exe /c), so the window does not vanish with the message.
if "%NOPAUSE%"=="" echo %cmdcmdline% | "%SYS%\find.exe" /i " /c " >nul && pause
endlocal & exit /b %RC%

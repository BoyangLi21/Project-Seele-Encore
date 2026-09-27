@echo off
setlocal
title Project SEELE - R41 Whole-floor circulation and connected stance motion
pushd "%~dp0"
if errorlevel 1 exit /b 1
set "SEELE_CHECK="
set "SEELE_SHADERS=--city-shaders"
set "SEELE_EXIT_CODE=1"
:args
if "%~1"=="" goto ready
if /i "%~1"=="--check" (
    set "SEELE_CHECK=--prepare-only"
) else if /i "%~1"=="--no-shaders" (
    set "SEELE_SHADERS="
) else if /i "%~1"=="--city-shaders" (
    set "SEELE_SHADERS=--city-shaders"
) else goto usage
shift
goto args
:ready
if not exist "run\saves\SEELE_R41_WORLD\r41_ready.json" (
    echo ERROR: The final R41 world has not been installed and packaged yet.
    goto failed
)
if not exist "run\resourcepacks\eva_real_model\pack.mcmeta" (
    echo ERROR: The private EVA model pack is missing.
    goto failed
)
for %%F in (eva_combat_capture_r31.json eva_combat_capture_r31_un00.json eva_combat_capture_r31_un01.json angel_grip_r31.json eva_recovery_r31.json eva_gameplay_r32_0.json eva_gameplay_r32_1.json eva_gameplay_r32_2.json eva_gameplay_r32_3.json eva_gameplay_r32_4.json sachiel_gameplay_r32.json articulated_bodies_r35.json) do (
    if not exist "run\projectseele-local-maps\%%F" (
        echo ERROR: Missing R41 runtime profile: %%F
        goto failed
    )
)
set "SEELE_PYTHON="
if exist "C:\Python314\python.exe" set "SEELE_PYTHON=C:\Python314\python.exe"
if not defined SEELE_PYTHON for %%P in (python.exe) do set "SEELE_PYTHON=%%~$PATH:P"
if not defined SEELE_PYTHON (
    echo ERROR: Python is required.
    goto failed
)
set "PYTHONUTF8=1"
set "OPENBLAS_NUM_THREADS=1"
"%SEELE_PYTHON%" tools\check_runtime_r41.py
if errorlevel 1 goto failed
echo R41 runtime - protocol 44. Use the matching R41 client and server.
echo Guide: %CD%\docs\MANUAL_ACCEPTANCE_R41.md
echo World: SEELE_R41_WORLD
"%SEELE_PYTHON%" tools\launch_rendered_client_r17.py --world SEELE_R41_WORLD --heap 6G --gradle-offline %SEELE_SHADERS% %SEELE_CHECK%
set "SEELE_EXIT_CODE=%ERRORLEVEL%"
if not "%SEELE_EXIT_CODE%"=="0" goto failed
goto done
:usage
echo Usage: start_eva_test_r41.bat [--check] [--city-shaders] [--no-shaders]
set "SEELE_EXIT_CODE=2"
goto done
:failed
echo.
echo Check the error above and run\logs\latest.log.
if "%SEELE_CHECK%"=="" pause
:done
popd
exit /b %SEELE_EXIT_CODE%

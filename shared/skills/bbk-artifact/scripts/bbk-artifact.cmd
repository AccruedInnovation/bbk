@echo off
setlocal
if defined BBK_PYTHON goto use_env
where py >nul 2>nul
if not errorlevel 1 goto use_py
where python >nul 2>nul
if not errorlevel 1 goto use_python
where python3 >nul 2>nul
if not errorlevel 1 goto use_python3
>&2 echo {"schema":"bbk.artifact-skill-binding.v1","status":"BLOCKED","code":"PYTHON_NOT_RESOLVED","message":"No Python interpreter was found for the BBK artifact skill wrapper.","smallest_next_action":"Set BBK_PYTHON to the Python executable recorded by the BBK installation."}
exit /b 127

:use_env
"%BBK_PYTHON%" -S -B -X utf8 "%~dp0bbk_artifact.py" %*
exit /b %errorlevel%

:use_py
py -3 -S -B -X utf8 "%~dp0bbk_artifact.py" %*
exit /b %errorlevel%

:use_python
python -S -B -X utf8 "%~dp0bbk_artifact.py" %*
exit /b %errorlevel%

:use_python3
python3 -S -B -X utf8 "%~dp0bbk_artifact.py" %*
exit /b %errorlevel%

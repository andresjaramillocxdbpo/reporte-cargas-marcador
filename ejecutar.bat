@echo off
REM Ejecuta el reporte de cargas: MySQL + Excel + correo.
REM Lo llama la tarea programada; tambien sirve con doble clic.
REM Sin argumentos reporta el dia anterior.
REM Se le pueden pasar argumentos, por ejemplo:  ejecutar.bat --fecha 2026-10-23

REM Ruta completa de Python: el Programador de tareas no siempre tiene el mismo PATH.
set "PYTHON=C:\Users\AndresFelipeJaramill\AppData\Local\Programs\Python\Python312\python.exe"

cd /d "%~dp0"
if not exist logs mkdir logs

echo ===== %date% %time% ===== >> "logs\ejecutar_bat.log"
"%PYTHON%" -m reporte_cargas %* >> "logs\ejecutar_bat.log" 2>&1
set "CODIGO=%errorlevel%"
echo ===== fin, codigo %CODIGO% ===== >> "logs\ejecutar_bat.log"

exit /b %CODIGO%

@echo off
REM Correr UNA SOLA VEZ (doble clic) para crear o actualizar la tarea programada.
REM Despues de eso, Windows ejecuta ejecutar.bat solo, TODOS los dias (incluidos
REM domingos y festivos) a la hora de abajo. Cada corrida reporta el dia anterior.
REM Requiere que la sesion de Windows este iniciada a esa hora.

REM ---- Ajustar aqui ----
REM Hora en formato 24h HH:MM
set "HORA=07:00"
set "NOMBRE=ReporteCargasMarcador"
REM ----------------------

schtasks /Create /SC DAILY /ST %HORA% /TN "%NOMBRE%" /TR "\"%~dp0ejecutar.bat\"" /F

echo.
echo Si no salio ningun error arriba, la tarea quedo creada: todos los dias a las %HORA%.
echo Puedes verla en el "Programador de tareas" de Windows, buscando "%NOMBRE%".
pause

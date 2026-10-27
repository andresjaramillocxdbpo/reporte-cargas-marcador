# reporte-cargas-marcador

Reporte diario de las bases (cargas) que el motor marcó en los marcadores CTI.

Lee los dos marcadores (PostgreSQL) **solo en modo lectura**, guarda los resultados en MySQL y genera un Excel.

```
Marcador 1 (PostgreSQL) ─┐   solo SELECT
                         ├──►  reporte_cargas ──► MySQL (rpt_*) + Excel
Marcador 2 (PostgreSQL) ─┘
```

## Qué reporta

Por cada día, marcador y carga marcada ese día:

1. Qué base se marcó: carga, tipo de base (`cti_campaign.descripcion`) y skill.
2. Cuándo se creó la carga (`cti_loads.created_at`) y cuántos registros tenía al iniciar y al terminar ese día (`skill_{skilldef}_data.dateinsert`). Si una carga de días anteriores recibe registros nuevos, se marca como **creció después de creada**.
3. Cuánto se marcó ese día: marcaciones y números distintos tocados.
4. Intentos por número: mínimo, promedio y máximo del día y históricos (desde que se creó la carga).
5. Porcentaje de cada `resultdesc` del día y histórico (desde que se creó la carga).

## Período

Corre todos los días, incluidos domingos y festivos, y siempre reporta **el día anterior**.

Se puede forzar un día o un rango con `--fecha` o `--desde/--hasta`. Con un rango, **cada día se procesa por separado**: tiene su propia ejecución en MySQL, su Excel y su correo. Nunca se suman marcaciones, intentos ni promedios de días distintos. Si un día no hubo marcación del motor, queda la ejecución en MySQL pero no se envía correo.

## Cómo se relacionan las tablas del marcador

```
cti_log_calls.idcampaign  = cti_skills.id          (¡es la skill, no la campaña!)
cti_skills.idcampaign     = cti_campaign.idcampaign (tipo de base: HOGAR OUTBOUND, …)
cti_log_calls.idload      = cti_loads.id
cti_loads.skill_id        = cti_skills.id
cti_log_calls.idreg       = skill_{skilldef}_data.id
skill_{skilldef}_data.number1 = teléfono
```

Solo se cuentan las marcaciones del motor: `typeskill = 'SKILL'` y `typecall = 'CallAuto'` (configurable con `TYPECALL`).

## Instalación

```bash
pip install -r requirements.txt
```

Copia `.env.example` como `.env` y llena las conexiones. El usuario de PostgreSQL basta con que tenga permiso de lectura; de todos modos el script abre la sesión en modo `read only`.

Crea la base `MYSQL_DB` con sus tablas y vistas (se puede repetir sin riesgo):

```bash
python -m reporte_cargas.instalar
```

## Histórico en MySQL

Nada se borra. Cada corrida por marcador queda en `rpt_ejecuciones` (rango, origen automático o manual, equipo, estado) y sus filas se guardan con ese `id_ejecucion`. Así queda qué se reportó cada vez y cuántos registros tenía la carga en ese momento.

| Objeto | Para qué |
|---|---|
| `rpt_ejecuciones` | Bitácora de corridas: `OK`, `ERROR` (con mensaje) o `EN_CURSO` |
| `rpt_cargas_marcacion_diaria` | Métricas por día, marcador y carga, de todas las ejecuciones |
| `rpt_cargas_resultados_diaria` | % por `resultdesc` del día, de todas las ejecuciones |
| `rpt_cargas_resultados_hist` | % por `resultdesc` desde que se creó la carga hasta el fin del día |
| `v_cargas_marcacion_vigente` | Solo la última ejecución OK de cada día. **Usar esta para consultar** |
| `v_cargas_resultados_vigente` | Igual, para los estados del día |
| `v_cargas_resultados_hist_vigente` | Igual, para los estados históricos |
| `v_cargas_crecimiento` | Cargas que crecieron en el día o contra el último día en que se reportaron |
| `v_cargas_dia_vs_historico` | Cada carga con su histórico (registros, con/sin marcación, % avance, intentos) al lado de lo del día |

Las columnas `*_hist` son desde que se creó la carga hasta el fin del día reportado; las `*_dia`, solo ese día. `python -m reporte_cargas.instalar` también aplica los cambios de estructura sobre una base ya instalada (por ejemplo, el cambio de nombres `*_acum` → `*_hist`).

## Uso

```bash
python -m reporte_cargas                                   # el día anterior
python -m reporte_cargas --fecha 2026-10-23                # un día
python -m reporte_cargas --desde 2026-10-20 --hasta 2026-10-23
python -m reporte_cargas --fecha 2026-10-23 --sin-mysql    # solo Excel, para probar
```

- El Excel queda en `salidas/` con las hojas **Resumen**, **Crecimiento**, **Estados día** y **Estados histórico** (una columna de % por resultado) y **Estados detalle**.
- Los logs quedan en `logs/`.
- Reprocesar un día agrega una ejecución nueva; las vistas `*_vigente` muestran la más reciente.
- Si un marcador falla, el otro se procesa igual y el script termina con código 1.

## Correo

El reporte se envía con Microsoft Graph desde la cuenta guardada en `msal_cache.bin` (mismo esquema que los otros proyectos). El archivo no se sube al repositorio.

Los destinatarios van en `config/correo.json` (copiar de `config/correo.example.json`, tampoco se sube):

```json
{
  "enviar": true,
  "asunto": "Reporte cargas marcador {periodo}",
  "para": ["..."],
  "cc": ["..."],
  "cco": ["..."],
  "adjuntar_excel": true,
  "alertas": {
    "prom_intentos_hist_alto": 4,
    "pct_avance_hist_bajo": 30,
    "dias_minimos_poco_tocada": 2,
    "registros_minimos": 100
  }
}
```

El correo es el reporte (los destinatarios no consultan MySQL), así que trae todo, ordenado de lo general a lo detallado:

1. **Indicadores:** cargas, marcaciones, números marcados y cargas que requieren atención, con el desglose por marcador.
2. **Puntos clave:** frases generadas a partir de los datos (alertas y resultados más frecuentes).
3. **Requiere atención:** una sola tabla con el motivo de cada carga:
   - **Muy trabajada:** promedio histórico de intentos ≥ `prom_intentos_hist_alto`.
   - **Poco tocada:** % de avance < `pct_avance_hist_bajo`, con al menos `dias_minimos_poco_tocada` días de creada.
   - **Creció después de creada.**
4. **Por marcador:**
   - Las cargas agrupadas por tipo de base, con el bloque **Histórico desde la creación** al lado del bloque **Día**. Las celdas fuera de umbral van resaltadas.
   - Los **resultados del día** y los **resultados históricos** en %, con las mismas columnas para comparar.
5. **Glosario** de los términos.

Las cargas con menos de `registros_minimos` registros (pruebas) no entran en las tablas ni generan alertas; se nombran en una nota. El Excel adjunto trae el detalle completo de cada resultado.

MySQL es opcional: si no conecta o falla al guardar, el Excel y el correo salen igual, y el error queda en el log (código de salida 1). Con `MYSQL_HABILITADO=0` en el `.env` no se intenta guardar.
- Si falló algún marcador, el asunto empieza con `[CON ERRORES]`.
- `"enviar": false` desactiva el envío sin tocar la tarea programada.

```bash
python -m reporte_cargas.correo --probar-token     # verifica el token sin enviar
python -m reporte_cargas.correo --login            # renueva el token si venció (pide código en el navegador)
python -m reporte_cargas --vista-previa-correo     # guarda el correo en salidas/ sin enviarlo
```

## Programación

- `ejecutar.bat`: corre el reporte completo y deja la salida en `logs/ejecutar_bat.log`. Acepta argumentos, por ejemplo `ejecutar.bat --fecha 2026-10-23`.
- `crear_tarea.bat`: se corre una vez y crea la tarea diaria en el Programador de tareas de Windows. La hora se ajusta en la variable `HORA` al inicio del archivo. La sesión de Windows debe estar iniciada a esa hora.

## Pruebas

```bash
python -m pytest
```

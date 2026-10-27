"""Columnas de las tablas de reporte, compartidas por MySQL y el Excel.

Cada entrada es (columna, título en el Excel).
"""

COLUMNAS_RESUMEN = [
    ("fecha_marcacion", "Fecha marcación"),
    ("marcador", "Marcador"),
    ("idload", "ID carga"),
    ("carga", "Carga"),
    ("tipo_base", "Tipo base"),
    ("skilldef", "Skill"),
    ("fecha_creacion_carga", "Creación carga"),
    ("registros_cti_loads", "Registros cti_loads"),
    ("registros_inicio_dia", "Registros inicio día"),
    ("registros_cargados", "Registros fin día"),
    ("registros_agregados_dia", "Registros agregados día"),
    ("crecio_despues_de_creada", "Creció después de creada"),
    ("numeros_unicos", "Números únicos"),
    ("marcaciones_dia", "Marcaciones día"),
    ("numeros_marcados_dia", "Números marcados día"),
    ("min_intentos_dia", "Mín. intentos día"),
    ("prom_intentos_dia", "Prom. intentos día"),
    ("max_intentos_dia", "Máx. intentos día"),
    ("registros_marcados_hist", "Registros con marcación (histórico)"),
    ("registros_sin_marcar_hist", "Registros sin marcación (histórico)"),
    ("numeros_marcados_hist", "Números marcados (histórico)"),
    ("pct_avance_hist", "% avance (histórico)"),
    ("min_intentos_hist", "Mín. intentos (histórico)"),
    ("prom_intentos_hist", "Prom. intentos (histórico)"),
    ("max_intentos_hist", "Máx. intentos (histórico)"),
]

# Para la hoja Glosario del Excel. "Histórico" = desde que se creó la carga
# hasta el fin del día reportado; "día" = solo el día reportado.
DESCRIPCIONES = {
    "fecha_marcacion": "Día reportado.",
    "marcador": "Marcador de donde salen los datos.",
    "idload": "ID de la carga (cti_loads.id).",
    "carga": "Nombre de la carga.",
    "tipo_base": "Campaña o tipo de base (cti_campaign).",
    "skilldef": "Skill que marca la carga.",
    "fecha_creacion_carga": "Fecha y hora en que se creó la carga.",
    "registros_cti_loads": "Registros procesados según cti_loads, al momento de generar el reporte.",
    "registros_inicio_dia": "Registros que tenía la carga al iniciar el día.",
    "registros_cargados": "Registros que tenía la carga al terminar el día.",
    "registros_agregados_dia": "Registros que entraron a la carga durante el día (fin - inicio).",
    "crecio_despues_de_creada": "1 si la carga recibió registros en un día posterior al de su creación.",
    "numeros_unicos": "Teléfonos (number1) distintos en la carga.",
    "marcaciones_dia": "Intentos de marcación del motor en el día.",
    "numeros_marcados_dia": "Teléfonos distintos marcados en el día.",
    "min_intentos_dia": "Mínimo de intentos por teléfono marcado, en el día.",
    "prom_intentos_dia": "Promedio de intentos por teléfono marcado, en el día.",
    "max_intentos_dia": "Máximo de intentos por teléfono marcado, en el día.",
    "registros_marcados_hist": "Registros con al menos un intento desde la creación de la carga.",
    "registros_sin_marcar_hist": "Registros sin ningún intento desde la creación de la carga.",
    "numeros_marcados_hist": "Teléfonos con al menos un intento desde la creación de la carga.",
    "pct_avance_hist": "% de teléfonos de la carga con al menos un intento (histórico).",
    "min_intentos_hist": "Mínimo de intentos por teléfono marcado (histórico).",
    "prom_intentos_hist": "Promedio de intentos por teléfono marcado (histórico).",
    "max_intentos_hist": "Máximo de intentos por teléfono marcado (histórico).",
    "resultdesc": "Resultado de la marcación (cti_log_calls.resultdesc); vacío = SIN RESULTADO.",
    "marcaciones": "Intentos con ese resultado.",
    "numeros": "Registros distintos con ese resultado.",
    "pct_marcaciones": "% de las marcaciones de la carga con ese resultado (del día o histórico, según la hoja).",
}

COLUMNAS_ESTADOS = [
    ("fecha_marcacion", "Fecha marcación"),
    ("marcador", "Marcador"),
    ("idload", "ID carga"),
    ("resultdesc", "Resultado"),
    ("marcaciones", "Marcaciones"),
    ("numeros", "Números"),
    ("pct_marcaciones", "% marcaciones"),
]

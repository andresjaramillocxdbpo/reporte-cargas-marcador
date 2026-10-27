"""Plantilla HTML del correo diario.

Pensado para gerencia: arriba lo que requiere atención y abajo el detalle
completo, porque el correo es el reporte (los destinatarios no consultan la
base). Solo tablas y estilos en línea: Outlook ignora <style>, flexbox y grid.
"""

import html
from datetime import date

# Umbrales para destacar cargas (se pueden cambiar en config/correo.json → alertas)
ALERTAS_POR_DEFECTO = {
    "prom_intentos_hist_alto": 4,       # muy trabajada: promedio histórico de intentos >= esto
    "pct_avance_hist_bajo": 30,         # poco tocada: % de avance histórico < esto ...
    "dias_minimos_poco_tocada": 2,      # ... y la carga ya tiene al menos estos días de creada
    "registros_minimos": 100,           # por debajo es carga de prueba: va aparte y sin alertas
}

TOP_RESULTADOS = 6

FUENTE = "font-family:Segoe UI,Calibri,Arial,sans-serif"
AZUL = "#1F3A5F"
VERDE = "#2F5D46"
OCRE = "#7A5418"
ROJO = "#A4262C"
GRIS = "#5B6573"
BORDE = "#DDE3EA"
FONDO_ALTERNO = "#F6F8FB"
FONDO_SECCION = "#EEF2F7"
RESALTE_ALTO = "#FBE9CF"    # intentos históricos altos
RESALTE_BAJO = "#E1EBF7"    # poco avance


# ── Utilidades ─────────────────────────────────────────────────────────────

def _n(valor, decimales: int = 0) -> str:
    if valor is None:
        return "-"
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _e(texto) -> str:
    return html.escape("" if texto is None else str(texto))


def _dias_desde_creacion(f: dict) -> int | None:
    creada = f["fecha_creacion_carga"]
    return (f["fecha_marcacion"] - creada.date()).days if creada else None


def es_prueba(f: dict, alertas: dict) -> bool:
    return f["registros_cargados"] is not None and f["registros_cargados"] < alertas["registros_minimos"]


def clasificar(resumen: list[dict], alertas: dict) -> tuple[list[dict], list[dict]]:
    """Devuelve (muy trabajadas, poco tocadas) según los umbrales."""
    reales = [f for f in resumen if (f["registros_cargados"] or 0) >= alertas["registros_minimos"]]
    trabajadas = sorted(
        (f for f in reales if (f["prom_intentos_hist"] or 0) >= alertas["prom_intentos_hist_alto"]),
        key=lambda f: -f["prom_intentos_hist"])
    poco_tocadas = sorted(
        (f for f in reales
         if f["pct_avance_hist"] is not None and f["pct_avance_hist"] < alertas["pct_avance_hist_bajo"]
         and (_dias_desde_creacion(f) or 0) >= alertas["dias_minimos_poco_tocada"]),
        key=lambda f: f["pct_avance_hist"])
    return trabajadas, poco_tocadas


# ── Bloques HTML ───────────────────────────────────────────────────────────

class _Seccion:
    """Fila de subtítulo dentro de una tabla (por ejemplo, el tipo de base)."""

    def __init__(self, texto: str):
        self.texto = texto


def _tabla(columnas: list[tuple[str, str]], filas: list, grupos: list[tuple[str, int, str]] | None = None) -> str:
    """columnas: (título, 'l'|'r'). Cada fila es una lista de celdas (texto o (texto, fondo)) o una _Seccion.

    grupos: (título, columnas que abarca, color) para un encabezado agrupado; cada
    grupo pinta sus encabezados y se separa del anterior con un borde.
    """
    color_col = [AZUL] * len(columnas)
    inicio_grupo: set[int] = set()
    fila_grupos = ""
    if grupos:
        col = 0
        for titulo, span, color in grupos:
            inicio_grupo.add(col)
            color_col[col:col + span] = [color] * span
            fila_grupos += (f'<th colspan="{span}" style="background:{color};color:#fff;padding:6px 8px;'
                            f'font-weight:600;text-align:center;border-left:2px solid #fff">{_e(titulo)}</th>')
            col += span
        fila_grupos = f"<tr>{fila_grupos}</tr>"

    def borde(i: int) -> str:
        return f"border-left:2px solid {BORDE};" if i in inicio_grupo and i > 0 else ""

    def alinear(i: int) -> str:
        return "right" if columnas[i][1] == "r" else "left"

    encabezado = "".join(
        f'<th style="background:{color_col[i]};color:#fff;padding:6px 8px;font-weight:600;white-space:nowrap;'
        f'{borde(i)}text-align:{alinear(i)}">{_e(t)}</th>' for i, (t, _) in enumerate(columnas))

    cuerpo, n = "", 0
    for fila in filas:
        if isinstance(fila, _Seccion):
            cuerpo += (f'<tr><td colspan="{len(columnas)}" style="background:{FONDO_SECCION};color:{AZUL};'
                       f'font-weight:600;padding:5px 8px;border-bottom:1px solid {BORDE}">{_e(fila.texto)}</td></tr>')
            n = 0
            continue
        fondo_fila = FONDO_ALTERNO if n % 2 else "#FFFFFF"
        celdas = ""
        for i, celda in enumerate(fila):
            texto, fondo = celda if isinstance(celda, tuple) else (celda, None)
            celdas += (f'<td style="padding:5px 8px;border-bottom:1px solid {BORDE};{borde(i)}'
                       f'{f"background:{fondo};" if fondo else ""}text-align:{alinear(i)}">{_e(texto)}</td>')
        cuerpo += f'<tr style="background:{fondo_fila}">{celdas}</tr>'
        n += 1

    return (f'<table cellspacing="0" cellpadding="0" style="border-collapse:collapse;{FUENTE};font-size:12px;'
            f'margin:4px 0 16px">{fila_grupos}<tr>{encabezado}</tr>{cuerpo}</table>')


def _titulo(texto: str, nivel: int = 2, color: str = AZUL) -> str:
    tam = "16px" if nivel == 2 else "13px"
    margen = "22px 0 6px" if nivel == 2 else "12px 0 4px"
    return f'<div style="{FUENTE};font-size:{tam};font-weight:600;color:{color};margin:{margen}">{_e(texto)}</div>'


def _nota(texto: str) -> str:
    return f'<div style="{FUENTE};font-size:11px;color:{GRIS};margin:-8px 0 14px">{texto}</div>'


def _indicadores(items: list[tuple[str, str, str]]) -> str:
    """Fila de indicadores: (valor, etiqueta, detalle)."""
    celdas = "".join(
        f'<td style="padding:12px 16px;border:1px solid {BORDE};background:#FFFFFF;vertical-align:top;width:25%">'
        f'<div style="{FUENTE};font-size:22px;font-weight:600;color:{AZUL}">{_e(valor)}</div>'
        f'<div style="{FUENTE};font-size:12px;color:#1b1b1b;margin-top:2px">{_e(etiqueta)}</div>'
        f'<div style="{FUENTE};font-size:11px;color:{GRIS};margin-top:4px">{_e(detalle)}</div></td>'
        for valor, etiqueta, detalle in items)
    return (f'<table cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin:14px 0 6px;'
            f'width:100%;max-width:900px"><tr>{celdas}</tr></table>')


# ── Secciones ──────────────────────────────────────────────────────────────

def _puntos_clave(resumen, estados, trabajadas, poco_tocadas, crecieron, fallidos) -> list[str]:
    puntos = []
    if fallidos:
        puntos.append(f'<b style="color:{ROJO}">No se pudo procesar {_e(", ".join(fallidos))}</b>; '
                      "las cifras de ese marcador no están incluidas.")

    marcaciones = sum(f["marcaciones_dia"] or 0 for f in resumen)
    puntos.append(f"Se marcaron <b>{_n(len(resumen))} cargas</b> con <b>{_n(marcaciones)} marcaciones</b> "
                  f"a {_n(sum(f['numeros_marcados_dia'] or 0 for f in resumen))} números.")

    for f in trabajadas[:3]:
        puntos.append(f"<b>{_e(f['idload'])} {_e(f['carga'])}</b> está muy trabajada: "
                      f"{_n(f['prom_intentos_hist'], 2)} intentos en promedio por número "
                      f"(máximo {_n(f['max_intentos_hist'])}) en {_n(_dias_desde_creacion(f))} días.")
    for f in poco_tocadas[:3]:
        puntos.append(f"<b>{_e(f['idload'])} {_e(f['carga'])}</b> casi no se ha tocado: "
                      f"{_n(f['pct_avance_hist'], 2)} % de avance en {_n(_dias_desde_creacion(f))} días, "
                      f"{_n(f['registros_sin_marcar_hist'])} registros sin marcar.")
    for f in crecieron:
        puntos.append(f"<b>{_e(f['idload'])} {_e(f['carga'])}</b> recibió "
                      f"{_n(f['registros_agregados_dia'])} registros nuevos, "
                      f"{_n(_dias_desde_creacion(f))} días después de creada.")
    if not (trabajadas or poco_tocadas or crecieron):
        puntos.append("Sin alertas: ninguna carga sobre-trabajada, sin tocar o con registros nuevos.")

    total = sum(e["marcaciones"] for e in estados)
    if total:
        por_resultado: dict[str, int] = {}
        for e in estados:
            por_resultado[e["resultdesc"]] = por_resultado.get(e["resultdesc"], 0) + e["marcaciones"]
        top = sorted(por_resultado.items(), key=lambda x: -x[1])[:3]
        puntos.append("Resultados más frecuentes del día: " + ", ".join(
            f"{_e(r)} ({_n(100 * m / total, 1)} %)" for r, m in top) + ".")
    return puntos


def _requiere_atencion(trabajadas, poco_tocadas, crecieron) -> str:
    filas = []
    for f in trabajadas:
        filas.append([("Muy trabajada", RESALTE_ALTO), f["marcador"], f["idload"], f["carga"],
                      _n(_dias_desde_creacion(f)),
                      f"Prom. {_n(f['prom_intentos_hist'], 2)} intentos · máx. {_n(f['max_intentos_hist'])} · "
                      f"{_n(f['pct_avance_hist'], 2)} % de avance"])
    for f in poco_tocadas:
        filas.append([("Poco tocada", RESALTE_BAJO), f["marcador"], f["idload"], f["carga"],
                      _n(_dias_desde_creacion(f)),
                      f"{_n(f['pct_avance_hist'], 2)} % de avance · {_n(f['registros_sin_marcar_hist'])} "
                      f"de {_n(f['registros_cargados'])} registros sin marcar"])
    for f in crecieron:
        filas.append([("Creció después de creada", "#F6D7D9"), f["marcador"], f["idload"], f["carga"],
                      _n(_dias_desde_creacion(f)),
                      f"+{_n(f['registros_agregados_dia'])} registros "
                      f"({_n(f['registros_inicio_dia'])} → {_n(f['registros_cargados'])})"])
    if not filas:
        return ""
    return _titulo("Requiere atención") + _tabla(
        [("Motivo", "l"), ("Marcador", "l"), ("ID", "r"), ("Carga", "l"), ("Días creada", "r"), ("Detalle", "l")],
        filas)


def _detalle_marcador(propias: list[dict], alertas: dict) -> str:
    filas: list = []
    tipo_actual = object()
    for f in propias:
        if f["tipo_base"] != tipo_actual:
            tipo_actual = f["tipo_base"]
            filas.append(_Seccion(tipo_actual or "Sin tipo de base"))
        prom_hist = _n(f["prom_intentos_hist"], 2)
        avance = _n(f["pct_avance_hist"], 2)
        alto = (f["prom_intentos_hist"] or 0) >= alertas["prom_intentos_hist_alto"]
        bajo = (f["pct_avance_hist"] is not None and f["pct_avance_hist"] < alertas["pct_avance_hist_bajo"]
                and (_dias_desde_creacion(f) or 0) >= alertas["dias_minimos_poco_tocada"])
        filas.append([
            f["idload"], f["carga"],
            f["fecha_creacion_carga"].strftime("%Y-%m-%d") if f["fecha_creacion_carga"] else "-",
            _n(f["registros_cargados"]), _n(f["registros_marcados_hist"]), _n(f["registros_sin_marcar_hist"]),
            (avance, RESALTE_BAJO) if bajo else avance,
            _n(f["min_intentos_hist"]),
            (prom_hist, RESALTE_ALTO) if alto else prom_hist,
            _n(f["max_intentos_hist"]),
            _n(f["marcaciones_dia"]), _n(f["numeros_marcados_dia"]),
            _n(f["min_intentos_dia"]), _n(f["prom_intentos_dia"], 2), _n(f["max_intentos_dia"]),
        ])
    return _tabla(
        [("ID", "r"), ("Carga", "l"), ("Creada", "l"),
         ("Registros", "r"), ("Con marcación", "r"), ("Sin marcación", "r"), ("% avance", "r"),
         ("Mín.", "r"), ("Prom.", "r"), ("Máx.", "r"),
         ("Marcaciones", "r"), ("Números", "r"), ("Mín.", "r"), ("Prom.", "r"), ("Máx.", "r")],
        filas,
        grupos=[("Carga", 3, AZUL), ("Histórico desde la creación", 7, VERDE), ("Día", 5, OCRE)])


def _resultados(propias: list[dict], estados: list[dict], columnas_resultado: list[str]) -> str:
    """Pivot de % por resultado, una fila por carga, mismas columnas para día e histórico."""
    por_carga: dict[int, dict[str, int]] = {}
    for e in estados:
        por_carga.setdefault(e["idload"], {})[e["resultdesc"]] = e["marcaciones"]
    filas = []
    for f in propias:
        datos = por_carga.get(f["idload"], {})
        total = sum(datos.values())
        if not total:
            continue
        mostrados = [datos.get(r, 0) for r in columnas_resultado]
        otros = total - sum(mostrados)
        filas.append([f["idload"], f["carga"], _n(total)]
                     + [_n(100 * m / total, 1) if m else "-" for m in mostrados]
                     + [_n(100 * otros / total, 1) if otros else "-"])
    return _tabla(
        [("ID", "r"), ("Carga", "l"), ("Marcaciones", "r")]
        + [(f"% {r}", "r") for r in columnas_resultado] + [("% Otros", "r")],
        filas)


def _seccion_marcador(marcador, resumen, estados, estados_hist, alertas, dia, fallidos) -> str:
    if marcador in fallidos:
        return (_titulo(marcador)
                + f'<div style="{FUENTE};font-size:13px;color:{ROJO}">No se pudo procesar este marcador. '
                  "Se reintentará en la próxima ejecución o puede reprocesarse a mano.</div>")
    propias = [f for f in resumen if f["marcador"] == marcador]
    if not propias:
        return _titulo(marcador) + f'<div style="{FUENTE};font-size:13px;color:{GRIS}">Sin marcación del motor este día.</div>'

    reales = sorted((f for f in propias if not es_prueba(f, alertas)),
                    key=lambda f: (f["tipo_base"] or "", -(f["marcaciones_dia"] or 0)))
    pruebas = [f for f in propias if es_prueba(f, alertas)]
    ids_reales = {f["idload"] for f in reales}
    est_dia = [e for e in estados if e["marcador"] == marcador and e["idload"] in ids_reales]
    est_hist = [e for e in estados_hist if e["marcador"] == marcador and e["idload"] in ids_reales]

    marcaciones = sum(f["marcaciones_dia"] or 0 for f in propias)
    partes = [_titulo(f"{marcador} · {_n(len(propias))} cargas · {_n(marcaciones)} marcaciones")]

    if reales:
        partes.append(_titulo("Cargas: histórico contra el día", nivel=3))
        partes.append(_detalle_marcador(reales, alertas))

        # Los resultados con más volumen del día en este marcador; el resto va en "Otros"
        volumen: dict[str, int] = {}
        for e in est_dia:
            volumen[e["resultdesc"]] = volumen.get(e["resultdesc"], 0) + e["marcaciones"]
        top = [r for r, _ in sorted(volumen.items(), key=lambda x: -x[1])[:TOP_RESULTADOS]]
        if top:
            partes.append(_titulo(f"Resultados del día {dia.isoformat()} (% de las marcaciones)", nivel=3))
            partes.append(_resultados(reales, est_dia, top))
            partes.append(_titulo("Resultados históricos desde la creación (% de las marcaciones)", nivel=3))
            partes.append(_resultados(reales, est_hist, top))

    if pruebas:
        detalle = ", ".join(f"{_e(f['idload'])} {_e(f['carga'])} ({_n(f['marcaciones_dia'])} marc.)"
                            for f in pruebas)
        partes.append(_nota(f"Cargas de prueba (menos de {_n(alertas['registros_minimos'])} registros), "
                            f"fuera de las tablas: {detalle}."))
    return "".join(partes)


GLOSARIO = (
    "<b>Histórico</b>: desde que se creó la carga hasta el fin del día reportado. "
    "<b>Día</b>: solo el día reportado. "
    "<b>Registros</b>: filas de la carga; <b>con / sin marcación</b>: registros con al menos un intento o ninguno. "
    "<b>% avance</b>: números con al menos un intento sobre los números de la carga. "
    "<b>Mín. / Prom. / Máx.</b>: intentos por número marcado. "
    "Solo se cuenta la marcación automática del motor (CallAuto). "
    "Celdas resaltadas: promedio histórico alto o avance bajo según los umbrales del reporte."
)


def armar_html(resumen: list[dict], estados: list[dict], estados_hist: list[dict], dia: date,
               fallidos: list[str], marcadores: list[str], alertas: dict | None = None) -> str:
    """Correo de un solo día: los totales nunca suman días distintos."""
    alertas = {**ALERTAS_POR_DEFECTO, **(alertas or {})}
    trabajadas, poco_tocadas = clasificar(resumen, alertas)
    crecieron = [f for f in resumen if f["crecio_despues_de_creada"]]

    # Indicadores
    def por_marcador(campo: str) -> str:
        return " · ".join(f"{m}: {_n(sum(f[campo] or 0 for f in resumen if f['marcador'] == m))}"
                          for m in marcadores if m not in fallidos)

    cargas_por_marcador = " · ".join(
        f"{m}: {_n(sum(1 for f in resumen if f['marcador'] == m))}" for m in marcadores if m not in fallidos)
    alertas_total = len(trabajadas) + len(poco_tocadas) + len(crecieron)
    indicadores = _indicadores([
        (_n(len(resumen)), "Cargas marcadas", cargas_por_marcador),
        (_n(sum(f["marcaciones_dia"] or 0 for f in resumen)), "Marcaciones", por_marcador("marcaciones_dia")),
        (_n(sum(f["numeros_marcados_dia"] or 0 for f in resumen)), "Números marcados", por_marcador("numeros_marcados_dia")),
        (_n(alertas_total), "Cargas que requieren atención",
         f"{len(trabajadas)} muy trabajadas · {len(poco_tocadas)} poco tocadas · {len(crecieron)} crecieron"),
    ])

    puntos = "".join(f'<li style="margin:3px 0">{p}</li>'
                     for p in _puntos_clave(resumen, estados, trabajadas, poco_tocadas, crecieron, fallidos))

    partes = [
        f'<div style="{FUENTE};color:#1b1b1b;font-size:13px;max-width:1400px">',
        f'<table cellspacing="0" cellpadding="0" style="border-collapse:collapse;width:100%"><tr>'
        f'<td style="background:{AZUL};color:#fff;padding:16px 20px">'
        f'<div style="{FUENTE};font-size:19px;font-weight:600">Reporte de cargas marcadas · {dia.isoformat()}</div>'
        f'<div style="{FUENTE};font-size:12px;color:#D6DEE8;margin-top:4px">Marcación automática del motor '
        f'(CallAuto) · {_e(", ".join(marcadores))}</div></td></tr></table>',
        indicadores,
        _titulo("Puntos clave"),
        f'<ul style="{FUENTE};font-size:13px;margin:0 0 6px 18px;padding:0">{puntos}</ul>',
        _requiere_atencion(trabajadas, poco_tocadas, crecieron),
    ]
    for m in marcadores:
        partes.append(_seccion_marcador(m, resumen, estados, estados_hist, alertas, dia, fallidos))
    partes.append(f'<div style="{FUENTE};font-size:11px;color:{GRIS};border-top:1px solid {BORDE};'
                  f'margin-top:18px;padding-top:8px">{GLOSARIO}<br><br>'
                  "El Excel adjunto trae el detalle completo, incluido cada resultado por carga.</div></div>")
    return "".join(partes)

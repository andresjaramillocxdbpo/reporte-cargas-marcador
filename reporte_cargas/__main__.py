"""Uso:
    python -m reporte_cargas                          # el día anterior
    python -m reporte_cargas --fecha 2026-10-23       # un día puntual
    python -m reporte_cargas --desde 2026-10-20 --hasta 2026-10-23
    python -m reporte_cargas --sin-mysql              # no escribe en MySQL
    python -m reporte_cargas --sin-correo             # no envía el correo
    python -m reporte_cargas --vista-previa-correo    # guarda el correo en salidas/ sin enviarlo
    python -m reporte_cargas --para a@x.com,b@x.com   # reemplaza los 'para' de config/correo.json

Cada día se procesa por separado: su propia ejecución en MySQL, su Excel y su
correo. Nunca se suman marcaciones ni intentos de días distintos.
"""

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from . import destino_mysql, excel
from .config import Config, cargar_config
from .extraccion import conectar, extraer_dia
from .periodo import dia_a_reportar, rango

log = logging.getLogger("reporte_cargas")


def _configurar_logs() -> None:
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(Path("logs") / f"{date.today().isoformat()}.log", encoding="utf-8"),
        ],
    )


def _argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="reporte_cargas", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fecha", type=date.fromisoformat, help="Día a reportar (YYYY-MM-DD)")
    p.add_argument("--desde", type=date.fromisoformat, help="Inicio del rango (YYYY-MM-DD)")
    p.add_argument("--hasta", type=date.fromisoformat, help="Fin del rango, inclusive (YYYY-MM-DD)")
    p.add_argument("--sin-mysql", action="store_true", help="No escribe en MySQL")
    p.add_argument("--sin-excel", action="store_true", help="No genera el Excel")
    p.add_argument("--sin-correo", action="store_true", help="No envía el correo")
    p.add_argument("--vista-previa-correo", action="store_true",
                   help="Guarda el HTML del correo en la carpeta de salida y no lo envía")
    p.add_argument("--para", help="Destinatarios separados por coma; reemplazan 'para' del config")
    args = p.parse_args()
    if args.fecha and (args.desde or args.hasta):
        p.error("Use --fecha o --desde/--hasta, no ambos")
    if bool(args.desde) != bool(args.hasta):
        p.error("--desde y --hasta van juntos")
    return args


def _correo(args, resumen: list[dict], estados: list[dict], estados_hist: list[dict], dia: date,
            fallidos: list[str], marcadores: list[str], ruta_excel: Path | None, carpeta_salida: str) -> None:
    from . import correo

    cfg_correo = correo.cargar_config_correo()
    if args.para:
        cfg_correo["para"] = [c.strip() for c in args.para.split(",") if c.strip()]
    asunto = cfg_correo["asunto"].format(periodo=dia.isoformat())
    if fallidos:
        asunto = f"[CON ERRORES] {asunto}"
    cuerpo = correo.armar_html(resumen, estados, estados_hist, dia, fallidos, marcadores, cfg_correo["alertas"])

    if args.vista_previa_correo:
        ruta = Path(carpeta_salida) / f"correo_{dia.isoformat()}.html"
        ruta.write_text(f"<!doctype html><meta charset='utf-8'><title>{asunto}</title>{cuerpo}", encoding="utf-8")
        log.info("Vista previa del correo (no enviado): %s | Para: %s | CC: %s | CCO: %s", ruta.resolve(),
                 cfg_correo["para"], cfg_correo["cc"], cfg_correo["cco"])
        return
    if not cfg_correo.get("enviar", True):
        log.info("Envío de correo desactivado en config/correo.json")
        return
    adjunto = ruta_excel if cfg_correo["adjuntar_excel"] else None
    correo.enviar(cfg_correo, asunto, cuerpo, adjunto)


def procesar_dia(args, cfg: Config, mysql, dia: date, origen: str) -> list[str]:
    """Extrae, guarda, arma el Excel y envía el correo de un solo día. Devuelve lo que falló."""
    log.info("===== Día %s =====", dia)
    resumen: list[dict] = []
    estados: list[dict] = []
    estados_hist: list[dict] = []
    fallidos: list[str] = []
    avisos_mysql: list[str] = []

    # Un marcador caído no detiene al otro. MySQL es un extra: si falla, se
    # registra en el log y el reporte sigue (el correo es lo que reciben).
    for m in cfg.marcadores:
        id_ejecucion = _mysql_seguro(lambda: destino_mysql.iniciar_ejecucion(mysql, m.nombre, dia, dia, origen),
                                     mysql, avisos_mysql, f"abrir ejecución {m.nombre}")
        try:
            conn = conectar(m, cfg.pg_statement_timeout_ms)
            try:
                r, e, a = extraer_dia(conn, m.nombre, dia, cfg.typecall)
            finally:
                conn.close()
        except Exception as exc:
            log.exception("Falló el marcador %s el %s", m.nombre, dia)
            fallidos.append(m.nombre)
            if id_ejecucion:
                _mysql_seguro(lambda: destino_mysql.marcar_error(mysql, id_ejecucion, f"{type(exc).__name__}: {exc}"),
                              mysql, avisos_mysql, f"marcar error {m.nombre}")
            continue

        if id_ejecucion:
            _mysql_seguro(lambda: destino_mysql.guardar(mysql, id_ejecucion, r, e, a),
                          mysql, avisos_mysql, f"guardar {m.nombre}")
        resumen += r
        estados += e
        estados_hist += a

    if not resumen and not fallidos:
        # Queda la ejecución OK con 0 cargas en MySQL, pero no se manda un reporte vacío
        log.info("%s: no hubo marcación del motor; no se genera Excel ni correo", dia)
        return fallidos

    ruta_excel = None
    if not args.sin_excel:
        ruta_excel = excel.generar(resumen, estados, estados_hist, dia, dia, cfg.carpeta_salida)
        log.info("Excel generado: %s", ruta_excel.resolve())

    if not args.sin_correo:
        try:
            _correo(args, resumen, estados, estados_hist, dia, fallidos,
                    [m.nombre for m in cfg.marcadores], ruta_excel, cfg.carpeta_salida)
        except Exception:
            log.exception("Falló el envío del correo del %s", dia)
            fallidos.append("CORREO")
    # MySQL no marca el correo como "con errores", pero sí el código de salida
    return fallidos + (["MYSQL"] if avisos_mysql else [])


def _mysql_seguro(accion, mysql, avisos: list[str], que: str):
    if not mysql:
        return None
    try:
        # La conexión queda quieta mientras se leen los marcadores y la red la
        # puede cortar por inactividad: se verifica y reconecta antes de usarla.
        mysql.ping(reconnect=True)
        return accion()
    except Exception:
        log.exception("MySQL falló al %s; el reporte continúa", que)
        avisos.append(que)
        return None


def main() -> int:
    args = _argumentos()
    _configurar_logs()
    cfg = cargar_config(requiere_mysql=not args.sin_mysql)

    if args.fecha:
        dias = [args.fecha]
    elif args.desde:
        dias = rango(args.desde, args.hasta)
    else:
        dias = [dia_a_reportar(date.today())]
    origen = "manual" if (args.fecha or args.desde) else "automatico"
    log.info("Días a reportar: %s", ", ".join(d.isoformat() for d in dias))

    mysql = None
    if cfg.mysql:
        try:
            mysql = destino_mysql.conectar(cfg.mysql)
        except Exception:
            log.exception("No se pudo conectar a MySQL; el reporte sigue sin guardar histórico")
    errores: list[str] = ["MYSQL sin conexión"] if cfg.mysql and not mysql else []
    try:
        for dia in dias:
            errores += [f"{dia} {f}" for f in procesar_dia(args, cfg, mysql, dia, origen)]
    finally:
        if mysql:
            mysql.close()

    if errores:
        log.error("Con error: %s", ", ".join(errores))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

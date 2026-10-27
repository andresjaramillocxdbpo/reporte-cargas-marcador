"""Escritura histórica en MySQL.

Cada corrida por marcador abre una fila en rpt_ejecuciones y agrega sus filas
con ese id_ejecucion. Nunca se borra nada: las vistas v_*_vigente eligen la
última ejecución exitosa de cada día.
"""

import logging
import socket
from datetime import date, datetime

import pymysql

from .config import ConexionMysql
from .modelo import COLUMNAS_ESTADOS, COLUMNAS_RESUMEN

log = logging.getLogger(__name__)

TABLA_RESUMEN = "rpt_cargas_marcacion_diaria"
TABLA_ESTADOS = "rpt_cargas_resultados_diaria"
TABLA_ESTADOS_HIST = "rpt_cargas_resultados_hist"


def conectar(c: ConexionMysql):
    return pymysql.connect(host=c.host, port=c.port, database=c.db, user=c.user,
                           password=c.password, charset="utf8mb4", autocommit=False)


def iniciar_ejecucion(conn, marcador: str, desde: date, hasta: date, origen: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "insert into rpt_ejecuciones (marcador, fecha_desde, fecha_hasta, origen, equipo, inicio, estado)"
            " values (%s, %s, %s, %s, %s, %s, 'EN_CURSO')",
            (marcador, desde, hasta, origen, socket.gethostname(), datetime.now()),
        )
        id_ejecucion = cur.lastrowid
    conn.commit()
    return id_ejecucion


def _insert(tabla: str, columnas: list[str]) -> str:
    lista = ", ".join(columnas)
    marcas = ", ".join(["%s"] * len(columnas))
    return f"insert into {tabla} ({lista}) values ({marcas})"


def guardar(conn, id_ejecucion: int, resumen: list[dict], estados: list[dict],
            estados_hist: list[dict]) -> None:
    """Inserta las filas y cierra la ejecución como OK, todo en una transacción."""
    cols_resumen = ["id_ejecucion"] + [col for col, _ in COLUMNAS_RESUMEN]
    cols_estados = ["id_ejecucion"] + [col for col, _ in COLUMNAS_ESTADOS]
    try:
        with conn.cursor() as cur:
            for tabla, columnas, filas in ((TABLA_RESUMEN, cols_resumen, resumen),
                                           (TABLA_ESTADOS, cols_estados, estados),
                                           (TABLA_ESTADOS_HIST, cols_estados, estados_hist)):
                if filas:
                    cur.executemany(_insert(tabla, columnas),
                                    [[id_ejecucion] + [f[col] for col in columnas[1:]] for f in filas])
            cur.execute(
                "update rpt_ejecuciones set estado = 'OK', fin = %s, cargas = %s where id_ejecucion = %s",
                (datetime.now(), len(resumen), id_ejecucion),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    log.info("Ejecución %s guardada (%d filas resumen, %d estados día, %d estados históricos)",
             id_ejecucion, len(resumen), len(estados), len(estados_hist))


def marcar_error(conn, id_ejecucion: int, mensaje: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "update rpt_ejecuciones set estado = 'ERROR', fin = %s, mensaje = %s where id_ejecucion = %s",
            (datetime.now(), mensaje[:5000], id_ejecucion),
        )
    conn.commit()

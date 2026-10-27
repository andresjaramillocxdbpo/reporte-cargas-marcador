"""Crea la base de datos MySQL (si no existe) y sus tablas y vistas.

Uso:
    python -m reporte_cargas.instalar

Es seguro correrlo varias veces: las tablas usan "if not exists" y las vistas
"create or replace".
"""

import re
import sys
from pathlib import Path

import pymysql

from .config import cargar_config

ARCHIVO_SQL = Path(__file__).resolve().parent.parent / "sql" / "mysql_tablas.sql"


def sentencias(texto: str) -> list[str]:
    sin_comentarios = "\n".join(
        linea for linea in texto.splitlines() if not linea.lstrip().startswith("--")
    )
    return [s.strip() for s in sin_comentarios.split(";") if s.strip()]


# Cambios sobre bases ya instaladas. Cada uno revisa antes de aplicar, así
# correr el instalador varias veces no hace nada de más.
RENOMBRES_TABLAS = [("rpt_cargas_resultados_acum", "rpt_cargas_resultados_hist")]
VISTAS_ELIMINADAS = ["v_cargas_resultados_acum_vigente"]
RENOMBRES_COLUMNAS = {
    "rpt_cargas_marcacion_diaria": [
        ("registros_marcados_acum", "registros_marcados_hist"),
        ("registros_sin_marcar_acum", "registros_sin_marcar_hist"),
        ("numeros_marcados_acum", "numeros_marcados_hist"),
        ("pct_avance_acum", "pct_avance_hist"),
        ("min_intentos_acum", "min_intentos_hist"),
        ("prom_intentos_acum", "prom_intentos_hist"),
        ("max_intentos_acum", "max_intentos_hist"),
    ],
}
COLUMNAS_NUEVAS = {
    "rpt_cargas_marcacion_diaria": [
        ("registros_marcados_hist", "int after max_intentos_dia"),
        ("registros_sin_marcar_hist", "int after registros_marcados_hist"),
    ],
}


def _existe_tabla(cur, tabla: str) -> bool:
    cur.execute("select count(*) from information_schema.tables "
                "where table_schema = database() and table_name = %s", (tabla,))
    return cur.fetchone()[0] > 0


def _existe_columna(cur, tabla: str, columna: str) -> bool:
    cur.execute("select count(*) from information_schema.columns "
                "where table_schema = database() and table_name = %s and column_name = %s", (tabla, columna))
    return cur.fetchone()[0] > 0


def migrar(cur) -> None:
    for vista in VISTAS_ELIMINADAS:
        cur.execute(f"drop view if exists {vista}")
    for viejo, nuevo in RENOMBRES_TABLAS:
        if _existe_tabla(cur, viejo) and not _existe_tabla(cur, nuevo):
            cur.execute(f"rename table {viejo} to {nuevo}")
            print(f"  migrado: tabla {viejo} -> {nuevo}")
    for tabla, columnas in RENOMBRES_COLUMNAS.items():
        if not _existe_tabla(cur, tabla):
            continue
        for viejo, nuevo in columnas:
            if _existe_columna(cur, tabla, viejo) and not _existe_columna(cur, tabla, nuevo):
                cur.execute(f"alter table {tabla} rename column {viejo} to {nuevo}")
                print(f"  migrado: {tabla}.{viejo} -> {nuevo}")
    for tabla, columnas in COLUMNAS_NUEVAS.items():
        if not _existe_tabla(cur, tabla):
            continue
        for columna, definicion in columnas:
            if not _existe_columna(cur, tabla, columna):
                cur.execute(f"alter table {tabla} add column {columna} {definicion}")
                print(f"  migrado: {tabla}.{columna} agregada")


def main() -> int:
    cfg = cargar_config()
    c = cfg.mysql
    if not re.fullmatch(r"[A-Za-z0-9_]+", c.db):
        print(f"Nombre de base inválido: {c.db!r}")
        return 1

    conn = pymysql.connect(host=c.host, port=c.port, user=c.user, password=c.password,
                           charset="utf8mb4", autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(f"create database if not exists `{c.db}` "
                        "default character set utf8mb4 collate utf8mb4_unicode_ci")
            cur.execute(f"use `{c.db}`")
            migrar(cur)
            for s in sentencias(ARCHIVO_SQL.read_text(encoding="utf-8")):
                cur.execute(s)
            cur.execute("show full tables")
            for nombre, tipo in cur.fetchall():
                print(f"  {tipo:<10} {nombre}")
    finally:
        conn.close()
    print(f"Base {c.db} lista en {c.host}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Lectura de un marcador (PostgreSQL). Solo SELECT, en sesión de solo lectura."""

import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import psycopg2
import psycopg2.extras
from psycopg2 import sql

from .config import ConexionPg

log = logging.getLogger(__name__)

# Cargas que el motor marcó en el día. Parte del log y no de cti_loads,
# así una carga sin registro en cti_loads también aparece.
SQL_CARGAS = """
select  x.idload,
        l.name               as carga,
        l.created_at         as fecha_creacion_carga,
        l.processed_records  as registros_cti_loads,
        s.skilldef,
        cc.descripcion       as tipo_base
from (select distinct idload
      from cti_log_calls
      where fecha >= %(desde)s and fecha < %(hasta)s
        and typeskill = 'SKILL'
        and typecall  = %(typecall)s) x
left join cti_loads    l  on l.id = x.idload
left join cti_skills   s  on s.id = l.skill_id
left join cti_campaign cc on cc.idcampaign = s.idcampaign
order by x.idload
"""

# Métricas de una carga. Todo se calcula "como estaba al terminar el día"
# (dateinsert y fecha < hasta), así reprocesar un día pasado da el mismo
# resultado aunque la carga haya crecido después.
# cti_log_calls no tiene índice por idload pero está particionada por fecha:
# el límite inferior en la creación de la carga evita leer meses que no aplican.
SQL_METRICAS = """
with base as (
    select id, number1, dateinsert
    from {tabla}
    where idload = %(idload)s
      and (dateinsert is null or dateinsert < %(hasta)s)
),
lg as (
    select idreg, fecha
    from cti_log_calls
    where idload = %(idload)s
      and typeskill = 'SKILL'
      and typecall  = %(typecall)s
      and fecha >= %(desde_carga)s
      and fecha <  %(hasta)s
),
acum as (
    select b.number1, count(lg.idreg) as veces
    from base b left join lg on lg.idreg = b.id
    group by b.number1
),
dia as (
    select b.number1, count(*) as veces
    from base b join lg on lg.idreg = b.id
    where lg.fecha >= %(desde)s
    group by b.number1
)
select (select count(*) filter (where dateinsert is null or dateinsert < %(desde)s) from base)
                                                                       as registros_inicio_dia,
       (select count(*) from base)                                     as registros_cargados,
       (select count(*) from base b
         where exists (select 1 from lg where lg.idreg = b.id))        as registros_marcados_hist,
       (select count(*) from acum)                                     as numeros_unicos,
       (select coalesce(sum(veces), 0) from dia)                       as marcaciones_dia,
       (select count(*) from dia)                                      as numeros_marcados_dia,
       (select min(veces) from dia)                                    as min_intentos_dia,
       (select round(avg(veces), 2) from dia)                          as prom_intentos_dia,
       (select max(veces) from dia)                                    as max_intentos_dia,
       (select count(*) filter (where veces > 0) from acum)            as numeros_marcados_hist,
       (select round(100.0 * count(*) filter (where veces > 0)
                     / nullif(count(*), 0), 2) from acum)              as pct_avance_hist,
       (select min(veces) filter (where veces > 0) from acum)          as min_intentos_hist,
       (select round(avg(veces) filter (where veces > 0), 2) from acum) as prom_intentos_hist,
       (select max(veces) from acum)                                   as max_intentos_hist
"""

SQL_ESTADOS = """
select  idload,
        coalesce(nullif(trim(resultdesc), ''), 'SIN RESULTADO') as resultdesc,
        count(*)               as marcaciones,
        count(distinct idreg)  as numeros
from cti_log_calls
where fecha >= %(desde)s and fecha < %(hasta)s
  and typeskill = 'SKILL'
  and typecall  = %(typecall)s
group by 1, 2
"""

# Igual que SQL_ESTADOS pero de una carga, desde que se creó hasta el fin del día.
SQL_ESTADOS_HIST = """
select  coalesce(nullif(trim(resultdesc), ''), 'SIN RESULTADO') as resultdesc,
        count(*)               as marcaciones,
        count(distinct idreg)  as numeros
from cti_log_calls
where idload = %(idload)s
  and typeskill = 'SKILL'
  and typecall  = %(typecall)s
  and fecha >= %(desde_carga)s
  and fecha <  %(hasta)s
group by 1
"""

METRICAS_VACIAS = {
    "registros_inicio_dia": None, "registros_cargados": None,
    "registros_agregados_dia": None, "crecio_despues_de_creada": None,
    "registros_marcados_hist": None, "registros_sin_marcar_hist": None,
    "numeros_unicos": None,
    "marcaciones_dia": None, "numeros_marcados_dia": None,
    "min_intentos_dia": None, "prom_intentos_dia": None, "max_intentos_dia": None,
    "numeros_marcados_hist": None, "pct_avance_hist": None,
    "min_intentos_hist": None, "prom_intentos_hist": None, "max_intentos_hist": None,
}

# Para cargas sin fecha de creación: no limita el acumulado.
SIN_LIMITE = datetime(2000, 1, 1)


def conectar(c: ConexionPg, statement_timeout_ms: int):
    conn = psycopg2.connect(
        host=c.host, port=c.port, dbname=c.db, user=c.user, password=c.password,
        connect_timeout=15,
        options=f"-c default_transaction_read_only=on -c statement_timeout={statement_timeout_ms}",
        application_name="reporte-cargas-marcador",
    )
    conn.set_session(readonly=True, autocommit=True)
    return conn


def _tabla_existe(cur, tabla: str) -> bool:
    cur.execute("select to_regclass(%s) is not null as existe", (tabla,))
    return cur.fetchone()["existe"]


def extraer_dia(conn, marcador: str, dia: date, typecall: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Devuelve (resumen, estados del día, estados históricos) de un marcador para un día."""
    params = {
        "desde": datetime.combine(dia, time.min),
        "hasta": datetime.combine(dia + timedelta(days=1), time.min),
        "typecall": typecall,
    }

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(SQL_CARGAS, params)
        cargas = cur.fetchall()
        log.info("%s %s: %d cargas marcadas", marcador, dia, len(cargas))

        resumen = []
        estados_hist = []
        for c in cargas:
            creada = _sin_tz(c["fecha_creacion_carga"])
            params_carga = {**params, "idload": c["idload"], "desde_carga": _inicio_carga(creada)}

            cur.execute(SQL_ESTADOS_HIST, params_carga)
            estados_hist += [
                {"fecha_marcacion": dia, "marcador": marcador, "idload": c["idload"], **e}
                for e in cur.fetchall()
            ]

            fila = {
                "fecha_marcacion": dia,
                "marcador": marcador,
                "idload": c["idload"],
                "carga": c["carga"],
                "tipo_base": c["tipo_base"],
                "skilldef": c["skilldef"],
                "fecha_creacion_carga": creada,
                "registros_cti_loads": c["registros_cti_loads"],
                **METRICAS_VACIAS,
            }
            tabla = f"skill_{c['skilldef']}_data" if c["skilldef"] else None
            if tabla is None:
                log.warning("%s carga %s: no está en cti_loads/cti_skills, sin métricas", marcador, c["idload"])
            elif not _tabla_existe(cur, tabla):
                log.warning("%s carga %s: no existe la tabla %s, sin métricas", marcador, c["idload"], tabla)
            else:
                consulta = sql.SQL(SQL_METRICAS).format(tabla=sql.Identifier(tabla))
                cur.execute(consulta, params_carga)
                fila.update(cur.fetchone())
                _marcar_crecimiento(fila, params["desde"])
                if fila["crecio_despues_de_creada"]:
                    log.warning("%s carga %s creció %s registros el %s (creada %s)", marcador,
                                c["idload"], fila["registros_agregados_dia"], dia, creada)
            resumen.append(fila)

        cur.execute(SQL_ESTADOS, params)
        estados = [
            {"fecha_marcacion": dia, "marcador": marcador, **e}
            for e in cur.fetchall()
        ]

    _calcular_pct_estados(estados)
    _calcular_pct_estados(estados_hist)
    return resumen, estados, estados_hist


def _inicio_carga(creada: datetime | None) -> datetime:
    # Un día antes por si el reloj del log y el de cti_loads no coinciden exacto.
    return datetime.combine(creada.date() - timedelta(days=1), time.min) if creada else SIN_LIMITE


def _marcar_crecimiento(fila: dict, inicio_dia: datetime) -> None:
    if fila.get("registros_marcados_hist") is not None:
        fila["registros_sin_marcar_hist"] = fila["registros_cargados"] - fila["registros_marcados_hist"]
    agregados = fila["registros_cargados"] - fila["registros_inicio_dia"]
    fila["registros_agregados_dia"] = agregados
    creada = fila["fecha_creacion_carga"]
    fila["crecio_despues_de_creada"] = int(agregados > 0 and creada is not None and creada < inicio_dia)


def _sin_tz(valor):
    # MySQL datetime y openpyxl no aceptan zona horaria
    return valor.replace(tzinfo=None) if getattr(valor, "tzinfo", None) else valor


def _calcular_pct_estados(estados: list[dict]) -> None:
    totales: dict[int, int] = {}
    for e in estados:
        totales[e["idload"]] = totales.get(e["idload"], 0) + e["marcaciones"]
    for e in estados:
        total = totales[e["idload"]]
        e["pct_marcaciones"] = (
            round(Decimal(100) * e["marcaciones"] / total, 2) if total else None
        )

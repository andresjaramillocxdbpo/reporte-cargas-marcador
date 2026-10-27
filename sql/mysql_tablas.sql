-- Tablas de reporte en MySQL/MariaDB. Los marcadores (PostgreSQL) solo se leen.
--
-- Las tablas rpt_cargas_* son históricas: cada ejecución agrega sus filas con su
-- id_ejecucion y nunca borra las anteriores. Así queda qué se reportó cada vez y
-- cuántos registros tenía la carga en ese momento. Las vistas v_*_vigente
-- muestran solo la última ejecución exitosa de cada día y marcador.

-- Cada corrida del script por marcador.
create table if not exists rpt_ejecuciones (
    id_ejecucion   int           not null auto_increment,
    marcador       varchar(30)   not null,
    fecha_desde    date          not null,
    fecha_hasta    date          not null,
    origen         varchar(20)   not null,               -- automatico | manual
    equipo         varchar(100),
    inicio         datetime      not null,
    fin            datetime,
    estado         varchar(10)   not null,               -- EN_CURSO | OK | ERROR
    cargas         int,
    mensaje        text,
    primary key (id_ejecucion),
    key ix_ejecuciones_marcador (marcador, estado, fecha_desde, fecha_hasta)
) engine=InnoDB default charset=utf8mb4;

-- Una fila por ejecución, día, marcador y carga marcada ese día.
create table if not exists rpt_cargas_marcacion_diaria (
    id_ejecucion             int           not null,
    fecha_marcacion          date          not null,
    marcador                 varchar(30)   not null,
    idload                   int           not null,
    carga                    varchar(255),
    tipo_base                varchar(100),             -- cti_campaign.descripcion
    skilldef                 varchar(100),
    fecha_creacion_carga     datetime,                 -- cti_loads.created_at
    registros_cti_loads      int,                      -- cti_loads.processed_records al momento de la ejecución
    registros_inicio_dia     int,                      -- filas en skill_{skilldef}_data al iniciar el día
    registros_cargados       int,                      -- filas en skill_{skilldef}_data al terminar el día
    registros_agregados_dia  int,                      -- fin - inicio
    crecio_despues_de_creada tinyint(1),               -- 1 si se agregaron registros a una carga de días anteriores
    numeros_unicos           int,                      -- number1 distintos al terminar el día
    marcaciones_dia          int,                      -- intentos del día
    numeros_marcados_dia     int,                      -- números distintos tocados en el día
    min_intentos_dia         int,
    prom_intentos_dia        decimal(10,2),
    max_intentos_dia         int,
    registros_marcados_hist  int,                      -- registros con al menos una marcación, desde la carga
    registros_sin_marcar_hist int,                     -- registros_cargados - registros_marcados_hist
    numeros_marcados_hist    int,                      -- desde la carga hasta el fin del día
    pct_avance_hist          decimal(5,2),
    min_intentos_hist        int,
    prom_intentos_hist       decimal(10,2),
    max_intentos_hist        int,
    primary key (id_ejecucion, marcador, fecha_marcacion, idload),
    key ix_marcacion_carga (marcador, idload, fecha_marcacion),
    key ix_marcacion_fecha (fecha_marcacion, marcador)
) engine=InnoDB default charset=utf8mb4;

-- Distribución de cti_log_calls.resultdesc por ejecución, día, marcador y carga.
create table if not exists rpt_cargas_resultados_diaria (
    id_ejecucion      int            not null,
    fecha_marcacion   date           not null,
    marcador          varchar(30)    not null,
    idload            int            not null,
    resultdesc        varchar(255)   not null,
    marcaciones       int,
    numeros           int,                             -- idreg distintos con ese resultado
    pct_marcaciones   decimal(5,2),                    -- % sobre las marcaciones del día de la carga
    primary key (id_ejecucion, marcador, fecha_marcacion, idload, resultdesc),
    key ix_resultados_fecha (fecha_marcacion, marcador)
) engine=InnoDB default charset=utf8mb4;

-- Distribución de resultdesc acumulada: desde la creación de la carga hasta el
-- fin de fecha_marcacion. Mismas columnas que la del día.
create table if not exists rpt_cargas_resultados_hist (
    id_ejecucion      int            not null,
    fecha_marcacion   date           not null,           -- día de corte del acumulado
    marcador          varchar(30)    not null,
    idload            int            not null,
    resultdesc        varchar(255)   not null,
    marcaciones       int,
    numeros           int,                               -- idreg distintos con ese resultado
    pct_marcaciones   decimal(5,2),                      -- % sobre todas las marcaciones de la carga
    primary key (id_ejecucion, marcador, fecha_marcacion, idload, resultdesc),
    key ix_resultados_hist_fecha (fecha_marcacion, marcador)
) engine=InnoDB default charset=utf8mb4;

-- Última versión de cada día: la de la ejecución OK más reciente que cubrió ese día.
create or replace view v_cargas_marcacion_vigente as
select r.*
from rpt_cargas_marcacion_diaria r
join rpt_ejecuciones e on e.id_ejecucion = r.id_ejecucion and e.estado = 'OK'
where not exists (
    select 1 from rpt_ejecuciones n
    where n.marcador = r.marcador and n.estado = 'OK'
      and n.id_ejecucion > r.id_ejecucion
      and r.fecha_marcacion between n.fecha_desde and n.fecha_hasta
);

create or replace view v_cargas_resultados_vigente as
select r.*
from rpt_cargas_resultados_diaria r
join rpt_ejecuciones e on e.id_ejecucion = r.id_ejecucion and e.estado = 'OK'
where not exists (
    select 1 from rpt_ejecuciones n
    where n.marcador = r.marcador and n.estado = 'OK'
      and n.id_ejecucion > r.id_ejecucion
      and r.fecha_marcacion between n.fecha_desde and n.fecha_hasta
);

create or replace view v_cargas_resultados_hist_vigente as
select r.*
from rpt_cargas_resultados_hist r
join rpt_ejecuciones e on e.id_ejecucion = r.id_ejecucion and e.estado = 'OK'
where not exists (
    select 1 from rpt_ejecuciones n
    where n.marcador = r.marcador and n.estado = 'OK'
      and n.id_ejecucion > r.id_ejecucion
      and r.fecha_marcacion between n.fecha_desde and n.fecha_hasta
);

-- Cargas que crecieron después de creadas: en el mismo día (registros_agregados_dia)
-- o entre dos días en que se reportaron (contra el día anterior con datos).
create or replace view v_cargas_crecimiento as
select *
from (
    select v.marcador, v.idload, v.carga, v.tipo_base, v.fecha_creacion_carga,
           v.fecha_marcacion,
           lag(v.fecha_marcacion)    over w as fecha_reporte_anterior,
           lag(v.registros_cargados) over w as registros_reporte_anterior,
           v.registros_inicio_dia,
           v.registros_cargados,
           v.registros_agregados_dia,
           v.registros_cargados - lag(v.registros_cargados) over w as crecimiento_vs_anterior
    from v_cargas_marcacion_vigente v
    window w as (partition by v.marcador, v.idload order by v.fecha_marcacion)
) x
where x.crecimiento_vs_anterior <> 0
   or (x.registros_agregados_dia > 0 and date(x.fecha_creacion_carga) < x.fecha_marcacion);

-- Comparación de cada carga: histórico (desde su creación) contra el día.
create or replace view v_cargas_dia_vs_historico as
select  fecha_marcacion,
        marcador,
        tipo_base,
        idload,
        carga,
        fecha_creacion_carga,
        datediff(fecha_marcacion, date(fecha_creacion_carga)) as dias_desde_creacion,
        -- histórico
        registros_cargados                as registros,
        registros_marcados_hist           as registros_con_marcacion,
        registros_sin_marcar_hist         as registros_sin_marcacion,
        pct_avance_hist,
        min_intentos_hist,
        prom_intentos_hist,
        max_intentos_hist,
        -- día
        marcaciones_dia,
        numeros_marcados_dia,
        min_intentos_dia,
        prom_intentos_dia,
        max_intentos_dia
from v_cargas_marcacion_vigente;

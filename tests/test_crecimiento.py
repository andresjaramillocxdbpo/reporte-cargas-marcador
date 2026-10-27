from datetime import datetime

from reporte_cargas.extraccion import _marcar_crecimiento

INICIO_DIA = datetime(2026, 10, 23)


def _fila(inicio, fin, creada):
    return {"registros_inicio_dia": inicio, "registros_cargados": fin, "fecha_creacion_carga": creada}


def test_carga_creada_ese_dia_no_cuenta_como_crecimiento():
    f = _fila(0, 39222, datetime(2026, 10, 23, 8, 0))
    _marcar_crecimiento(f, INICIO_DIA)
    assert f["registros_agregados_dia"] == 39222
    assert f["crecio_despues_de_creada"] == 0


def test_carga_vieja_que_recibe_registros_crecio():
    f = _fila(39222, 40000, datetime(2026, 10, 21, 16, 51))
    _marcar_crecimiento(f, INICIO_DIA)
    assert f["registros_agregados_dia"] == 778
    assert f["crecio_despues_de_creada"] == 1


def test_registros_sin_marcar():
    f = {**_fila(39222, 39222, datetime(2026, 10, 21)), "registros_marcados_hist": 39000}
    _marcar_crecimiento(f, INICIO_DIA)
    assert f["registros_sin_marcar_hist"] == 222


def test_carga_sin_cambios():
    f = _fila(39222, 39222, datetime(2026, 10, 21, 16, 51))
    _marcar_crecimiento(f, INICIO_DIA)
    assert f["crecio_despues_de_creada"] == 0

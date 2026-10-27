from datetime import date

import pytest

from reporte_cargas.periodo import dia_a_reportar, rango


@pytest.mark.parametrize("hoy, esperado", [
    (date(2026, 10, 26), date(2026, 10, 25)),   # lunes -> domingo
    (date(2026, 10, 25), date(2026, 10, 24)),   # domingo -> sábado
    (date(2026, 10, 27), date(2026, 10, 26)),   # martes -> lunes
    (date(2026, 11, 1), date(2026, 10, 31)),    # cambio de mes
])
def test_siempre_el_dia_anterior(hoy, esperado):
    assert dia_a_reportar(hoy) == esperado


def test_rango_inclusivo():
    assert rango(date(2026, 10, 20), date(2026, 10, 22)) == [
        date(2026, 10, 20), date(2026, 10, 21), date(2026, 10, 22)]


def test_rango_invertido_falla():
    with pytest.raises(ValueError):
        rango(date(2026, 10, 22), date(2026, 10, 20))

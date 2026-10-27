from datetime import date, datetime
from decimal import Decimal

from reporte_cargas.correo import ALERTAS_POR_DEFECTO, armar_html, clasificar

DIA = date(2026, 10, 24)


def _carga(idload, registros, pct, prom_hist, creada=datetime(2026, 10, 3), marcador="ENIGMA_CXD_1",
           tipo="HOGAR", agregados=0):
    pct = Decimal(pct)
    return {
        "fecha_marcacion": DIA, "marcador": marcador, "idload": idload, "carga": f"carga {idload}",
        "tipo_base": tipo, "fecha_creacion_carga": creada, "crecio_despues_de_creada": int(agregados > 0),
        "registros_inicio_dia": registros - agregados, "registros_agregados_dia": agregados,
        "registros_cargados": registros, "registros_marcados_hist": int(registros * pct / 100),
        "registros_sin_marcar_hist": registros - int(registros * pct / 100),
        "pct_avance_hist": pct, "min_intentos_hist": 1, "prom_intentos_hist": Decimal(prom_hist),
        "max_intentos_hist": 37, "marcaciones_dia": 80, "numeros_marcados_dia": 80,
        "min_intentos_dia": 1, "prom_intentos_dia": Decimal("1.00"), "max_intentos_dia": 1,
    }


def _estado(idload, resultdesc, marcaciones, marcador="ENIGMA_CXD_1"):
    return {"fecha_marcacion": DIA, "marcador": marcador, "idload": idload,
            "resultdesc": resultdesc, "marcaciones": marcaciones, "numeros": marcaciones}


def test_clasifica_trabajadas_y_poco_tocadas():
    resumen = [
        _carga(155, 8090, "99.53", "6.36"),                               # muy trabajada
        _carga(447, 81911, "1.95", "1.00"),                               # poco tocada
        _carga(500, 5000, "10", "1.00", creada=datetime(2026, 10, 24)),   # recién creada: no alerta
        _carga(191, 1, "100", "9"),                                       # prueba: se ignora
        _carga(146, 91271, "99.14", "3.64"),                              # normal
    ]
    trabajadas, poco_tocadas = clasificar(resumen, ALERTAS_POR_DEFECTO)
    assert [f["idload"] for f in trabajadas] == [155]
    assert [f["idload"] for f in poco_tocadas] == [447]


def test_umbral_configurable():
    resumen = [_carga(146, 91271, "99.14", "3.64")]
    trabajadas, _ = clasificar(resumen, {**ALERTAS_POR_DEFECTO, "prom_intentos_hist_alto": 3})
    assert [f["idload"] for f in trabajadas] == [146]


def test_correo_completo():
    resumen = [_carga(155, 8090, "99.53", "6.36"), _carga(447, 81911, "1.95", "1.00", tipo="PORTA"),
               _carga(439, 11742, "42.37", "1.00", agregados=334), _carga(191, 1, "100", "2"),
               _carga(462, 63481, "100", "1.01", marcador="ENIGMA_CXD_2")]
    estados = [_estado(155, "No Answer", 60), _estado(155, "DialError", 20),
               _estado(462, "No Answer", 80, marcador="ENIGMA_CXD_2")]
    hist = [_estado(155, "No Answer", 600), _estado(155, "Sin Ruta", 400)]
    cuerpo = armar_html(resumen, estados, hist, DIA, [], ["ENIGMA_CXD_1", "ENIGMA_CXD_2"])

    for texto in ("Puntos clave", "Requiere atención", "Muy trabajada", "Poco tocada",
                  "Creció después de creada", "Histórico desde la creación", "Resultados del día",
                  "Resultados históricos", "ENIGMA_CXD_2", "Cargas de prueba"):
        assert texto in cuerpo, texto
    # la carga de prueba no entra en las tablas, solo en la nota
    assert cuerpo.count("carga 191") == 1
    # el histórico de 155 muestra Sin Ruta dentro de "Otros" (no es top del día) = 40 %
    assert "40,0" in cuerpo


def test_marcador_con_error_se_avisa():
    cuerpo = armar_html([_carga(155, 8090, "99.53", "6.36")], [], [], DIA,
                        ["ENIGMA_CXD_2"], ["ENIGMA_CXD_1", "ENIGMA_CXD_2"])
    assert "No se pudo procesar ENIGMA_CXD_2" in cuerpo

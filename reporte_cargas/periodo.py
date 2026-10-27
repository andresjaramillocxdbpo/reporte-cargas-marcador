from datetime import date, timedelta


def dia_a_reportar(hoy: date) -> date:
    """Siempre el día anterior; corre todos los días, incluidos domingos y festivos."""
    return hoy - timedelta(days=1)


def rango(desde: date, hasta: date) -> list[date]:
    if hasta < desde:
        raise ValueError("La fecha final es anterior a la inicial")
    return [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]

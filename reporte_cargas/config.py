import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class ConexionPg:
    nombre: str
    host: str
    port: int
    db: str
    user: str
    password: str


@dataclass(frozen=True)
class ConexionMysql:
    host: str
    port: int
    db: str
    user: str
    password: str


@dataclass(frozen=True)
class Config:
    marcadores: list[ConexionPg]
    mysql: ConexionMysql | None
    typecall: str
    pg_statement_timeout_ms: int
    carpeta_salida: str


def _requerida(clave: str) -> str:
    valor = os.getenv(clave, "").strip()
    if not valor:
        raise ValueError(f"Falta la variable {clave} en el .env")
    return valor


def cargar_config(requiere_mysql: bool = True) -> Config:
    load_dotenv()

    nombres = [n.strip() for n in _requerida("MARCADORES").split(",") if n.strip()]
    marcadores = [
        ConexionPg(
            nombre=n,
            host=_requerida(f"PG_{n}_HOST"),
            port=int(os.getenv(f"PG_{n}_PORT", "5432")),
            db=_requerida(f"PG_{n}_DB"),
            user=_requerida(f"PG_{n}_USER"),
            password=os.getenv(f"PG_{n}_PASSWORD", ""),
        )
        for n in nombres
    ]

    if requiere_mysql and os.getenv("MYSQL_HABILITADO", "1").strip() != "0":
        mysql = ConexionMysql(
            host=_requerida("MYSQL_HOST"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            db=_requerida("MYSQL_DB"),
            user=_requerida("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD", ""),
        )
    else:
        mysql = None

    return Config(
        marcadores=marcadores,
        mysql=mysql,
        typecall=os.getenv("TYPECALL", "CallAuto"),
        pg_statement_timeout_ms=int(os.getenv("PG_STATEMENT_TIMEOUT_MS", "600000")),
        carpeta_salida=os.getenv("CARPETA_SALIDA", "salidas"),
    )

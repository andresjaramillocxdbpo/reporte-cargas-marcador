"""Envío del reporte por correo con Microsoft Graph (/me/sendMail).

Usa el mismo esquema que los otros proyectos: cliente público de Office y el
token guardado en msal_cache.bin. La programada nunca abre login: si el token
no sirve, falla con un mensaje claro y hay que correr una vez, a mano:

    python -m reporte_cargas.correo --login
"""

import argparse
import base64
import json
import logging
import sys
from pathlib import Path

import msal
import requests

from .plantilla_correo import ALERTAS_POR_DEFECTO, armar_html, clasificar  # noqa: F401

log = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parent.parent
CONFIG_PATH = RAIZ / "config" / "correo.json"
CACHE_PATH = RAIZ / "msal_cache.bin"

TENANT = "common"
CLIENT_ID = "d3590ed6-52b3-4102-aeff-aad2292ab01c"
SCOPES = ["https://graph.microsoft.com/Mail.Send"]
GRAPH_SENDMAIL_URL = "https://graph.microsoft.com/v1.0/me/sendMail"

# Graph acepta adjuntos de hasta ~3 MB dentro de sendMail
MAX_ADJUNTO_BYTES = 3 * 1024 * 1024


# ── Configuración ──────────────────────────────────────────────────────────

def cargar_config_correo(ruta: Path = CONFIG_PATH) -> dict:
    if not ruta.exists():
        raise FileNotFoundError(f"No existe {ruta}. Copie config/correo.example.json como correo.json")
    cfg = json.loads(ruta.read_text(encoding="utf-8"))
    for clave in ("para", "cc", "cco"):
        cfg[clave] = [c.strip() for c in cfg.get(clave, []) if c and c.strip()]
        invalidos = [c for c in cfg[clave] if "@" not in c]
        if invalidos:
            raise ValueError(f"Correos inválidos en '{clave}': {invalidos}")
    if cfg.get("enviar", True) and not cfg["para"]:
        raise ValueError("config/correo.json no tiene destinatarios en 'para'")
    cfg.setdefault("asunto", "Reporte cargas marcador {periodo}")
    cfg.setdefault("adjuntar_excel", True)
    cfg["alertas"] = {**ALERTAS_POR_DEFECTO, **cfg.get("alertas", {})}
    return cfg


# ── Token ──────────────────────────────────────────────────────────────────

def _app_y_cache() -> tuple[msal.PublicClientApplication, msal.SerializableTokenCache]:
    cache = msal.SerializableTokenCache()
    if CACHE_PATH.exists():
        cache.deserialize(CACHE_PATH.read_text(encoding="utf-8"))
    app = msal.PublicClientApplication(
        CLIENT_ID, authority=f"https://login.microsoftonline.com/{TENANT}", token_cache=cache)
    return app, cache


def _guardar_cache(cache: msal.SerializableTokenCache) -> None:
    if cache.has_state_changed:
        CACHE_PATH.write_text(cache.serialize(), encoding="utf-8")


def obtener_token() -> str:
    """Token sin intervención. Nunca abre login (corre en una tarea programada)."""
    app, cache = _app_y_cache()
    cuentas = app.get_accounts()
    if cuentas:
        resultado = app.acquire_token_silent(SCOPES, account=cuentas[0])
        if resultado and "access_token" in resultado:
            _guardar_cache(cache)
            return resultado["access_token"]
    raise RuntimeError("El token de correo venció o no existe. "
                       "Corra una vez: python -m reporte_cargas.correo --login")


def login_interactivo() -> None:
    app, cache = _app_y_cache()
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise RuntimeError(f"No se pudo iniciar device flow: {flow.get('error_description')}")
    print("\n" + flow["message"])
    resultado = app.acquire_token_by_device_flow(flow)
    if "access_token" not in resultado:
        raise RuntimeError(f"Error de autenticación: {resultado.get('error_description')}")
    _guardar_cache(cache)
    print(f"Listo, token guardado en {CACHE_PATH}")


# ── Envío ──────────────────────────────────────────────────────────────────

def enviar(cfg: dict, asunto: str, cuerpo_html: str, adjunto: Path | None) -> None:
    mensaje = {
        "subject": asunto,
        "body": {"contentType": "HTML", "content": cuerpo_html},
        "toRecipients": [{"emailAddress": {"address": c}} for c in cfg["para"]],
        "ccRecipients": [{"emailAddress": {"address": c}} for c in cfg["cc"]],
        "bccRecipients": [{"emailAddress": {"address": c}} for c in cfg["cco"]],
    }
    if adjunto:
        contenido = adjunto.read_bytes()
        if len(contenido) > MAX_ADJUNTO_BYTES:
            log.warning("El Excel pesa %d bytes, más que el límite de Graph; se envía sin adjunto", len(contenido))
        else:
            mensaje["attachments"] = [{
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": adjunto.name,
                "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "contentBytes": base64.b64encode(contenido).decode("ascii"),
            }]

    respuesta = requests.post(
        GRAPH_SENDMAIL_URL,
        headers={"Authorization": f"Bearer {obtener_token()}", "Content-Type": "application/json"},
        json={"message": mensaje, "saveToSentItems": "true"},
        timeout=60,
    )
    if respuesta.status_code != 202:
        raise RuntimeError(f"Error enviando correo: {respuesta.status_code} {respuesta.text[:500]}")
    log.info("Correo enviado. Para: %s | CC: %s | CCO: %d",
             ", ".join(cfg["para"]), ", ".join(cfg["cc"]) or "-", len(cfg["cco"]))


def main() -> int:
    p = argparse.ArgumentParser(prog="reporte_cargas.correo")
    p.add_argument("--login", action="store_true", help="Inicia sesión (device flow) y guarda el token")
    p.add_argument("--probar-token", action="store_true", help="Verifica que el token sirve, sin enviar nada")
    args = p.parse_args()
    if args.login:
        login_interactivo()
    elif args.probar_token:
        obtener_token()
        print("Token OK: se puede enviar correo sin login")
    else:
        p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

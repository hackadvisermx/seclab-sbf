"""
scripts/seclab_network.py
Módulo de seguridad de red para clasificación de endpoints y destinos de inferencia/herramientas.
"""

from __future__ import annotations

import ipaddress
from typing import Any, Dict, Optional
from urllib.parse import urlsplit


def normalize_endpoint_url(url: Optional[str]) -> Optional[str]:
    """Limpia y valida que la URL tenga protocolo http:// o https:// y sin espacios accidentales."""
    if not url:
        return None
    cleaned = url.strip()
    if not cleaned:
        return None
    if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
        if (
            cleaned.startswith("localhost")
            or cleaned.startswith("127.0.0.1")
            or ":11434" in cleaned
            or ":8000" in cleaned
        ):
            cleaned = f"http://{cleaned}"
        else:
            cleaned = f"https://{cleaned}"
    return cleaned.rstrip("/")


def classify_endpoint(url: Optional[str]) -> Dict[str, Any]:
    """
    Clasifica un endpoint según su destino de red y evalúa la seguridad del transporte (TLS).
    Retorna un diccionario con:
    - classification: "LOCAL_LOOPBACK" | "PRIVATE_NETWORK" | "PUBLIC_REMOTE" | "UNKNOWN"
    - is_local: bool (True para LOCAL_LOOPBACK y PRIVATE_NETWORK)
    - is_insecure_transport: bool (True si se usa http:// en destinos remotos o de red privada)
    - transport_warning: Optional[str]
    - hostname: Optional[str]
    - scheme: Optional[str]
    - normalized_url: Optional[str]
    """
    norm = normalize_endpoint_url(url)
    if not norm:
        return {
            "classification": "UNKNOWN",
            "is_local": False,
            "is_insecure_transport": False,
            "transport_warning": None,
            "hostname": None,
            "scheme": None,
            "normalized_url": None,
        }

    parsed = urlsplit(norm)
    scheme = parsed.scheme.lower() if parsed.scheme else "http"
    hostname = (parsed.hostname or "").lower()

    if not hostname:
        return {
            "classification": "UNKNOWN",
            "is_local": False,
            "is_insecure_transport": False,
            "transport_warning": None,
            "hostname": None,
            "scheme": scheme,
            "normalized_url": norm,
        }

    # 1. Comprobar loopback
    is_loopback = False
    if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or hostname.endswith(".localhost"):
        is_loopback = True
    else:
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_loopback or ip == ipaddress.ip_address("0.0.0.0"):
                is_loopback = True
        except ValueError:
            pass

    if is_loopback:
        return {
            "classification": "LOCAL_LOOPBACK",
            "is_local": True,
            "is_insecure_transport": False,
            "transport_warning": None,
            "hostname": hostname,
            "scheme": scheme,
            "normalized_url": norm,
        }

    # 2. Comprobar red privada o interna
    is_private = False
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_link_local or ip.is_reserved:
            is_private = True
    except ValueError:
        if hostname in ("host.docker.internal", "gateway.docker.internal") or any(
            hostname.endswith(sfx) for sfx in (".local", ".internal", ".lan", ".home.arpa")
        ):
            is_private = True

    if is_private:
        is_insecure = (scheme == "http")
        warning = (
            "Aviso: El endpoint de red privada utiliza HTTP sin cifrado (texto claro). "
            "El tráfico dentro del segmento local no cuenta con cifrado TLS."
            if is_insecure
            else None
        )
        return {
            "classification": "PRIVATE_NETWORK",
            "is_local": True,
            "is_insecure_transport": is_insecure,
            "transport_warning": warning,
            "hostname": hostname,
            "scheme": scheme,
            "normalized_url": norm,
        }

    # 3. Destino remoto público
    is_insecure = (scheme == "http")
    warning = (
        "⚠️ Advertencia de seguridad crítica: El endpoint remoto público utiliza HTTP sin cifrar (texto claro). "
        "El contexto confidencial del engagement y las API keys viajarán expuestos a interceptación."
        if is_insecure
        else None
    )
    return {
        "classification": "PUBLIC_REMOTE",
        "is_local": False,
        "is_insecure_transport": is_insecure,
        "transport_warning": warning,
        "hostname": hostname,
        "scheme": scheme,
        "normalized_url": norm,
    }

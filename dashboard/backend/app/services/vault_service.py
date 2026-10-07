import datetime
import time
from urllib.parse import urlsplit
from typing import Any, Dict, List, Optional
import httpx
from app.core.database import get_db_connection
from app.core.security import encrypt_secret, decrypt_secret, mask_secret
from app.models.schemas import ApiKeyCreate, ApiKeyResponse, ApiKeyUpdate, HealthCheckResult


def normalize_endpoint_url(url: Optional[str]) -> Optional[str]:
    """Limpia y valida que la URL tenga protocolo http:// o https:// y sin espacios accidentales."""
    if not url:
        return None
    cleaned = url.strip()
    if not cleaned:
        return None
    # Si falta protocolo, agregar http:// para localhost/127.0.0.1 o https:// para dominios
    if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
        if cleaned.startswith("localhost") or cleaned.startswith("127.0.0.1") or ":11434" in cleaned or ":8000" in cleaned:
            cleaned = f"http://{cleaned}"
        else:
            cleaned = f"https://{cleaned}"
    return cleaned.rstrip("/")


def is_openrouter_url(url: Optional[str]) -> bool:
    return urlsplit(normalize_endpoint_url(url) or "").hostname in ("openrouter.ai", "eu.openrouter.ai")


def openrouter_base_url(url: Optional[str]) -> str:
    parsed = urlsplit(normalize_endpoint_url(url) or "https://openrouter.ai/api/v1")
    if parsed.hostname not in ("openrouter.ai", "eu.openrouter.ai") or parsed.scheme != "https" or parsed.username or parsed.password or parsed.port:
        raise ValueError("OpenRouter requiere https://openrouter.ai/api/v1 o https://eu.openrouter.ai/api/v1")
    return f"https://{parsed.hostname}/api/v1"


class VaultService:
    async def list_models(self, provider: str, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """Consulta el catálogo de modelos de un proveedor LLM, sin necesidad de
        haber guardado la clave antes (usado tanto por el modal de alta del
        Vault como por el selector del Chat Táctico / Copiloto). Cada
        proveedor tiene su propio formato de listado; se normalizan todos a
        {"id", "name"} para que la UI los trate de forma uniforme."""
        entry = self.get_key_entry(provider) if not api_key else None
        if not api_key:
            if not entry or not entry.get("is_active"):
                raise ValueError("Proveedor no configurado o inactivo; introduce una clave para consultar modelos")
            api_key = entry["api_key"]
            base_url = base_url or entry.get("base_url")
        api_key = api_key.strip()
        default_model = entry.get("model_name") if entry else None

        if provider == "openrouter" or is_openrouter_url(base_url):
            models = await self._list_openrouter_models(api_key, base_url)
        elif provider == "openai":
            models = await self._list_openai_compatible_models(api_key, normalize_endpoint_url(base_url) or "https://api.openai.com/v1", "OpenAI")
        elif provider == "anthropic":
            models = await self._list_anthropic_models(api_key, normalize_endpoint_url(base_url) or "https://api.anthropic.com/v1")
        elif provider == "gemini":
            models = await self._list_gemini_models(api_key, normalize_endpoint_url(base_url) or "https://generativelanguage.googleapis.com/v1beta")
        elif provider == "custom_llm":
            clean_base = normalize_endpoint_url(base_url)
            if not clean_base:
                raise ValueError("Especifica un Base URL antes de consultar el catálogo de este endpoint")
            models = await self._list_openai_compatible_models(api_key, clean_base, "el endpoint")
        else:
            raise ValueError(f"El catálogo de modelos no está disponible para el proveedor '{provider}'")

        return {"models": models, "default_model": default_model}

    async def _list_openrouter_models(self, api_key: str, base_url: Optional[str]) -> list:
        base = openrouter_base_url(base_url)
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(f"{base}/models/user", headers={"Authorization": f"Bearer {api_key}"})
            if response.status_code != 200:
                raise RuntimeError(f"No se pudo consultar el catálogo de OpenRouter (HTTP {response.status_code})")
            try:
                body = response.json()
                data = body.get("data") if isinstance(body, dict) else None
            except ValueError:
                raise RuntimeError("Catálogo de OpenRouter inválido") from None
            if not isinstance(data, list):
                raise RuntimeError("Catálogo de OpenRouter inválido")
            models = {m["id"]: {"id": m["id"], "name": m.get("name") or m["id"], "context_length": m.get("context_length"), "pricing": m.get("pricing") or {}} for m in data if isinstance(m, dict) and isinstance(m.get("id"), str)}
            return sorted(models.values(), key=lambda m: m["name"].casefold())
        except httpx.HTTPError:
            raise RuntimeError("No se pudo conectar con OpenRouter para consultar modelos") from None

    async def _list_openai_compatible_models(self, api_key: str, base: str, label: str) -> list:
        """Lista modelos de cualquier endpoint compatible con la API de OpenAI:
        GET {base}/models. Sirve tanto para OpenAI real como para un servidor
        local (Ollama, LM Studio, vLLM) registrado como custom_llm."""
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(f"{base}/models", headers=headers)
        except httpx.HTTPError:
            raise RuntimeError(f"No se pudo conectar con {label} para consultar modelos") from None
        if response.status_code != 200:
            raise RuntimeError(f"No se pudo consultar el catálogo de {label} (HTTP {response.status_code})")
        try:
            body = response.json()
            data = body.get("data") if isinstance(body, dict) else None
        except ValueError:
            raise RuntimeError(f"Catálogo de {label} inválido") from None
        if not isinstance(data, list):
            raise RuntimeError(f"Catálogo de {label} inválido")
        models = {m["id"]: {"id": m["id"], "name": m.get("name") or m["id"]} for m in data if isinstance(m, dict) and isinstance(m.get("id"), str)}
        return sorted(models.values(), key=lambda m: m["name"].casefold())

    async def _list_anthropic_models(self, api_key: str, base: str) -> list:
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(f"{base}/models", headers=headers)
        except httpx.HTTPError:
            raise RuntimeError("No se pudo conectar con Anthropic para consultar modelos") from None
        if response.status_code != 200:
            raise RuntimeError(f"No se pudo consultar el catálogo de Anthropic (HTTP {response.status_code})")
        try:
            body = response.json()
            data = body.get("data") if isinstance(body, dict) else None
        except ValueError:
            raise RuntimeError("Catálogo de Anthropic inválido") from None
        if not isinstance(data, list):
            raise RuntimeError("Catálogo de Anthropic inválido")
        models = {m["id"]: {"id": m["id"], "name": m.get("display_name") or m["id"]} for m in data if isinstance(m, dict) and isinstance(m.get("id"), str)}
        return sorted(models.values(), key=lambda m: m["name"].casefold())

    async def _list_gemini_models(self, api_key: str, base: str) -> list:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(f"{base}/models", params={"key": api_key})
        except httpx.HTTPError:
            raise RuntimeError("No se pudo conectar con Gemini para consultar modelos") from None
        if response.status_code != 200:
            raise RuntimeError(f"No se pudo consultar el catálogo de Gemini (HTTP {response.status_code})")
        try:
            body = response.json()
            data = body.get("models") if isinstance(body, dict) else None
        except ValueError:
            raise RuntimeError("Catálogo de Gemini inválido") from None
        if not isinstance(data, list):
            raise RuntimeError("Catálogo de Gemini inválido")
        models = {}
        for m in data:
            if not isinstance(m, dict) or not isinstance(m.get("name"), str):
                continue
            # Descarta modelos que no soportan generación de texto (p. ej.
            # embeddings): un dato real que Gemini declara, no una suposición
            # por nombre.
            methods = m.get("supportedGenerationMethods")
            if isinstance(methods, list) and "generateContent" not in methods:
                continue
            model_id = m["name"].removeprefix("models/")
            models[model_id] = {"id": model_id, "name": m.get("displayName") or model_id}
        return sorted(models.values(), key=lambda m: m["name"].casefold())

    def list_keys(self) -> List[ApiKeyResponse]:
        """Obtiene la lista de API keys configuradas con las claves enmascaradas."""
        conn = get_db_connection()
        rows = conn.execute("SELECT * FROM api_keys ORDER BY service_type, provider").fetchall()
        conn.close()

        results = []
        for r in rows:
            decrypted = decrypt_secret(r["encrypted_key"])
            results.append(
                ApiKeyResponse(
                    id=r["id"],
                    provider=r["provider"],
                    label=r["label"],
                    service_type=r["service_type"],
                    masked_key=mask_secret(decrypted),
                    base_url=r["base_url"],
                    model_name=r["model_name"],
                    is_active=bool(r["is_active"]),
                    last_checked=r["last_checked"],
                    status=r["status"],
                    status_message=r["status_message"],
                    created_at=r["created_at"] or "",
                    updated_at=r["updated_at"] or "",
                )
            )
        return results

    def get_raw_key(self, provider: str) -> Optional[str]:
        """Obtiene la clave descifrada para uso interno del proxy o clientes de auditoría."""
        entry = self.get_key_entry(provider)
        if not entry or not entry.get("is_active"):
            return None
        return entry.get("api_key")

    def get_key_entry(self, provider: str) -> Optional[Dict[str, Any]]:
        """Obtiene registro completo con la clave descifrada."""
        prov = provider.lower().strip()
        conn = get_db_connection()
        row = conn.execute("SELECT * FROM api_keys WHERE provider = ?", (prov,)).fetchone()
        if not row and prov == "openrouter":
            candidate = conn.execute("SELECT * FROM api_keys WHERE provider = 'custom_llm'").fetchone()
            if candidate and is_openrouter_url(candidate["base_url"]):
                row = candidate
        conn.close()
        if not row:
            return None
        data = dict(row)
        data["api_key"] = decrypt_secret(row["encrypted_key"])
        data["base_url"] = normalize_endpoint_url(data.get("base_url"))
        return data

    def upsert_key(self, key_create: ApiKeyCreate) -> ApiKeyResponse:
        """Crea o reemplaza una API key en el vault cifrado."""
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        encrypted = encrypt_secret(key_create.api_key.strip() if key_create.api_key else "")
        clean_base_url = normalize_endpoint_url(key_create.base_url)
        clean_model = key_create.model_name.strip() if key_create.model_name else None

        conn = get_db_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO api_keys (
                    provider, label, service_type, encrypted_key, base_url, model_name,
                    is_active, last_checked, status, status_message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 'untested', NULL, ?, ?)
                ON CONFLICT(provider) DO UPDATE SET
                    label = excluded.label,
                    service_type = excluded.service_type,
                    encrypted_key = excluded.encrypted_key,
                    base_url = excluded.base_url,
                    model_name = excluded.model_name,
                    is_active = excluded.is_active,
                    status = 'untested',
                    updated_at = excluded.updated_at;
                """,
                (
                    key_create.provider.lower().strip(),
                    key_create.label.strip(),
                    key_create.service_type.strip(),
                    encrypted,
                    clean_base_url,
                    clean_model,
                    1 if key_create.is_active else 0,
                    now_ts,
                    now_ts,
                ),
            )
        conn.close()
        return self.get_response_by_provider(key_create.provider.lower().strip())

    def update_key(self, provider: str, update: ApiKeyUpdate) -> Optional[ApiKeyResponse]:
        """Actualiza parcialmente una clave existente."""
        current_prov = provider.lower().strip()
        target_prov = (update.provider.lower().strip() if update.provider else current_prov)

        conn = get_db_connection()
        row = conn.execute("SELECT * FROM api_keys WHERE provider = ?", (current_prov,)).fetchone()
        if not row:
            conn.close()
            return None

        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        label = (update.label.strip() if update.label.strip() else row["label"]) if update.label is not None else row["label"]
        base_url = normalize_endpoint_url(update.base_url) if update.base_url is not None else normalize_endpoint_url(row["base_url"])
        model_name = (update.model_name.strip() or None) if update.model_name is not None else row["model_name"]
        is_active = (1 if update.is_active else 0) if update.is_active is not None else row["is_active"]

        encrypted = row["encrypted_key"]
        if update.api_key and update.api_key.strip():
            encrypted = encrypt_secret(update.api_key.strip())

        status = row["status"]
        status_message = row["status_message"]
        if (update.api_key and update.api_key.strip()) or update.base_url is not None or update.model_name is not None or (target_prov != current_prov):
            status = "untested"
            status_message = "Configuración actualizada; pendiente de verificación"

        try:
            with conn:
                if target_prov != current_prov:
                    existing = conn.execute("SELECT 1 FROM api_keys WHERE provider = ?", (target_prov,)).fetchone()
                    if existing:
                        # No cerrar conn aqui: seguimos dentro de "with conn",
                        # que hace rollback al salir por excepcion. Cerrarla
                        # antes haria que ese rollback fallara con
                        # sqlite3.ProgrammingError, enmascarando este ValueError.
                        raise ValueError("Ya existe una clave para el proveedor elegido")
                    conn.execute("UPDATE api_keys SET provider = ? WHERE provider = ?", (target_prov, current_prov))
                    current_prov = target_prov

                conn.execute(
                    """
                    UPDATE api_keys SET
                        label = ?, base_url = ?, model_name = ?, is_active = ?,
                        encrypted_key = ?, status = ?, status_message = ?, updated_at = ?
                    WHERE provider = ?
                    """,
                    (label, base_url, model_name, is_active, encrypted, status, status_message, now_ts, current_prov),
                )
        finally:
            conn.close()
        return self.get_response_by_provider(current_prov)

    def delete_key(self, provider: str) -> bool:
        """Elimina una clave del vault."""
        conn = get_db_connection()
        with conn:
            cursor = conn.execute("DELETE FROM api_keys WHERE provider = ?", (provider.lower(),))
            deleted = cursor.rowcount > 0
        conn.close()
        return deleted

    def get_response_by_provider(self, provider: str) -> Optional[ApiKeyResponse]:
        conn = get_db_connection()
        r = conn.execute("SELECT * FROM api_keys WHERE provider = ?", (provider.lower(),)).fetchone()
        conn.close()
        if not r:
            return None
        decrypted = decrypt_secret(r["encrypted_key"])
        return ApiKeyResponse(
            id=r["id"],
            provider=r["provider"],
            label=r["label"],
            service_type=r["service_type"],
            masked_key=mask_secret(decrypted),
            base_url=r["base_url"],
            model_name=r["model_name"],
            is_active=bool(r["is_active"]),
            last_checked=r["last_checked"],
            status=r["status"],
            status_message=r["status_message"],
            created_at=r["created_at"] or "",
            updated_at=r["updated_at"] or "",
        )

    async def check_health(self, provider: str) -> HealthCheckResult:
        """Prueba la validez y conectividad de una API key contra su servicio upstream."""
        entry = self.get_key_entry(provider.lower())
        if not entry:
            return HealthCheckResult(provider=provider, status="error", message="Proveedor no encontrado en el vault")

        api_key = entry["api_key"]
        base_url = entry["base_url"]
        start_time = time.time()
        status = "error"
        message = ""
        details = {}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 1. SHODAN
                if provider == "shodan":
                    res = await client.get(f"https://api.shodan.io/api-info?key={api_key}")
                    if res.status_code == 200:
                        data = res.json()
                        status = "online"
                        message = f"Activa. Créditos de escaneo: {data.get('scan_credits', 'N/A')}, plan: {data.get('plan', 'N/A')}"
                        details = data
                    elif res.status_code == 401:
                        status = "error"
                        message = "API key de Shodan inválida o revocada (401)"
                    else:
                        status = "error"
                        message = f"Respuesta inesperada ({res.status_code})"

                # 2. CENSYS
                elif provider == "censys":
                    # Censys usualmente usa auth básica o token v2
                    auth = None
                    if ":" in api_key:
                        uid, secret = api_key.split(":", 1)
                        auth = (uid.strip(), secret.strip())
                    headers = {"Authorization": f"Bearer {api_key}"} if not auth else {}
                    res = await client.get("https://search.censys.io/api/v1/account", auth=auth, headers=headers)
                    if res.status_code == 200:
                        status = "online"
                        message = "Conexión a Censys validada exitosamente"
                        details = res.json()
                    elif res.status_code == 401:
                        status = "error"
                        message = "Credenciales Censys no autorizadas (401)"
                    else:
                        status = "error"
                        message = f"Censys retornó código {res.status_code}"

                # 3. VIRUSTOTAL
                elif provider == "virustotal":
                    res = await client.get(
                        "https://www.virustotal.com/api/v3/users/current",
                        headers={"x-apikey": api_key},
                    )
                    if res.status_code == 200:
                        status = "online"
                        user_info = res.json().get("data", {}).get("attributes", {})
                        message = f"Activa para usuario: {user_info.get('id', 'OK')}"
                        details = {"user": user_info.get("id")}
                    elif res.status_code == 401 or res.status_code == 403:
                        status = "error"
                        message = "API key de VirusTotal inválida (401/403)"
                    else:
                        status = "error"
                        message = f"VirusTotal código {res.status_code}"

                # 4. CHAOS / PROJECTDISCOVERY
                elif provider == "chaos":
                    res = await client.get(
                        "https://dns.projectdiscovery.io/dns/example.com",
                        headers={"Authorization": api_key},
                    )
                    if res.status_code in (200, 404):
                        status = "online"
                        message = "Chaos API key autenticada correctamente"
                    elif res.status_code == 401:
                        status = "error"
                        message = "API key de Chaos rechazada (401)"
                    else:
                        status = "error"
                        message = f"ProjectDiscovery Chaos código {res.status_code}"

                # 5. OPENAI
                elif provider == "openai":
                    res = await client.get(
                        "https://api.openai.com/v1/models",
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                    if res.status_code == 200:
                        status = "online"
                        models = [m["id"] for m in res.json().get("data", [])][:5]
                        message = f"Conexión exitosa. Modelos disponibles: {', '.join(models)}"
                        details = {"sample_models": models}
                    elif res.status_code == 401:
                        status = "error"
                        message = "API key de OpenAI incorrecta (401)"
                    elif res.status_code == 429:
                        status = "rate_limited"
                        message = "OpenAI cuota excedida o rate-limited (429)"
                    else:
                        status = "error"
                        message = f"OpenAI código {res.status_code}"

                # 6. ANTHROPIC
                elif provider == "anthropic":
                    res = await client.get(
                        "https://api.anthropic.com/v1/models",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                        },
                    )
                    if res.status_code == 200:
                        status = "online"
                        message = "Conexión a Anthropic validada exitosamente"
                    elif res.status_code == 401:
                        status = "error"
                        message = "API key de Anthropic inválida (401)"
                    else:
                        status = "error"
                        message = f"Anthropic código {res.status_code}"

                # 7. GEMINI
                elif provider == "gemini":
                    res = await client.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}")
                    if res.status_code == 200:
                        status = "online"
                        data = res.json()
                        models = [m["name"].split("/")[-1] for m in data.get("models", [])][:4]
                        message = f"Google Gemini activo. Modelos: {', '.join(models)}"
                        details = {"models": models}
                    elif res.status_code in (400, 401, 403):
                        status = "error"
                        message = "API key de Gemini rechazada (400/401/403)"
                    else:
                        status = "error"
                        message = f"Gemini código {res.status_code}"

                # 8. OPENROUTER
                elif provider == "openrouter":
                    clean_base = openrouter_base_url(base_url)
                    url = clean_base if clean_base.endswith("/auth/key") else f"{clean_base}/auth/key"
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "HTTP-Referer": "http://localhost:8080",
                        "X-Title": "SecLab Tactical Dashboard",
                    }
                    res = await client.get(url, headers=headers)
                    if res.status_code == 200:
                        data = res.json().get("data", {})
                        status = "online"
                        limit_val = data.get("limit")
                        limit_str = f"${limit_val:.2f}" if (isinstance(limit_val, (int, float)) and limit_val is not None) else "Sin límite"
                        usage_val = data.get("usage", 0)
                        message = f"Clave válida; la disponibilidad del modelo se verifica al consultar. Uso: ${usage_val:.4f}, Límite: {limit_str}"
                        details = data
                    elif res.status_code == 401:
                        status = "error"
                        message = "API key de OpenRouter inválida o revocada (401)"
                    elif res.status_code == 429:
                        status = "rate_limited"
                        message = "OpenRouter cuota excedida o rate-limited (429)"
                    else:
                        status = "error"
                        message = f"OpenRouter código {res.status_code}"

                # 9. CUSTOM LLM / HERMES PROXY LOCAL
                elif provider in ("custom_llm", "hermes_local"):
                    clean_base = normalize_endpoint_url(base_url) or "http://localhost:11434"
                    # Si apunta a openrouter, usar el probe de OpenRouter
                    if is_openrouter_url(clean_base):
                        clean_base = openrouter_base_url(clean_base)
                        if "/api/v1" not in clean_base:
                            clean_base = clean_base.rstrip("/") + "/api/v1"
                        url = clean_base if clean_base.endswith("/auth/key") else f"{clean_base}/auth/key"
                        headers = {
                            "Authorization": f"Bearer {api_key}",
                            "HTTP-Referer": "http://localhost:8080",
                            "X-Title": "SecLab Tactical Dashboard",
                        }
                        res = await client.get(url, headers=headers)
                        if res.status_code == 200:
                            data = res.json().get("data", {})
                            status = "online"
                            usage_val = data.get("usage", 0)
                            message = f"Clave válida; el modelo se verifica al consultar (vía custom_llm). Uso: ${usage_val:.4f}"
                            details = data
                        elif res.status_code == 401:
                            status = "error"
                            message = "API key de OpenRouter inválida (401)"
                        elif res.status_code == 429:
                            status = "rate_limited"
                            message = "OpenRouter cuota excedida (429)"
                        else:
                            status = "error"
                            message = f"OpenRouter código {res.status_code}"
                    else:
                        url = clean_base if clean_base.endswith("/models") else (
                            f"{clean_base}/models" if clean_base.endswith("/v1") else f"{clean_base}/v1/models"
                        )
                        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                        res = await client.get(url, headers=headers)
                        if res.status_code == 200:
                            status = "online"
                            message = f"Endpoint local {url} respondiendo OK"
                        else:
                            status = "error"
                            message = f"Endpoint {url} retornó código {res.status_code}"

                # 9. HACKTHEBOX
                elif provider == "hackthebox":
                    res = await client.get(
                        "https://www.hackthebox.com/api/v4/user/profile/basic",
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                    if res.status_code == 200:
                        status = "online"
                        profile = res.json().get("profile", {})
                        message = f"HTB activo para: {profile.get('name', 'Usuario')} (Rango: {profile.get('rank', 'N/A')})"
                        details = profile
                    else:
                        status = "error"
                        message = f"HTB API retornó {res.status_code}"

                else:
                    status = "online"
                    message = "Llave guardada (proveedor genérico)"

        except Exception as e:
            status = "error"
            message = f"Fallo de conexión: {str(e)}"

        latency = int((time.time() - start_time) * 1000)
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Actualizar estado en la base de datos
        conn = get_db_connection()
        with conn:
            conn.execute(
                "UPDATE api_keys SET status = ?, status_message = ?, last_checked = ? WHERE provider = ?",
                (status, message, now_ts, entry["provider"]),
            )
        conn.close()

        return HealthCheckResult(
            provider=provider,
            status=status,
            latency_ms=latency,
            message=message,
            details=details,
        )


vault_service = VaultService()

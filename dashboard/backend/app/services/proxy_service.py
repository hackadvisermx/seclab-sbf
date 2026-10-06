import datetime
import time
from typing import Any, Dict, List, Optional
import httpx
from app.core.database import get_db_connection
from app.services.vault_service import vault_service, normalize_endpoint_url
from app.models.schemas import ChatCompletionRequest, ChatCompletionResponse


PROFILE_DEFAULTS = {
    "quick": [
        ("openrouter", "deepseek/deepseek-chat"),
        ("gemini", "gemini-2.0-flash"),
        ("openai", "gpt-4o-mini"),
        ("anthropic", "claude-3-5-haiku-20241022"),
        ("custom_llm", "llama3:latest"),
    ],
    "deep": [
        ("openrouter", "anthropic/claude-3.5-sonnet"),
        ("anthropic", "claude-3-5-sonnet-20241022"),
        ("openai", "gpt-4o"),
        ("gemini", "gemini-1.5-pro"),
        ("custom_llm", "llama3:70b"),
    ],
    "local": [
        ("custom_llm", "local-model"),
    ],
}


class ProxyService:
    def _log_request(
        self,
        provider: str,
        model: str,
        service_type: str,
        status: str,
        latency_ms: int,
        tokens_used: int = 0,
        error_message: Optional[str] = None,
    ):
        """Registra cada interacción del proxy en la tabla de auditoría proxy_audit_log."""
        try:
            now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn = get_db_connection()
            with conn:
                conn.execute(
                    """
                    INSERT INTO proxy_audit_log (
                        provider, model, service_type, status, latency_ms,
                        tokens_used, error_message, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (provider, model, service_type, status, latency_ms, tokens_used, error_message, now_ts),
                )
            conn.close()
        except Exception:
            pass

    async def _dispatch_single_provider(
        self,
        provider: str,
        req: ChatCompletionRequest,
        model_override: Optional[str] = None,
    ) -> ChatCompletionResponse:
        entry = vault_service.get_key_entry(provider.lower())
        if not entry or not entry.get("api_key"):
            raise ValueError(f"Proveedor '{provider}' no configurado o sin API key.")

        api_key = entry["api_key"]
        base_url = entry.get("base_url")
        model = model_override or req.model or entry.get("model_name")
        start_time = time.time()

        async with httpx.AsyncClient(timeout=45.0) as client:
            # 1. OPENAI o COMPATIBLE (incluyendo OPENROUTER y CUSTOM_LLM hacia OpenRouter)
            if provider in ("openai", "custom_llm", "local", "openrouter"):
                clean_base = normalize_endpoint_url(base_url)
                is_openrouter = (provider == "openrouter") or ("openrouter.ai" in (clean_base or "").lower())
                if is_openrouter:
                    endpoint_base = clean_base or "https://openrouter.ai/api/v1"
                    if "openrouter.ai" in endpoint_base.lower() and "/api/v1" not in endpoint_base:
                        endpoint_base = endpoint_base.rstrip("/") + "/api/v1"
                    url = endpoint_base if endpoint_base.endswith("/chat/completions") else f"{endpoint_base}/chat/completions"
                    used_model = model or "anthropic/claude-3.5-sonnet"
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "HTTP-Referer": "http://localhost:8080",
                        "X-Title": "SecLab Tactical Dashboard",
                    }
                else:
                    endpoint_base = clean_base or "https://api.openai.com/v1"
                    url = endpoint_base if endpoint_base.endswith("/chat/completions") else f"{endpoint_base}/chat/completions"
                    used_model = model or ("gpt-4o-mini" if provider == "openai" else "local-model")
                    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

                payload = {
                    "model": used_model,
                    "messages": [{"role": m.role, "content": m.content} for m in req.messages],
                    "temperature": req.temperature,
                }
                if req.max_tokens:
                    payload["max_tokens"] = req.max_tokens

                res = await client.post(url, json=payload, headers=headers)
                if res.status_code != 200:
                    raise RuntimeError(f"Error {res.status_code} desde {provider}: {res.text}")
                data = res.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage")
                total_tokens = usage.get("total_tokens", 0) if usage else 0

            # 2. ANTHROPIC
            elif provider == "anthropic":
                url = "https://api.anthropic.com/v1/messages"
                used_model = model or "claude-3-5-sonnet-20241022"

                system_msg = ""
                chat_messages = []
                for m in req.messages:
                    if m.role == "system":
                        system_msg = m.content
                    else:
                        chat_messages.append({"role": m.role, "content": m.content})

                payload = {
                    "model": used_model,
                    "messages": chat_messages,
                    "max_tokens": req.max_tokens or 2000,
                    "temperature": req.temperature,
                }
                if system_msg:
                    payload["system"] = system_msg

                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code != 200:
                    raise RuntimeError(f"Error {res.status_code} de Anthropic: {res.text}")
                data = res.json()
                content = data["content"][0]["text"]
                usage = data.get("usage")
                total_tokens = (usage.get("input_tokens", 0) + usage.get("output_tokens", 0)) if usage else 0

            # 3. GOOGLE GEMINI
            elif provider == "gemini":
                used_model = model or "gemini-2.0-flash"
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{used_model}:generateContent?key={api_key}"

                contents = []
                for m in req.messages:
                    role = "user" if m.role in ("user", "system") else "model"
                    contents.append({"role": role, "parts": [{"text": m.content}]})

                payload = {
                    "contents": contents,
                    "generationConfig": {"temperature": req.temperature, "maxOutputTokens": req.max_tokens or 2000},
                }
                res = await client.post(url, json=payload)
                if res.status_code != 200:
                    raise RuntimeError(f"Error {res.status_code} de Gemini: {res.text}")
                data = res.json()
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                usage = data.get("usageMetadata")
                total_tokens = usage.get("totalTokenCount", 0) if usage else 0

            else:
                raise ValueError(f"Proveedor no soportado: {provider}")

        latency = int((time.time() - start_time) * 1000)
        return ChatCompletionResponse(
            provider=provider,
            model=used_model,
            content=content,
            latency_ms=latency,
            usage={"total_tokens": total_tokens},
        )

    async def chat_completion(
        self,
        req: ChatCompletionRequest,
        profile: Optional[str] = None,
    ) -> ChatCompletionResponse:
        """Enruta consultas con failover dinámico entre proveedores activos del Vault."""
        candidates = []

        # 1. Si se solicitó un proveedor específico
        if req.provider:
            candidates.append((req.provider, req.model))

        # 2. Si se solicitó un modelo específico sin proveedor explícito
        elif req.model:
            # Si el modelo tiene formato "vendor/model" (común en OpenRouter), enrutar preferentemente a OpenRouter si está activo
            if "/" in req.model:
                openrouter_entry = vault_service.get_key_entry("openrouter")
                if openrouter_entry and openrouter_entry.get("is_active"):
                    candidates.append(("openrouter", req.model))
                else:
                    custom_entry = vault_service.get_key_entry("custom_llm")
                    if custom_entry and custom_entry.get("is_active") and "openrouter.ai" in (custom_entry.get("base_url") or "").lower():
                        candidates.append(("custom_llm", req.model))

            # Si aún no hay candidato, asociar el modelo a los proveedores LLM activos
            if not candidates:
                all_keys = vault_service.list_keys()
                llm_keys = [k for k in all_keys if k.service_type == "llm" and k.is_active]
                for k in llm_keys:
                    candidates.append((k.provider, req.model or k.model_name))

        # 3. Si se solicita un perfil específico (quick, deep, local)
        elif profile and profile in PROFILE_DEFAULTS:
            for prov, mod in PROFILE_DEFAULTS[profile]:
                entry = vault_service.get_key_entry(prov)
                if entry and entry.get("is_active"):
                    effective_model = entry.get("model_name") or mod
                    candidates.append((prov, effective_model))

        # 4. Fallback: listar todos los proveedores LLM activos
        if not candidates:
            all_keys = vault_service.list_keys()
            llm_keys = [k for k in all_keys if k.service_type == "llm" and k.is_active]
            for k in llm_keys:
                candidates.append((k.provider, req.model or k.model_name))

        if not candidates:
            raise ValueError("No hay proveedores LLM configurados ni activos en el Vault.")

        last_error = None
        attempt_count = 0

        for prov, mod in candidates:
            attempt_count += 1
            try:
                resp = await self._dispatch_single_provider(prov, req, model_override=mod)
                status = "fallback" if attempt_count > 1 else "success"
                tokens = resp.usage.get("total_tokens", 0) if resp.usage else 0
                self._log_request(
                    provider=prov,
                    model=resp.model,
                    service_type="llm",
                    status=status,
                    latency_ms=resp.latency_ms,
                    tokens_used=tokens,
                )
                return resp
            except Exception as e:
                last_error = e
                self._log_request(
                    provider=prov,
                    model=mod or "unknown",
                    service_type="llm",
                    status="error",
                    latency_ms=0,
                    error_message=str(e),
                )
                continue

        raise RuntimeError(f"Todos los proveedores fallaron. Último error: {str(last_error)}")

    async def shodan_host_query(self, ip: str) -> Dict[str, Any]:
        """Consulta información de host en Shodan utilizando la clave del Vault y registra auditoría."""
        api_key = vault_service.get_raw_key("shodan")
        if not api_key:
            raise ValueError("No hay API key activa para Shodan en el Vault.")

        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(f"https://api.shodan.io/shodan/host/{ip}?key={api_key}")
                latency = int((time.time() - start_time) * 1000)
                if res.status_code != 200:
                    self._log_request("shodan", "host", "recon", "error", latency, error_message=res.text)
                    raise RuntimeError(f"Error Shodan ({res.status_code}): {res.text}")

                self._log_request("shodan", "host", "recon", "success", latency)
                return res.json()
        except Exception as e:
            latency = int((time.time() - start_time) * 1000)
            self._log_request("shodan", "host", "recon", "error", latency, error_message=str(e))
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Calcula estadísticas agregadas de telemetría de uso del Proxy."""
        conn = get_db_connection()
        total_requests = conn.execute("SELECT COUNT(*) FROM proxy_audit_log").fetchone()[0]
        successful = conn.execute("SELECT COUNT(*) FROM proxy_audit_log WHERE status IN ('success', 'fallback')").fetchone()[0]
        fallbacks = conn.execute("SELECT COUNT(*) FROM proxy_audit_log WHERE status = 'fallback'").fetchone()[0]
        errors = conn.execute("SELECT COUNT(*) FROM proxy_audit_log WHERE status = 'error'").fetchone()[0]
        total_tokens = conn.execute("SELECT SUM(tokens_used) FROM proxy_audit_log").fetchone()[0] or 0
        avg_latency = conn.execute("SELECT AVG(latency_ms) FROM proxy_audit_log WHERE status != 'error'").fetchone()[0] or 0

        # Por proveedor
        rows = conn.execute(
            """
            SELECT provider, COUNT(*) as count, AVG(latency_ms) as avg_latency
            FROM proxy_audit_log
            GROUP BY provider
            ORDER BY count DESC
            """
        ).fetchall()
        conn.close()

        providers_stats = [
            {"provider": r["provider"], "count": r["count"], "avg_latency": round(r["avg_latency"] or 0, 1)}
            for r in rows
        ]

        return {
            "total_requests": total_requests,
            "successful_requests": successful,
            "fallback_requests": fallbacks,
            "error_requests": errors,
            "success_rate_pct": round((successful / total_requests) * 100, 1) if total_requests > 0 else 100.0,
            "total_tokens_used": total_tokens,
            "avg_latency_ms": round(avg_latency, 1),
            "by_provider": providers_stats,
        }

    def get_audit_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Obtiene las últimas N peticiones registradas por el proxy."""
        conn = get_db_connection()
        rows = conn.execute(
            """
            SELECT id, provider, model, service_type, status, latency_ms, tokens_used, error_message, created_at
            FROM proxy_audit_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


proxy_service = ProxyService()

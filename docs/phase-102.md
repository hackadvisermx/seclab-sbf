# Fase 102: Reclasificación de Proveedor y Fallback de Despacho entre OpenRouter y Custom LLM

## 1. Contexto y Diagnóstico

Al interactuar con el Chat IA Táctico (`ChatView.vue`), el operador recibió el siguiente error upstream:
```
[Error al comunicar con upstream]: Error en comunicación upstream: Todos los proveedores fallaron. Último error: Proveedor 'openrouter' no configurado o sin API key.
```

### Causa Raíz Identificada:
1. En la base de datos SQLite (`api_keys`), la credencial de OpenRouter del operador estaba registrada bajo `provider = 'custom_llm'` con `base_url = 'https://openrouter.ai/api/v1'`, ya que se había configurado originalmente con esa opción antes de la incorporación de OpenRouter nativo.
2. Al ingresar al Chat Táctico (`/chat`), la interfaz seleccionó por defecto `Proveedor: OpenRouter` (`selectedProvider = 'openrouter'`).
3. El endpoint de inferencia recibió `req.provider = 'openrouter'`. Al consultar el Vault mediante `vault_service.get_key_entry('openrouter')`, no existía una fila directa con ese nombre de proveedor, arrojando: `ValueError: Proveedor 'openrouter' no configurado o sin API key`.

---

## 2. Nota sobre solape con la fase 103

Esta fase se desarrolló en paralelo con la fase 103 (`phase/103-openrouter-model-catalog`, en el worktree aislado `/Users/castr/tmp/t01-openrouter`), que atacó una causa raíz muy similar y ya fue mergeada a `bootstrap/baseline` antes de que este trabajo se commiteara. Al combinar ambas ramas se encontró que la fase 103 ya implementaba, de forma independiente, el fallback bidireccional en `vault_service.get_key_entry()` (resuelve `openrouter` a partir de una fila `custom_llm` que apunte a `openrouter.ai`), el refactor de `get_raw_key()` sobre `get_key_entry()`, y los helpers `is_openrouter_url()` / `openrouter_base_url()`. Esa parte del diagnóstico original (puntos A y la mitad de B más abajo) ya estaba resuelta antes de este merge; se mantiene aquí documentada por contexto histórico, no como trabajo nuevo.

El aporte neto de esta fase, una vez reconciliado con la 103, es:

### A. Reclasificación de proveedor en `vault_service.update_key()`
- `ApiKeyUpdate.provider: Optional[str] = None` (nuevo campo en `schemas.py`).
- `update_key(provider, update)` admite mover una clave existente a otro nombre de proveedor (p. ej. `custom_llm` → `openrouter`) sin borrarla y volver a crearla, rechazando la operación con `ValueError` claro si el proveedor destino ya tiene una clave propia.
- **Bug encontrado y corregido durante el merge**: el código original cerraba la conexión SQLite (`conn.close()`) inmediatamente antes de lanzar ese `ValueError`, estando todavía dentro del bloque `with conn:`. Al propagarse la excepción, `__exit__` intentaba hacer `rollback()` sobre una conexión ya cerrada, lanzando `sqlite3.ProgrammingError: Cannot operate on a closed database` y enmascarando el mensaje de error real. Se corrigió moviendo el cierre a un `finally` que envuelve todo el `with conn:`, así la conexión se cierra exactamente una vez sin importar el camino (éxito, `return None` temprano, o `ValueError`).

### B. Fallback de candidatos en `proxy_service.chat_completion()`
- Si se solicita explícitamente `req.provider = 'openrouter'` y existe una clave `custom_llm` activa que apunte a `openrouter.ai`, se añade como candidato de respaldo.
- Si se solicita `req.provider = 'custom_llm'` y existe una clave `openrouter` activa, se añade como candidato de respaldo (este caso es el que realmente necesita el fallback explícito: `get_key_entry('custom_llm')` no tiene resolución inversa propia, solo `get_key_entry('openrouter')` sabe buscar hacia `custom_llm`).
- Si el primer candidato falla al despachar, `chat_completion()` reintenta con el candidato de respaldo antes de reportar "todos los proveedores fallaron".

### C. Migración automática en `database.py` — no implementada
El diagnóstico original proponía una migración automática en `init_db()` para reescribir `provider = 'custom_llm'` a `provider = 'openrouter'` en la base de datos. Esa migración **no llegó a implementarse** (ni en esta rama ni en la 103) y, tras revisar el resultado final, no es necesaria: el fallback en tiempo real de `get_key_entry()` (punto A de la fase 103) ya resuelve la clave correcta en cada lectura sin tener que reescribir datos existentes.

---

## 3. Pruebas y Validación

1. **Backend (`make dashboard-tests`)**: 90 pruebas pasando (2 nuevas en `test_openrouter_proxy.py`: reclasificación de proveedor con caso de colisión, y fallback de `custom_llm` a `openrouter` en el despacho).
2. **Frontend (`npm test`)**: 34 pruebas pasando, 0 fallos.
3. **Regresión completa (`make verify`)**: 118 pruebas pasando.
4. **Escaneo de secretos (`gitleaks`)**: 0 fugas detectadas.

La prueba de reclasificación con colisión (`test_update_key_reclassifies_provider_and_rejects_collision`) falla con `sqlite3.ProgrammingError` contra el código original sin el fix del punto A; se usó precisamente para confirmar el bug antes de corregirlo.

# Fase 72: Empaquetado Seguro, Sanitización y Cierre de Engagements (`pt-eng pack`, `close`, `export`)

## 1. Contexto y Objetivos

Con la creación (`pt-eng new`), validación de alcance (`pt-scope check`), auditoría asistida por agentes (`skills/`, `pt-callback`, `pt-context`) y compilación técnica (`pt-report build`) ya establecidas, esta fase completa el **ciclo de vida de la auditoría ofensiva ética**: la fase final de **empaquetado seguro, sanitización y cierre formal**.

1. **Motor de Empaquetado y Sanitización (`scripts/pt-engagement-packer.py`)**:
   - Binario en Python stdlib instalado como `/usr/local/bin/pt-engagement-packer` con permisos `0555` en [`images/full/Dockerfile`](file:///Users/castr/tmp/t01/images/full/Dockerfile#L741).
   - **Sanitización de Datos Sensibles**:
     - Enmascara tokens JWT (`eyJ...` -> `[REDACTED_JWT]`).
     - Enmascara cabeceras de autorización (`Authorization: Bearer ...` -> `Authorization: Bearer [REDACTED_AUTH_TOKEN]`).
     - Enmascara contraseñas en comandos `curl` (`-u user:pass` -> `-u user:[REDACTED_PASSWORD]`) y URLs (`https://user:pass@...` -> `https://user:[REDACTED_PASSWORD]@...`).
     - Enmascara cookies de sesión sensibles (`PHPSESSID`, `JSESSIONID`, `session=...` -> `[REDACTED_SESSION]`).
     - Enmascara bloques de claves privadas (`BEGIN ... PRIVATE KEY`).
   - **Manifiesto Criptográfico de Integridad (`manifest.sha256`)**:
     - Genera automáticamente un manifiesto con formato estándar `sha256sum` para todos los archivos incluidos en el entregable (`REPORT.md`, `target.yaml`, `scope.txt`, `evidence/*.md`, `recon/live_hosts.txt`, `subdomains.txt`), garantizando no repudio y verificación de integridad.
   - **Compresión Reproducible**:
     - Genera bundles portables `.tar.gz` o `.zip` organizados dentro de una carpeta raíz con el nombre del engagement.

2. **Cierre Formal de Auditoría y Verificación de Limpieza (`pt-eng close`)**:
   - Actualiza de forma atómica y determinista el archivo `target.yaml` marcando:
     - `status: closed`
     - `closed_at: '<ISO-8601-Timestamp>'`
   - Emite la lista de verificación post-engagement (Sección 5 de `REPORT.md`):
     - Detención de receptores de callbacks (`pt-callback stop`).
     - Cierre y sellado del log de auditoría (`pt-log stop`).
     - Notificación para revocación de credenciales temporales y limpieza de artefactos en servidores objetivo.

3. **Integración en Shell Zsh (`shell/pentest-lab/pentest-lab.plugin.zsh`)**:
   - Subcomandos ampliados en `pt-eng`:
     - `pt-eng pack [nombre] [--sanitize] [-o <ruta>] [--format tar.gz|zip]`
     - `pt-eng close [nombre]`
     - `pt-eng export [nombre] [destino]`
   - Aliases ergonómicos añadidos:
     - `alias ptpack="pt-eng pack"`
     - `alias engpack="pt-eng pack"`
     - `alias ptclose="pt-eng close"`
   - Actualización de `_pt-eng-help` y `pt-help`.

---

## 2. Flujo Completo del Ciclo de Vida de Engagements en SecLab-SBF

```mermaid
flowchart LR
    A["1. Inicio<br>pt-eng new acme"] --> B["2. Scope Guard<br>pt-scope check api.acme.com"]
    B --> C["3. Auditoría & Callbacks<br>pt-callback start<br>pt-skills recon-profiling"]
    C --> D["4. Hallazgos Evidence-First<br>pt-finding new idor-users"]
    D --> E["5. Inyección LLM<br>pt-context acme auth"]
    E --> F["6. Compilación de Informe<br>pt-report build acme"]
    F --> G["7. Empaquetado & Sanitización<br>pt-eng pack acme --sanitize"]
    G --> H["8. Cierre de Auditoría<br>pt-eng close acme"]
```

---

## 3. Ejemplos de Uso

### Empaquetar Engagement con Sanitización Automática
```bash
# Empaquetar el engagement acme-corp ofuscando credenciales
pt-eng pack acme-corp --sanitize

# O usando el alias directo
ptpack acme-corp -s -o /workspace/exports/acme_final.tar.gz

# Inspeccionar el manifiesto criptográfico generado
tar -ztvf /workspace/exports/acme_final.tar.gz
```

### Exportar Directamente a una Carpeta Local o Compartida
```bash
pt-eng export acme-corp /workspace/exports
```

### Cerrar Formalmente la Auditoría
```bash
pt-eng close acme-corp
# o mediante alias
ptclose acme-corp
```

---

## 4. Verificaciones y Calidad

1. **Pruebas Unitarias (`scripts/verify/check-python-units.py`)**:
   - `test_engagement_packaging_and_lifecycle_closure`: Valida la sanitización de 5 tipos de credenciales/tokens, la generación del tarball reproducible con `manifest.sha256`, la verificación de hashes SHA-256, el cierre en `target.yaml` y la integración en Dockerfile y plugin Zsh.
   - `test_pentest_lab_plugin_helpers_and_aliases`: Valida helpers (`_pt-packer-script()`) y aliases (`ptpack`, `engpack`, `ptclose`).
   - Total: **61/61 pruebas en verde**.

2. **Suite de Verificación (`make verify`)**:
   - Gitleaks (0 secretos en código).
   - Hadolint (Dockerfiles validados).
   - ShellCheck, Actionlint y comprobación estructural de Makefile en verde.
   - Validación de Compose (`make compose-config`).

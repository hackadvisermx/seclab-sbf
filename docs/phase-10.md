# Fase 10 — CI/CD y operación

## Estado

Completada. La fase cubre la cadena de CI/CD de seguridad, las pruebas de
humo funcionales, la gestión de respaldos e integridad del workspace, el
sistema de alertas operacionales y los procedimientos de recuperación ante
desastres (Disaster Recovery).

## Componentes

- `.github/workflows/security.yml`: workflow de GitHub Actions que ejecuta
  Gitleaks, Trivy en filesystem, Hadolint sobre `base` y `full`, ShellCheck sin
  exclusiones globales, Actionlint, validación de referencias de compose,
  comprobación de comandos documentados, validación de la jail de fail2ban y
  validación de sintaxis/render de los tres stacks Terraform.
- `scripts/verify/smoke-test.sh` y `make smoke-test`: prueba funcional en
  contenedor efímero que valida permisos de `/workspace` para `tester`,
  ejecución limpia de Zsh interactivo con `pt-help`, disponibilidad de runtimes
  (Python, Ruby, Perl), respuesta de herramientas clave y helper de proxy
  `pt-forward`.
- `scripts/host/workspace-backup.sh` y `make workspace-backup`: empaquetado del
  workspace con timestamp y checksum SHA-256 (`.tar.gz` + `.sha256`) hacia
  `./backups/` (ignorado en `.gitignore`).
- `scripts/host/workspace-restore.sh` y `make workspace-restore`: restauración del
  workspace con verificación de integridad del checksum SHA-256 y protección
  frente a sobreescrituras accidentales (`FORCE=1`).
- `scripts/host/notify.sh`: sistema de alertas ligeras por Webhook HTTP (Discord,
  Slack o receptor compatible) ante eventos del sistema (respaldos, bloqueos de
  fail2ban o caídas de conectividad).
- `docs/runbooks.md`: procedimientos por síntoma y runbook formal de
  **Recuperación ante desastres (Disaster Recovery)**.
- `docs/backups.md`: guía paso a paso para respaldos y restauración en local y
  en la nube.

## Decisiones operacionales

1. **El workspace es una carpeta, no un volumen de nube:**
   Desde el 2026-09-29 el workspace vive en una carpeta del disco de arranque
   de la VM (o `./workspace` en local) para evitar facturación de volúmenes con
   la máquina apagada. El respaldo es por tanto disciplina del operador
   mediante `make workspace-backup` o extracción manual por `scp`.

2. **Integridad de respaldos con SHA-256:**
   Cada archivo generado por `workspace-backup` va acompañado de su archivo
   `.sha256`. Al restaurar con `workspace-restore`, el script valida el hash
   antes de descomprimir los datos.

3. **Alertas no intrusivas:**
   `scripts/host/notify.sh` utiliza `ALERT_WEBHOOK_URL`. Si la variable no está
   definida, registra el mensaje en el log local y sale con código 0 sin
   interrumpir procesos ni pipelines.

4. **Disaster Recovery rápido:**
   En caso de pérdida o destrucción de una VM, la reconstrucción no depende de
   snapshots de nube: la infraestructura se levanta en minutos con Terraform o
   Compose local, la imagen se reutiliza o construye nativa, y el workspace se
   restaura desde el último archivo `.tar.gz` verificado.

## Verificación

```bash
# Validaciones estáticas de CI
make verify

# Smoke test funcional del contenedor
make smoke-test

# Prueba de respaldo y checksum
make workspace-backup

# Prueba de alerta local
./scripts/host/notify.sh "Test" "Mensaje de prueba" info
```

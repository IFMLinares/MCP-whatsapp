# WhatsApp Manager MCP 🚀

Este servidor MCP (Model Context Protocol) permite gestionar WhatsApp Web de forma automatizada y eficiente, optimizado para ser utilizado por agentes de IA.

## ✨ Características Principales

- **Velocidad Extrema:** Utiliza un sistema de persistencia de navegador que mantiene la sesión activa, reduciendo los tiempos de respuesta de 30s a menos de 5s tras la primera carga.
- **AdBlock Inteligente:** Bloquea automáticamente imágenes, videos, estilos CSS y fuentes para minimizar el consumo de recursos y acelerar la extracción de texto.
- **Modo Invisible (Headless):** Funciona totalmente en segundo plano sin interrumpir el flujo de trabajo del usuario.
- **Auto-Cierre por Inactividad:** El navegador se cierra automáticamente tras 5 minutos sin uso para liberar memoria RAM.
- **Seguridad por Permisos:** Solo permite interactuar con grupos autorizados explícitamente en el archivo `.env`.

## 🛠️ Requisitos

- Python 3.10+
- Playwright (`playwright install chromium`)
- Una sesión de WhatsApp Web iniciada.

## 🚀 Instalación y Configuración

1. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Configurar el archivo `.env`:**
   Crea un archivo `.env` en la raíz con:
   ```env
   SESSION_PATH=e:/Programs Installed/xampp/htdocs/IA/MCP Notion Ws/whatsapp_session
   GRUPOS_PERMITIDOS=NombreGrupo1,NombreGrupo2
   ```

## 🔌 Herramientas Incluidas

| Herramienta | Descripción |
| :--- | :--- |
| `iniciar_sesion_whatsapp` | Abre una ventana visible para escanear el QR y sincronizar la sesión. |
| `leer_mensajes_whatsapp_v2` | Lee los últimos mensajes de un grupo autorizado. |
| `enviar_mensaje_whatsapp` | Envía un mensaje de texto a un grupo autorizado. |
| `buscar_chats_whatsapp` | Busca chats por nombre para validar el nombre exacto del destinatario. |
| `autorizar_grupo_whatsapp` | Añade dinámicamente nuevos grupos a la lista de permitidos en el `.env`. |

## ⚙️ Funcionamiento Interno

El servidor utiliza el `WhatsAppBrowserManager`, el cual gestiona el ciclo de vida del navegador Chromium a través de Playwright. Implementa un sistema de bloqueos de red (`page.route`) para prevenir la carga de archivos multimedia, asegurando que el agente de IA reciba la información textual de forma inmediata.

import asyncio
import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright

base_path = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(base_path, ".env"))

mcp = FastMCP("WhatsApp-Manager")
SESSION_PATH = os.getenv("SESSION_PATH")

class WhatsAppBrowserManager:
    def __init__(self):
        self.pw = None
        self.context = None
        self.page = None
        self.lock = asyncio.Lock()
        self.timeout_handle = None
        self.inactivity_timeout = 300 # 5 minutos

    async def _close_browser(self):
        async with self.lock:
            if self.context:
                await self.context.close()
            if self.pw:
                await self.pw.stop()
            self.pw = None
            self.context = None
            self.page = None
            print("Navegador cerrado por inactividad.")

    def _reset_timeout(self):
        if self.timeout_handle:
            self.timeout_handle.cancel()
        self.timeout_handle = asyncio.get_event_loop().call_later(
            self.inactivity_timeout, 
            lambda: asyncio.create_task(self._close_browser())
        )

    async def _setup_adblock(self, page):
        """Bloquea recursos innecesarios para mejorar la velocidad."""
        async def block_resources(route):
            if route.request.resource_type in ["image", "stylesheet", "media", "font", "other"]:
                await route.abort()
            else:
                await route.continue_()
        await page.route("**/*", block_resources)

    async def get_page(self):
        async with self.lock:
            self._reset_timeout()
            if self.page and not self.page.is_closed():
                return self.page
            
            if not self.pw:
                self.pw = await async_playwright().start()
            
            self.context = await self.pw.chromium.launch_persistent_context(
                SESSION_PATH,
                headless=True,
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 800}
            )
            
            self.page = await self.context.new_page()
            await self._setup_adblock(self.page)
            
            # Navegación inicial
            await self.page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=60000)
            return self.page

    async def force_close(self):
        """Cierra el navegador inmediatamente (usado para login manual)."""
        await self._close_browser()

browser_manager = WhatsAppBrowserManager()
def obtener_grupos_permitidos():
    """Lee el archivo .env directamente para evitar problemas de caché de variables de entorno."""
    env_path = os.path.join(base_path, ".env")
    grupos = []
    try:
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("GRUPOS_PERMITIDOS="):
                        val = line.split("=", 1)[1].strip()
                        grupos = [g.strip() for g in val.split(",") if g.strip()]
                        break
    except Exception:
        pass
    return grupos

# USER AGENT REAL para que WhatsApp no sospeche
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

@mcp.tool()
async def iniciar_sesion_whatsapp():
    """Abre el navegador con configuración optimizada para guardar la sesión. CIERRA LA INSTANCIA PERSISTENTE SI EXISTE."""
    await browser_manager.force_close()
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            SESSION_PATH,
            headless=False,
            user_agent=USER_AGENT,
            no_viewport=True
        )
        page = await context.new_page()
        await page.goto("https://web.whatsapp.com")
        
        await asyncio.sleep(120) 
        
        await context.close()
        return "Sesión sincronizada. Intenta leer mensajes ahora."

@mcp.tool()
async def leer_mensajes_whatsapp_v2(grupo: str) -> str:
    """Lectura robusta de mensajes con recarga dinámica de permisos."""
    env_path = os.path.join(base_path, ".env")
    linea_detectada = "No se encontró la línea GRUPOS_PERMITIDOS"
    grupos_actualies = []
    
    try:
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("GRUPOS_PERMITIDOS="):
                        linea_detectada = line.strip()
                        val = line.split("=", 1)[1].strip()
                        grupos_actualies = [g.strip() for g in val.split(",") if g.strip()]
                        break
    except Exception as e:
        linea_detectada = f"Error leyendo archivo: {str(e)}"

    if grupo not in grupos_actualies:
        return f"ACCESO DENEGADO: '{grupo}' no en {grupos_actualies}. Línea en .env: '{linea_detectada}'. Ruta: {env_path}"

    page = await browser_manager.get_page()
    
    try:
        # Verificar si estamos en la página correcta
        if "web.whatsapp.com" not in page.url:
            await page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=60000)
        
        # Esperar a que cargue la interfaz principal
        try:
            await page.wait_for_selector('div[contenteditable="true"]', timeout=30000)
        except:
            # Si falla, podría ser que no hay sesión
            if await page.locator('canvas').count() > 0:
                return "ERROR: WhatsApp Web solicita código QR. Usa el comando 'iniciar_sesion_whatsapp'."
            raise

        # Buscar el grupo
        search_box = page.locator('div[contenteditable="true"]').first
        await search_box.click()
        await search_box.fill(grupo)
        await asyncio.sleep(3) # Esperar a que aparezcan los resultados
        await page.keyboard.press("Enter")
        
        # Esperar a que el chat cargue los mensajes
        try:
            await page.wait_for_selector('span.selectable-text.copyable-text', timeout=15000)
        except:
            pass # Continuar si no hay nuevos mensajes

        messages = []
        selectors = [
            'span.selectable-text.copyable-text',
            'div.copyable-text span',
            'div.message-in span.selectable-text',
            'div.message-out span.selectable-text'
        ]
        
        for selector in selectors:
            found = await page.locator(selector).all_text_contents()
            if found:
                messages.extend(found)
                break
        
        if not messages:
            messages = await page.locator('div[role="row"] span').all_text_contents()
            messages = [m for m in messages if len(m) > 10 and ":" not in m]

        # Limpiar y deduplicar manteniendo orden
        seen = set()
        unique_messages = []
        for m in messages:
            clean = m.strip()
            if clean and clean not in seen:
                unique_messages.append(clean)
                seen.add(clean)
        
        return "\n".join(unique_messages[-5:]) if unique_messages else f"No se encontraron mensajes en el grupo '{grupo}'."
        
    except Exception as e:
        return f"Error crítico al leer WhatsApp: {str(e)}"

@mcp.tool()
async def buscar_chats_whatsapp(consulta: str) -> str:
    """Busca chats por nombre y devuelve las coincidencias encontradas."""
    page = await browser_manager.get_page()
    
    try:
        # Verificar si estamos en la página correcta
        if "web.whatsapp.com" not in page.url:
            await page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=60000)

        await page.wait_for_selector('div[contenteditable="true"]', timeout=30000)
        
        # Buscar
        search_box = page.locator('div[contenteditable="true"]').first
        await search_box.click()
        await search_box.fill(consulta)
        await asyncio.sleep(3) # Esperar resultados
        
        # Extraer nombres de chats de los resultados de búsqueda
        chat_elements = await page.locator('div[role="listitem"] span[title]').all()
        nombres = []
        for el in chat_elements:
            title = await el.get_attribute("title")
            if title and title not in nombres:
                nombres.append(title)
        
        if not nombres:
            return f"No se encontraron chats que coincidan con '{consulta}'."
        
        return "Coincidencias encontradas:\n" + "\n".join(f"- {n}" for n in nombres)
        
    except Exception as e:
        return f"Error al buscar chats: {str(e)}"

@mcp.tool()
async def autorizar_grupo_whatsapp(nombre_grupo: str) -> str:
    """Añade un nombre de grupo a la lista de GRUPOS_PERMITIDOS en el archivo .env."""
    env_path = os.path.join(base_path, ".env")
    try:
        lineas = []
        encontrado = False
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lineas = f.readlines()
        
        nuevas_lineas = []
        for line in lineas:
            if line.startswith("GRUPOS_PERMITIDOS="):
                encontrado = True
                val = line.split("=", 1)[1].strip()
                grupos = [g.strip() for g in val.split(",") if g.strip()]
                if nombre_grupo not in grupos:
                    grupos.append(nombre_grupo)
                    nueva_linea = f"GRUPOS_PERMITIDOS={','.join(grupos)}\n"
                    nuevas_lineas.append(nueva_linea)
                else:
                    nuevas_lineas.append(line)
            else:
                nuevas_lineas.append(line)
        
        if not encontrado:
            nuevas_lineas.append(f"\nGRUPOS_PERMITIDOS={nombre_grupo}\n")
            
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(nuevas_lineas)
            
        return f"Grupo '{nombre_grupo}' autorizado correctamente y añadido al .env."
    except Exception as e:
        return f"Error al actualizar el archivo .env: {str(e)}"

@mcp.tool()
async def enviar_mensaje_whatsapp(grupo: str, mensaje: str) -> str:
    """Envía un mensaje a un grupo o chat autorizado. REQUIERE CONFIRMACIÓN PREVIA DEL USUARIO."""
    env_path = os.path.join(base_path, ".env")
    grupos_actuales = []
    
    try:
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("GRUPOS_PERMITIDOS="):
                        val = line.split("=", 1)[1].strip()
                        grupos_actuales = [g.strip() for g in val.split(",") if g.strip()]
                        break
    except Exception as e:
        return f"Error leyendo permisos: {str(e)}"

    if grupo not in grupos_actuales:
        return f"ACCESO DENEGADO: El grupo '{grupo}' no está autorizado en el .env."

    page = await browser_manager.get_page()
    
    try:
        if "web.whatsapp.com" not in page.url:
            await page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=60000)

        await page.wait_for_selector('div[contenteditable="true"]', timeout=30000)
        
        # Buscar el grupo
        search_box = page.locator('div[contenteditable="true"]').first
        await search_box.click()
        await search_box.fill(grupo)
        await asyncio.sleep(3)
        await page.keyboard.press("Enter")
        
        # Esperar a que el chat se abra y localizar el cuadro de texto del mensaje
        await asyncio.sleep(2)
        message_box = page.locator('footer div[contenteditable="true"]').first
        
        if await message_box.count() == 0:
            message_box = page.locator('div[role="textbox"]').last
        
        await message_box.click()
        await message_box.fill(mensaje)
        await asyncio.sleep(1)
        await page.keyboard.press("Enter")
        await asyncio.sleep(2) # Esperar a que se envíe
        
        return f"Mensaje enviado con éxito a '{grupo}'."
        
    except Exception as e:
        return f"Error al enviar el mensaje: {str(e)}"

if __name__ == "__main__":
    mcp.run()

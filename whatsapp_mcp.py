import asyncio
import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright

base_path = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(base_path, ".env"))

mcp = FastMCP("WhatsApp-Manager")
SESSION_PATH = os.getenv("SESSION_PATH")
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
    """Abre el navegador con configuración optimizada para guardar la sesión."""
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

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            SESSION_PATH, 
            headless=True,
            user_agent=USER_AGENT
        )
        page = await context.new_page()
        
        try:
            # Aumentar tiempo de espera de navegación
            await page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=60000)
            
            # Esperar a que cargue la interfaz principal (el cuadro de búsqueda es un buen indicador)
            await page.wait_for_selector('div[contenteditable="true"]', timeout=60000)
            
            # Buscar el grupo
            search_box = page.locator('div[contenteditable="true"]').first
            await search_box.click()
            await search_box.fill(grupo)
            await asyncio.sleep(3) # Esperar a que aparezcan los resultados
            await page.keyboard.press("Enter")
            
            # Esperar a que el chat cargue los mensajes (esperar a que aparezca al menos uno)
            try:
                await page.wait_for_selector('span.selectable-text.copyable-text', timeout=15000)
            except:
                pass # Continuar si no hay nuevos mensajes o demora mucho

            # Selector para mensajes (intentar varios)
            # 1. Spans con data-pre-plain-text (suelen contener el mensaje limpio)
            # 2. El selector estándar
            # 3. Cualquier span dentro de un mensaje
            
            messages = []
            
            # Buscar en elementos con la clase que suele tener el texto
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
                # Intento desesperado: buscar cualquier cosa que parezca un mensaje por estructura
                messages = await page.locator('div[role="row"] span').all_text_contents()
                # Filtrar ruidos cortos o labels de sistema
                messages = [m for m in messages if len(m) > 10 and ":" not in m]

            await context.close()
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
            # Captura de pantalla opcional para depuración si fuera necesario
            # await page.screenshot(path="error_whatsapp.png")
            await context.close()
            return f"Error crítico al leer WhatsApp: {str(e)}"

@mcp.tool()
async def buscar_chats_whatsapp(consulta: str) -> str:
    """Busca chats por nombre y devuelve las coincidencias encontradas."""
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            SESSION_PATH,
            headless=True,
            user_agent=USER_AGENT
        )
        page = await context.new_page()
        
        try:
            await page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_selector('div[contenteditable="true"]', timeout=60000)
            
            # Buscar
            search_box = page.locator('div[contenteditable="true"]').first
            await search_box.click()
            await search_box.fill(consulta)
            await asyncio.sleep(3) # Esperar resultados
            
            # Extraer nombres de chats de los resultados de búsqueda
            # Los nombres suelen estar en spans dentro de elementos con rol='listitem' en el panel lateral
            chat_elements = await page.locator('div[role="listitem"] span[title]').all()
            nombres = []
            for el in chat_elements:
                title = await el.get_attribute("title")
                if title and title not in nombres:
                    nombres.append(title)
            
            await context.close()
            
            if not nombres:
                return f"No se encontraron chats que coincidan con '{consulta}'."
            
            return "Coincidencias encontradas:\n" + "\n".join(f"- {n}" for n in nombres)
            
        except Exception as e:
            await context.close()
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

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            SESSION_PATH,
            headless=True,
            user_agent=USER_AGENT
        )
        page = await context.new_page()
        
        try:
            await page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_selector('div[contenteditable="true"]', timeout=60000)
            
            # Buscar el grupo
            search_box = page.locator('div[contenteditable="true"]').first
            await search_box.click()
            await search_box.fill(grupo)
            await asyncio.sleep(3)
            await page.keyboard.press("Enter")
            
            # Esperar a que el chat se abra y localizar el cuadro de texto del mensaje
            # El cuadro de texto del mensaje suele ser el segundo contenteditable en la página (el primero es la búsqueda)
            # O podemos usar un selector más específico para el pie de página
            await asyncio.sleep(2)
            message_box = page.locator('footer div[contenteditable="true"]').first
            
            if await message_box.count() == 0:
                # Intento alternativo por rol
                message_box = page.locator('div[role="textbox"]').last
            
            await message_box.click()
            await message_box.fill(mensaje)
            await asyncio.sleep(1)
            await page.keyboard.press("Enter")
            await asyncio.sleep(2) # Esperar a que se envíe
            
            await context.close()
            return f"Mensaje enviado con éxito a '{grupo}'."
            
        except Exception as e:
            await context.close()
            return f"Error al enviar el mensaje: {str(e)}"

if __name__ == "__main__":
    mcp.run()

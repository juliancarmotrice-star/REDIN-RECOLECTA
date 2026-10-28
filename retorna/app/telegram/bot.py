"""
RETORNA — Integración del Chatbot con Telegram.

Roles y Control de Acceso:
1. CONDUCTOR (Repartidor):
   - Flujo restringido y enfocado: SOLO puede notificar entregas y recogidas (mediante foto o reporte).
   - No tiene acceso a transacciones globales, saldos, costos ni administración de proveedores.
2. GERENCIA (Supervisión / Administración):
   - Acceso completo a todas las transacciones (/transacciones o /historial).
   - Consulta de saldos por tienda (insensible a mayúsculas y acentos: /saldo tienda general).
   - Consulta de tiendas críticas (/criticas) y resumen general (/resumen).
   - Gestión completa de proveedores (/proveedores, /nuevo_proveedor, /eliminar_proveedor).

Persistencia:
Todos los movimientos se graban directamente en las tablas SQL de Supabase (entregas, recogidas, proveedor).
"""

import json
import logging
import os
import re
import time
from datetime import datetime
import httpx

from app.config import settings
from app.db.supabase_client import db
from app.services.conciliacion import (
    conciliar_tienda,
    conciliar_proveedor,
    resumen_por_tienda,
    tiendas_criticas,
)
from app.services.normalizer import (
    normalizar_texto,
    normalizar_nombre_tienda,
    resolver_tienda,
    coinciden_tiendas,
    es_tienda_o_cliente,
    obtener_info_tienda,
    CATALOGO_CLIENTES_TIENDAS,
)
from app.services.vision import contar_canastas_en_imagen

logger = logging.getLogger("telegram_bot")

ROLES_FILE = os.path.join(os.path.dirname(__file__), "roles.json")


def _cargar_roles() -> dict:
    if os.path.exists(ROLES_FILE):
        try:
            with open(ROLES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error leyendo roles.json: {e}")
    return {}


def _guardar_roles(roles: dict):
    try:
        with open(ROLES_FILE, "w", encoding="utf-8") as f:
            json.dump(roles, f, indent=2)
    except Exception as e:
        logger.warning(f"Error guardando roles.json: {e}")


class TelegramBot:
    ROL_CONDUCTOR = "conductor"
    ROL_GERENCIA = "gerencia"

    def __init__(self, token: str = None):
        self.token = token or settings.telegram_bot_token
        self.api_url = f"https://api.telegram.org/bot{self.token}" if self.token else ""
        self.pending_photos = {}  # chat_id -> {pequenas, grandes, total, descripcion}
        self.roles = _cargar_roles()

    @property
    def is_configured(self) -> bool:
        return bool(self.token and len(self.token) > 10)

    def get_user_role(self, chat_id: int | str) -> str:
        """Retorna 'gerencia' o 'conductor'. Por defecto todo usuario es conductor."""
        cid_str = str(chat_id)
        # 1. Verificar si está en la lista de IDs de administración del .env
        admins = [a.strip() for a in settings.admin_telegram_ids.split(",") if a.strip()]
        if cid_str in admins:
            return self.ROL_GERENCIA
        # 2. Verificar rol persistido
        return self.roles.get(cid_str, self.ROL_CONDUCTOR)

    def set_user_role(self, chat_id: int | str, role: str):
        """Asigna y persiste el rol del usuario."""
        self.roles[str(chat_id)] = role
        _guardar_roles(self.roles)

    def send_message(self, chat_id: int | str, text: str, parse_mode: str = "HTML") -> bool:
        """Envía un mensaje a un chat de Telegram."""
        if not self.is_configured:
            logger.warning("Telegram Bot Token no está configurado.")
            return False

        try:
            url = f"{self.api_url}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
            }
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Error al enviar mensaje a Telegram {chat_id}: {e}")
            return False

    def get_me(self) -> dict | None:
        """Verifica la validez del token y obtiene datos del bot."""
        if not self.is_configured:
            return None
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(f"{self.api_url}/getMe")
                if resp.status_code == 200:
                    return resp.json().get("result")
        except Exception as e:
            logger.error(f"Error en getMe de Telegram: {e}")
        return None

    def process_update(self, update: dict) -> dict:
        """Procesa una actualización recibida de Telegram (vía webhook o polling)."""
        message = update.get("message") or update.get("edited_message")
        if not message:
            return {"status": "ignored", "reason": "no_message"}

        chat_id = message.get("chat", {}).get("id")
        text = (message.get("text") or "").strip()
        sender_name = message.get("from", {}).get("first_name", "Usuario")
        user_role = self.get_user_role(chat_id)

        # 1. Si el usuario envió una fotografía (Conteo automático por IA)
        if message.get("photo"):
            return self._handle_photo(chat_id, message, sender_name, user_role)

        # 2. Si el usuario está respondiendo a una foto previamente contada
        if chat_id in self.pending_photos and text and not text.startswith("/"):
            return self._handle_pending_photo_followup(chat_id, text, sender_name, user_role)

        if not text:
            if user_role == self.ROL_CONDUCTOR:
                self.send_message(
                    chat_id,
                    "👋 Hola. Tómale una <b>foto</b> a las canastas para contarlas y registrar tu entrega o recogida.",
                )
            else:
                self.send_message(
                    chat_id,
                    "👋 Hola. Escribe un comando como <code>/transacciones</code> o <code>/saldo &lt;tienda&gt;</code>.",
                )
            return {"status": "ok", "action": "empty_text"}

        # 3. Comandos estructurados con /
        if text.startswith("/"):
            return self._handle_command(chat_id, text, sender_name, user_role)

        # 4. Mensajes en lenguaje natural
        return self._handle_natural_text(chat_id, text, sender_name, user_role)

    handle_update = process_update

    def _handle_photo(self, chat_id: int | str, message: dict, sender_name: str, user_role: str) -> dict:
        """Descarga la foto de Telegram, cuenta las canastas con Visión IA y procesa el movimiento."""
        photos = message.get("photo", [])
        caption = (message.get("caption") or "").strip()

        if not photos:
            self.send_message(chat_id, "⚠️ No pude procesar la imagen enviada.")
            return {"status": "error", "error": "no_photos"}

        self.send_message(
            chat_id,
            "📸 <i>He recibido la foto. Analizando y contando las canastillas con Inteligencia Artificial...</i>",
        )

        image_bytes = None
        if self.is_configured:
            try:
                best_photo = photos[-1]
                file_id = best_photo.get("file_id")
                with httpx.Client(timeout=15.0) as client:
                    info_resp = client.get(f"{self.api_url}/getFile?file_id={file_id}")
                    info_resp.raise_for_status()
                    file_path = info_resp.json().get("result", {}).get("file_path")
                    if file_path:
                        img_resp = client.get(f"https://api.telegram.org/file/bot{self.token}/{file_path}")
                        img_resp.raise_for_status()
                        image_bytes = img_resp.content
            except Exception as e:
                logger.error(f"Error descargando foto de Telegram: {e}")

        # Fallback sintético si no se descargó imagen real
        if not image_bytes:
            from PIL import Image
            from io import BytesIO
            img_placeholder = Image.new("RGB", (600, 800), color=(40, 60, 100))
            buf = BytesIO()
            img_placeholder.save(buf, format="JPEG")
            image_bytes = buf.getvalue()

        # Análisis visual con IA
        conteo = contar_canastas_en_imagen(image_bytes)
        peq = conteo.get("canastas_pequenas", 0)
        grd = conteo.get("canastas_grandes", 0)
        total = conteo.get("total", peq + grd)
        desc = conteo.get("descripcion", "")

        # Si el conductor envió texto con la foto (caption):
        if caption:
            caption_lower = caption.lower()
            es_entrega = any(w in caption_lower for w in ("entrega", "entregue", "entregué", "descargue", "dejé", "deje"))
            es_recogida = any(w in caption_lower for w in ("recogida", "recogi", "recogí", "cargue", "me traje", "retiro"))

            if es_entrega or es_recogida:
                tipo = "entrega" if es_entrega else "recogida"
                provs = db.listar_transportadores()
                id_prov = provs[0]["id_transportador"] if provs else 1
                prov_match = re.search(r"(?:transportador|transportadora|proveedor)\s*(\d+)", caption_lower)
                if prov_match:
                    id_prov = int(prov_match.group(1))

                tienda = self._extraer_tienda_de_texto(caption)
                res = self._parse_and_save_movement(chat_id, f"{id_prov} {tienda} {peq} {grd}", tipo=tipo)
                return {"status": "ok", "action": "photo_counted_and_saved", "conteo": conteo, "result": res}

        # Si NO había caption, guardamos el estado y preguntamos:
        self.pending_photos[chat_id] = {
            "pequenas": peq,
            "grandes": grd,
            "total": total,
            "descripcion": desc,
        }

        niveles_info = ""
        if conteo.get("desglose_niveles"):
            lines_desglose = []
            for n in conteo["desglose_niveles"]:
                t_ico = "📦 Grande" if n.get("tipo") == "grande" else "🔹 Pequeña"
                pos = f" ({n.get('posicion')})" if n.get("posicion") else ""
                lines_desglose.append(f"  • Nivel {n.get('nivel')}: {t_ico}{pos}")
            niveles_info = "\n\n📋 <b>Inspección nivel por nivel (arriba ⬇ abajo):</b>\n" + "\n".join(lines_desglose)

        msg = (
            f"📸 <b>¡Conteo Visual por IA Completado!</b>\n\n"
            f"🔢 <b>Canastas detectadas en la foto:</b> <b>{total}</b>\n"
            f"• 📦 Grandes: <b>{grd}</b>\n"
            f"• 🔹 Pequeñas: <b>{peq}</b>\n"
            f"ℹ️ <i>{desc}</i>{niveles_info}\n\n"
            f"👉 <b>¿Esta foto corresponde a una Entrega o a una Recogida?</b>\n"
            f"Por favor responde con el tipo y la tienda. Por ejemplo:\n"
            f"• <code>Entrega Exito Calle 80</code>\n"
            f"• <code>Recogida Carulla 140</code>"
        )
        self.send_message(chat_id, msg)
        return {"status": "ok", "action": "photo_pending_confirmation", "conteo": conteo}

    def _handle_pending_photo_followup(self, chat_id: int | str, text: str, sender_name: str, user_role: str) -> dict:
        """El conductor responde indicando si las canastas contadas son Entrega o Recogida y la tienda."""
        data_foto = self.pending_photos.pop(chat_id)
        peq = data_foto["pequenas"]
        grd = data_foto["grandes"]

        lower = text.lower()
        es_recogida = any(w in lower for w in ("recogida", "recogi", "recogí", "cargue", "me traje", "retiro"))
        tipo = "recogida" if es_recogida else "entrega"

        provs = db.listar_transportadores()
        id_prov = provs[0]["id_transportador"] if provs else 1
        prov_match = re.search(r"(?:transportador|transportadora|proveedor)\s*(\d+)", lower)
        if prov_match:
            id_prov = int(prov_match.group(1))

        tienda = self._extraer_tienda_de_texto(text)
        res = self._parse_and_save_movement(chat_id, f"{id_prov} {tienda} {peq} {grd}", tipo=tipo)
        return {"status": "ok", "action": f"photo_{tipo}_confirmed", "data": res}

    def _extraer_tienda_de_texto(self, text: str) -> str:
        """Extrae, normaliza y corrige con fuzzy matching el nombre de la tienda desde un texto libre."""
        entregas = db.listar_entregas()
        recogidas = db.listar_recogidas()
        tiendas_existentes = set(
            e.get("nombre_tienda") for e in (entregas + recogidas) if e.get("nombre_tienda")
        )
        return resolver_tienda(text, tiendas_existentes)

    def _handle_command(self, chat_id: int | str, text: str, sender_name: str, user_role: str) -> dict:
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower().split("@")[0]
        args_str = parts[1].strip() if len(parts) > 1 else ""

        # ─── Comandos de Gestión de Roles ───
        if cmd in ("/gerencia", "/admin"):
            clave_esperada = settings.clave_gerencia or "gerencia2026"
            if args_str == clave_esperada:
                self.set_user_role(chat_id, self.ROL_GERENCIA)
                msg = (
                    f"👔 <b>¡Acceso Autorizado a GERENCIA!</b>\n\n"
                    f"Bienvenido, {sender_name}. Ahora tienes acceso al panel de supervisión de transacciones y saldos.\n\n"
                    "📋 <b>Comandos de Gerencia:</b>\n"
                    "• <code>/transacciones</code> — Historial de todas las entregas y recogidas de conductores\n"
                    "• <code>/saldo &lt;tienda&gt;</code> — Balance y tasa de no retorno (insensible a mayúsculas)\n"
                    "• <code>/criticas</code> — Tiendas con retención alta de canastas\n"
                    "• <code>/resumen</code> — Panorama consolidado de tiendas\n"
                    "• <code>/transportadores</code> — Catálogo maestro de transportadores\n"
                    "• <code>/nuevo_transportador Nombre | Contacto | Tel</code>\n"
                    "• <code>/eliminar_transportador ID</code>\n"
                    "• <code>/modo_conductor</code> — Cambiar a vista de conductor para pruebas"
                )
                self.send_message(chat_id, msg)
                return {"status": "ok", "action": "login_gerencia"}
            else:
                self.send_message(
                    chat_id,
                    "❌ <b>Clave incorrecta.</b>\nUsa: <code>/gerencia &lt;clave&gt;</code>",
                )
                return {"status": "error", "error": "bad_password"}

        elif cmd in ("/conductor", "/modo_conductor"):
            self.set_user_role(chat_id, self.ROL_CONDUCTOR)
            msg = (
                "🚚 <b>Modo Conductor Activado</b>\n\n"
                "Ahora estás en la vista exclusiva para repartidores. Tu función es reportar entregas y recogidas tomando fotos a las canastas."
            )
            self.send_message(chat_id, msg)
            return {"status": "ok", "action": "set_conductor"}

        elif cmd in ("/rol", "/mi_rol"):
            rol_txt = "👔 <b>Gerencia / Supervisión</b>" if user_role == self.ROL_GERENCIA else "🚚 <b>Conductor / Repartidor</b>"
            self.send_message(chat_id, f"Tu rol actual es: {rol_txt}")
            return {"status": "ok", "role": user_role}

        # ─── Comandos de Ayuda (/start, /ayuda) ───
        elif cmd in ("/start", "/help", "/ayuda"):
            if user_role == self.ROL_CONDUCTOR:
                msg = (
                    f"👋 <b>¡Hola, {sender_name}! (Módulo Conductor / Repartidor)</b>\n\n"
                    "📸 <b>Tu función es reportar lo que entregas y lo que recoges:</b>\n\n"
                    "1. <b>Tómale una foto a las canastas.</b>\n"
                    "2. Envíala con el mensaje de entrega o recogida:\n"
                    "   • <i>\"Entrega en Éxito Calle 80\"</i>\n"
                    "   • <i>\"Recogida en Carulla 140\"</i>\n\n"
                    "⚡ <i>El software calcula automáticamente la cantidad de canastillas por ti.</i>\n\n"
                    "📝 <b>Si prefieres escribir los números directamente:</b>\n"
                    "• <code>/entrega ID_PROV TIENDA PEQUEÑAS GRANDES</code>\n"
                    "• <code>/recogida ID_PROV TIENDA PEQUEÑAS GRANDES</code>\n\n"
                    "🔒 <i>Las consultas de saldos y transacciones son de uso exclusivo de Gerencia (/gerencia clave).</i>"
                )
            else:
                msg = (
                    f"👔 <b>Panel de Control de GERENCIA — RETORNA</b>\n\n"
                    "Supervisión en tiempo real de canastas en consignación conectada a Supabase SQL.\n\n"
                    "📋 <b>Comandos disponibles:</b>\n"
                    "• <code>/transacciones</code> — Últimos movimientos de todos los conductores\n"
                    "• <code>/saldo NOMBRE_TIENDA</code> — Balance de tienda (ej: <code>/saldo tienda general</code>)\n"
                    "• <code>/criticas</code> — Tiendas en estado crítico\n"
                    "• <code>/resumen</code> — Resumen de todas las tiendas\n"
                    "• <code>/transportadores</code> — Lista transportadores en SQL\n"
                    "• <code>/nuevo_transportador Nombre | Contacto | Tel</code>\n"
                    "• <code>/eliminar_transportador ID</code>\n"
                    "• <code>/modo_conductor</code> — Cambiar a modo repartidor"
                )
            self.send_message(chat_id, msg)
            return {"status": "ok", "action": "help", "role": user_role}

        # ─── Comandos Operativos (Permitidos para TODOS: Conductor y Gerencia) ───
        elif cmd == "/entrega":
            return self._parse_and_save_movement(chat_id, args_str, tipo="entrega")

        elif cmd == "/recogida":
            return self._parse_and_save_movement(chat_id, args_str, tipo="recogida")

        elif cmd in ("/donde", "/ubicacion", "/cliente", "/tienda"):
            if not args_str:
                self.send_message(
                    chat_id,
                    "📍 <b>Consulta de Ubicación de Clientes/Tiendas:</b>\n"
                    "Uso: <code>/donde NOMBRE_TIENDA</code>\n"
                    "Ejemplo: <code>/donde Exito Calle 80</code> o <code>/donde carulla 140</code>",
                )
                return {"status": "bad_args"}

            entregas = db.listar_entregas()
            recogidas = db.listar_recogidas()
            tiendas_db = set(e.get("nombre_tienda") for e in (entregas + recogidas) if e.get("nombre_tienda"))
            tienda_res = resolver_tienda(args_str, tiendas_db)
            info = obtener_info_tienda(tienda_res)
            saldo = conciliar_tienda(tienda_res)
            s = saldo["saldo"]

            lines = [f"📍 <b>Ficha de Cliente / Punto de Consignación:</b>\n"]
            lines.append(f"• <b>Nombre Oficial:</b> <b>{tienda_res}</b>")
            if info:
                lines.append(f"• <b>Cadena:</b> {info.get('cadena', '-')}")
                lines.append(f"• <b>Tipo de Superficie:</b> {info.get('tipo', '-')}")
                lines.append(f"• <b>Dirección Física:</b> <code>{info.get('direccion', '-')}</code>")
                lines.append(f"• <b>Ciudad / Zona:</b> {info.get('ciudad', 'Bogotá')} ({info.get('zona', '')})")
            else:
                lines.append("• <b>Ubicación:</b> Registrada en base de datos de movimientos.")

            lines.append(f"\n📦 <b>Canastas en consignación:</b>")
            lines.append(f"• Pendientes: <b>{s['total']}</b> (Peq: {s['pequenas']}, Grd: {s['grandes']})")
            lines.append(f"• Tasa de no retorno: {saldo['tasa_no_retorno']*100:.1f}%")

            self.send_message(chat_id, "\n".join(lines))
            return {"status": "ok", "action": "donde_tienda", "tienda": tienda_res, "info": info}

        # ─── Bloqueo de Comandos Gerenciales para Conductores ───
        if user_role == self.ROL_CONDUCTOR:
            if cmd in ("/transacciones", "/historial", "/saldo", "/criticas", "/resumen", "/transportadores", "/proveedores", "/nuevo_transportador", "/nuevo_proveedor", "/eliminar_transportador", "/eliminar_proveedor"):
                msg_bloqueo = (
                    "🔒 <b>Acceso Restringido a Conductor</b>\n\n"
                    "Tu perfil de repartidor está configurado exclusivamente para <b>notificar entregas y recogidas</b> mediante foto o reporte, "
                    "y consultar ubicaciones con <code>/donde [tienda]</code>.\n\n"
                    "Si perteneces al equipo de Gerencia, desbloquea el acceso ingresando tu clave:\n"
                    "<code>/gerencia &lt;clave&gt;</code>"
                )
                self.send_message(chat_id, msg_bloqueo)
                return {"status": "forbidden", "role": user_role, "command": cmd}

        # ─── Comandos Exclusivos de GERENCIA ───
        if cmd in ("/transacciones", "/historial"):
            return self._handle_transacciones_gerencia(chat_id)

        elif cmd == "/saldo":
            if not args_str:
                self.send_message(
                    chat_id,
                    "⚠️ Formato: <code>/saldo NOMBRE_TIENDA</code>\nEjemplo: <code>/saldo tienda general</code> o <code>/saldo Exito Calle 80</code>",
                )
                return {"status": "bad_args"}
            try:
                res = conciliar_tienda(args_str)
                s = res["saldo"]
                pct = res["tasa_no_retorno"] * 100
                info = obtener_info_tienda(res["nombre_tienda"])
                ubicacion_txt = f"\n📍 <i>Dirección: {info['direccion']} ({info['ciudad']})</i>" if info else ""
                msg = (
                    f"📊 <b>Saldo de Canastas: {res['nombre_tienda']}</b>{ubicacion_txt}\n\n"
                    f"• <b>Entregadas totales:</b> {res['entregas']['total']} (Peq: {res['entregas']['pequenas']}, Grd: {res['entregas']['grandes']})\n"
                    f"• <b>Recogidas totales:</b> {res['recogidas']['total']} (Peq: {res['recogidas']['pequenas']}, Grd: {res['recogidas']['grandes']})\n"
                    f"• <b>Saldo pendiente:</b> <b>{s['total']}</b> (Peq: {s['pequenas']}, Grd: {s['grandes']})\n"
                    f"• <b>Tasa de no retorno:</b> {pct:.1f}%"
                )
                self.send_message(chat_id, msg)
                return {"status": "ok", "action": "saldo", "data": res}
            except Exception as e:
                self.send_message(chat_id, f"❌ Error al consultar saldo: {e}")
                return {"status": "error", "error": str(e)}

        elif cmd == "/criticas":
            try:
                criticas = tiendas_criticas()
                if not criticas:
                    self.send_message(chat_id, "✅ No hay tiendas en estado crítico actualmente.")
                    return {"status": "ok", "action": "criticas", "count": 0}

                lines = ["⚠️ <b>Tiendas con Saldo Crítico (Gerencia):</b>\n"]
                for t in criticas:
                    lines.append(
                        f"• <b>{t['nombre_tienda']}:</b> {t['saldo']['total']} pendientes "
                        f"(No retorno: {t['tasa_no_retorno']*100:.1f}%)"
                    )
                self.send_message(chat_id, "\n".join(lines))
                return {"status": "ok", "action": "criticas", "count": len(criticas)}
            except Exception as e:
                self.send_message(chat_id, f"❌ Error al consultar tiendas críticas: {e}")
                return {"status": "error", "error": str(e)}

        elif cmd == "/resumen":
            try:
                resumen = resumen_por_tienda()
                if not resumen:
                    self.send_message(chat_id, "ℹ️ No hay movimientos registrados en ninguna tienda.")
                    return {"status": "ok", "count": 0}

                lines = ["📈 <b>Resumen Consolidado de Tiendas (Gerencia):</b>\n"]
                for r in resumen:
                    lines.append(
                        f"• <b>{r['nombre_tienda']}:</b> Saldo {r['saldo']['total']} (Ent: {r['entregas']['total']}, Rec: {r['recogidas']['total']})"
                    )
                self.send_message(chat_id, "\n".join(lines))
                return {"status": "ok", "action": "resumen", "count": len(resumen)}
            except Exception as e:
                self.send_message(chat_id, f"❌ Error al obtener resumen: {e}")
                return {"status": "error", "error": str(e)}

        elif cmd in ("/transportadores", "/proveedores"):
            try:
                provs = db.listar_transportadores()
                if not provs:
                    self.send_message(chat_id, "ℹ️ No hay transportadores registrados en la base de datos.")
                    return {"status": "ok", "action": "list_transportadores", "count": 0}

                lines = ["🚚 <b>Catálogo de Transportadores (Gerencia):</b>\n"]
                for p in provs:
                    lines.append(
                        f"• <b>ID {p['id_transportador']}:</b> {p.get('nombre_transportador', '')} "
                        f"(Contacto: {p.get('contacto') or 'N/A'}, Tel: {p.get('telefono') or 'N/A'})"
                    )
                self.send_message(chat_id, "\n".join(lines))
                return {"status": "ok", "action": "list_transportadores", "count": len(provs)}
            except Exception as e:
                self.send_message(chat_id, f"❌ Error al consultar transportadores: {e}")
                return {"status": "error", "error": str(e)}

        elif cmd in ("/nuevo_transportador", "/nuevo_proveedor"):
            if not args_str:
                self.send_message(
                    chat_id,
                    "⚠️ Formato: <code>/nuevo_transportador Nombre [| Contacto | Telefono]</code>\n"
                    "Ejemplo: <code>/nuevo_transportador Flota Bimbo Norte | Juan Gomez | 3101234567</code>",
                )
                return {"status": "bad_args"}

            partes_prov = [p.strip() for p in args_str.split("|")]
            nombre = partes_prov[0]
            contacto = partes_prov[1] if len(partes_prov) > 1 else ""
            telefono = partes_prov[2] if len(partes_prov) > 2 else ""

            # Validar que NO sea una tienda/cliente (ej: Éxito Calle 80, Carulla, etc.)
            if es_tienda_o_cliente(nombre):
                tienda_res = resolver_tienda(nombre)
                info = obtener_info_tienda(tienda_res)
                dir_txt = f"\n• <b>Dirección Física:</b> <code>{info['direccion']}</code>" if info else ""
                self.send_message(
                    chat_id,
                    f"⚠️ <b>'{nombre}' NO es un transportador.</b>\n\n"
                    f"Es un <b>Cliente / Tienda (Punto de Consignación)</b>: <b>{tienda_res}</b>.{dir_txt}\n\n"
                    "💡 <b>Diferencia en el sistema:</b>\n"
                    "• <b>Transportadores:</b> Empresas o transportistas que mueven y entregan canastas (ej: <i>Transportes Especializados</i>, <i>Flota Bimbo</i>).\n"
                    "• <b>Clientes / Tiendas:</b> Grandes superficies donde se entregan y recogen las canastas.\n\n"
                    f"Para ver su saldo o dónde está ubicada, usa:\n"
                    f"• <code>/saldo {tienda_res}</code>\n"
                    f"• <code>/donde {tienda_res}</code>",
                )
                return {"status": "rejected_is_client", "nombre": nombre, "tienda_res": tienda_res}

            try:
                nuevo = db.crear_transportador({
                    "nombre_transportador": nombre,
                    "contacto": contacto,
                    "telefono": telefono,
                    "estado": "activo",
                })
                self.send_message(
                    chat_id,
                    f"✅ <b>Transportador creado en Supabase SQL:</b>\n"
                    f"• ID: <code>{nuevo.get('id_transportador')}</code>\n"
                    f"• Nombre: <b>{nuevo.get('nombre_transportador')}</b>\n"
                    f"• Contacto: {nuevo.get('contacto') or '-'}\n"
                    f"• Teléfono: {nuevo.get('telefono') or '-'}",
                )
                return {"status": "ok", "action": "create_transportador", "data": nuevo}
            except Exception as e:
                self.send_message(chat_id, f"❌ Error al crear transportador en SQL: {e}")
                return {"status": "error", "error": str(e)}

        elif cmd in ("/eliminar_transportador", "/eliminar_proveedor"):
            if not args_str.isdigit():
                self.send_message(chat_id, "⚠️ Formato: <code>/eliminar_transportador ID</code>\nEjemplo: <code>/eliminar_transportador 3</code>")
                return {"status": "bad_args"}
            id_prov = int(args_str)
            try:
                db.eliminar_transportador(id_prov)
                self.send_message(chat_id, f"🗑️ <b>Transportador ID {id_prov} eliminado correctamente</b> de Supabase.")
                return {"status": "ok", "action": "delete_transportador", "id": id_prov}
            except Exception as e:
                self.send_message(chat_id, f"❌ Error al eliminar transportador: {e}")
                return {"status": "error", "error": str(e)}

        else:
            self.send_message(
                chat_id,
                f"❓ Comando desconocido <code>{cmd}</code>. Usa /ayuda para ver los comandos de tu perfil.",
            )
            return {"status": "unknown_command"}

    def _handle_transacciones_gerencia(self, chat_id: int | str) -> dict:
        """Muestra a Gerencia las últimas transacciones de entregas y recogidas de todos los conductores."""
        try:
            entregas = db.listar_entregas()
            recogidas = db.listar_recogidas()
            provs_list = db.listar_proveedores()
            provs_map = {p["id_proveedor"]: p.get("nombre_proveedor", f"Prov {p['id_proveedor']}") for p in provs_list}

            movimientos = []
            for e in entregas:
                movimientos.append({
                    "tipo": "ENTREGA",
                    "icono": "📥",
                    "id": e.get("id_entrega"),
                    "fecha": e.get("fecha") or "",
                    "hora": e.get("hora") or "",
                    "tienda": normalizar_nombre_tienda(e.get("nombre_tienda")),
                    "prov": provs_map.get(e.get("id_proveedor"), f"ID {e.get('id_proveedor')}"),
                    "peq": e.get("cantidad_canastas_pequenas", 0) or 0,
                    "grd": e.get("cantidad_canastas_grandes", 0) or 0,
                })

            for r in recogidas:
                movimientos.append({
                    "tipo": "RECOGIDA",
                    "icono": "📤",
                    "id": r.get("id_recogida"),
                    "fecha": r.get("fecha") or "",
                    "hora": r.get("hora") or "",
                    "tienda": normalizar_nombre_tienda(r.get("nombre_tienda")),
                    "prov": provs_map.get(r.get("id_proveedor"), f"ID {r.get('id_proveedor')}"),
                    "peq": r.get("cantidad_canastas_pequenas", 0) or 0,
                    "grd": r.get("cantidad_canastas_grandes", 0) or 0,
                })

            movimientos.sort(key=lambda x: f"{x['fecha']} {x['hora']}", reverse=True)
            ultimos = movimientos[:10]

            if not ultimos:
                self.send_message(chat_id, "ℹ️ No hay transacciones de entregas ni recogidas registradas en SQL.")
                return {"status": "ok", "count": 0}

            lines = ["📋 <b>Historial de Transacciones (Gerencia):</b>\n"]
            for m in ultimos:
                total = m["peq"] + m["grd"]
                lines.append(
                    f"{m['icono']} <b>{m['tipo']} #{m['id']}</b> ({m['fecha']} {m['hora']})\n"
                    f"   • Tienda: <b>{m['tienda']}</b>\n"
                    f"   • Proveedor: {m['prov']}\n"
                    f"   • Total canastas: <b>{total}</b> (Peq: {m['peq']}, Grd: {m['grd']})\n"
                )

            self.send_message(chat_id, "\n".join(lines))
            return {"status": "ok", "action": "transacciones", "count": len(ultimos)}
        except Exception as e:
            self.send_message(chat_id, f"❌ Error al consultar transacciones: {e}")
            return {"status": "error", "error": str(e)}

    def _parse_and_save_movement(self, chat_id: int | str, args_str: str, tipo: str) -> dict:
        """
        Formato flexible: [ID_PROVEEDOR] TIENDA PEQUEÑAS [GRANDES]
        Ejemplos:
          • '2 Exito Calle 80 15 5'
          • 'Exito Calle 80 15 5' (asigna proveedor principal automáticamente)
          • 'extio cll 80 10 5' (fuzzy matching a Éxito Calle 80)
        """
        tokens = args_str.split()
        if not tokens:
            ej = "Exito Calle 80 10 5" if tipo == "entrega" else "Exito Calle 80 8 4"
            self.send_message(
                chat_id,
                f"⚠️ Formato: <code>/{tipo} [ID_PROV] NOMBRE_TIENDA PEQUEÑAS [GRANDES]</code>\n"
                f"Ejemplo: <code>/{tipo} {ej}</code>",
            )
            return {"status": "bad_args"}

        try:
            provs = db.listar_proveedores()
            id_prov_default = provs[0]["id_proveedor"] if provs else 1

            # 1. Determinar si el primer token es un ID numérico de proveedor
            if tokens[0].isdigit() and len(tokens) >= 3:
                id_prov = int(tokens[0])
                resto = tokens[1:]
            else:
                id_prov = id_prov_default
                resto = tokens

            # 2. Extraer cantidades de canastas desde el final de los tokens
            if len(resto) >= 3 and resto[-1].isdigit() and resto[-2].isdigit():
                peq = int(resto[-2])
                grd = int(resto[-1])
                tienda_raw = " ".join(resto[:-2])
            elif len(resto) >= 2 and resto[-1].isdigit():
                peq = int(resto[-1])
                grd = 0
                tienda_raw = " ".join(resto[:-1])
            else:
                peq = 0
                grd = 0
                tienda_raw = " ".join(resto)

            entregas = db.listar_entregas()
            recogidas = db.listar_recogidas()
            tiendas_db = set(e.get("nombre_tienda") for e in (entregas + recogidas) if e.get("nombre_tienda"))
            tienda = resolver_tienda(tienda_raw, tiendas_db)

            ahora = datetime.now()
            data = {
                "id_proveedor": id_prov,
                "nombre_tienda": tienda,
                "fecha": ahora.strftime("%Y-%m-%d"),
                "hora": ahora.strftime("%H:%M:%S"),
                "cantidad_canastas_pequenas": peq,
                "cantidad_canastas_grandes": grd,
            }

            if tipo == "entrega":
                res = db.registrar_entrega(data)
                id_reg = res.get("id_entrega")
                icono = "📥"
                titulo = "Entrega Registrada"
            else:
                res = db.registrar_recogida(data)
                id_reg = res.get("id_recogida")
                icono = "📤"
                titulo = "Recogida Registrada"

            saldo = conciliar_tienda(tienda)
            s = saldo["saldo"]

            msg = (
                f"{icono} <b>¡{titulo} en Supabase SQL!</b>\n\n"
                f"• <b>Registro ID:</b> #{id_reg}\n"
                f"• <b>Proveedor ID:</b> {id_prov}\n"
                f"• <b>Tienda:</b> <b>{tienda}</b>\n"
                f"• <b>Pequeñas:</b> {peq} | <b>Grandes:</b> {grd}\n"
                f"• <b>Fecha y Hora:</b> {data['fecha']} {data['hora']}\n\n"
                f"📊 <b>Saldo actual en tienda:</b> {s['total']} pendientes (Peq: {s['pequenas']}, Grd: {s['grandes']})"
            )
            self.send_message(chat_id, msg)
            return {"status": "ok", "action": tipo, "id": id_reg, "data": res}

        except Exception as e:
            self.send_message(chat_id, f"❌ Error al guardar {tipo} en SQL: {e}")
            return {"status": "error", "error": str(e)}

    def _handle_natural_text(self, chat_id: int | str, text: str, sender_name: str, user_role: str) -> dict:
        """
        Procesa mensajes de texto libre normalizando tildes, abreviaciones y typos:
        - Soporta consultas de ubicación de tiendas ('donde esta exito calle 80').
        - Evita que clientes/tiendas sean confundidos con nuevos proveedores.
        - CONDUCTOR: Reporte de entregas/recogidas por foto o texto.
        - GERENCIA: Consultas de saldo, transacciones y supervisor IA.
        """
        lower = text.lower()
        norm_txt = normalizar_texto(text)

        # 1. Consulta de ubicación de tiendas en catálogo maestro
        if any(w in norm_txt for w in ("donde esta", "donde queda", "ubicacion", "direccion")):
            tienda = self._extraer_tienda_de_texto(text)
            return self._handle_command(chat_id, f"/donde {tienda}", sender_name, user_role)

        # 2. Interceptar si intentan registrar una tienda como proveedor en texto libre
        if any(w in norm_txt for w in ("nuevo proveedor", "crear proveedor", "agregar proveedor", "meter proveedor")):
            tienda = self._extraer_tienda_de_texto(text)
            if es_tienda_o_cliente(tienda) or es_tienda_o_cliente(text):
                return self._handle_command(chat_id, f"/nuevo_proveedor {tienda}", sender_name, user_role)

        # 3. Detección de entrega o recogida
        es_entrega = any(w in lower for w in ("entregué", "entregue", "entrega", "descargué", "descargue", "dejé", "deje"))
        es_recogida = any(w in lower for w in ("recogí", "recogi", "recogida", "cargué", "cargue", "me traje", "retiro"))

        if es_entrega or es_recogida:
            tipo = "entrega" if es_entrega else "recogida"
            provs = db.listar_proveedores()
            id_prov = provs[0]["id_proveedor"] if provs else 1

            prov_match = re.search(r"proveedor\s*(\d+)", lower)
            if prov_match:
                id_prov = int(prov_match.group(1))

            tienda = self._extraer_tienda_de_texto(text)

            # Limpiar el nombre de la tienda del texto para que sus números de dirección (ej: 80, 140)
            # no se confundan con cantidades de canastas
            texto_limpio = text
            for tok in tienda.split():
                if tok.isalnum():
                    texto_limpio = re.sub(rf"\b{re.escape(tok)}\b", " ", texto_limpio, flags=re.IGNORECASE)
            texto_limpio = re.sub(r"\b(calle|cll|clle|carrera|cra|kr|avenida|av|diag|transv)\b", " ", texto_limpio, flags=re.IGNORECASE)

            numeros = [int(n) for n in re.findall(r"\b\d+\b", texto_limpio)]

            peq = 0
            grd = 0
            if numeros:
                if "pequeña" in lower or "pequena" in lower:
                    peq = numeros[0]
                    if len(numeros) > 1 and ("grande" in lower):
                        grd = numeros[1]
                elif "grande" in lower:
                    grd = numeros[0]
                    if len(numeros) > 1 and ("pequeña" in lower or "pequena" in lower):
                        peq = numeros[1]
                else:
                    peq = numeros[0]

            return self._parse_and_save_movement(chat_id, f"{id_prov} {tienda} {peq} {grd}", tipo=tipo)

        # Si es CONDUCTOR y no es entrega/recogida:
        if user_role == self.ROL_CONDUCTOR:
            if any(w in lower for w in ("saldo", "cuantas", "cuántas", "critica", "criticas", "transaccion", "transacciones", "historial")):
                msg = (
                    "🔒 <b>Acceso Restringido (Perfil de Conductor)</b>\n\n"
                    "Como repartidor solo puedes notificar entregas y recogidas (enviando una foto de las canastas o escribiendo tu reporte).\n\n"
                    "Las consultas de saldo y transacciones son de uso exclusivo de Gerencia (<code>/gerencia clave</code>)."
                )
                self.send_message(chat_id, msg)
                return {"status": "forbidden", "role": user_role}

            self.send_message(
                chat_id,
                f"👋 Hola, {sender_name}.\n"
                "Para reportar tus canastas, simplemente <b>tómale una foto a la pila de canastas</b> y envíala, o escribe:\n"
                "• <code>Entrega en [Nombre Tienda]</code>\n"
                "• <code>Recogida en [Nombre Tienda]</code>",
            )
            return {"status": "ok", "action": "conductor_help_sent"}

        # Si es GERENCIA: consulta de saldo normalizada
        if "saldo" in lower or "cuantas canastas" in lower or "cuántas canastas" in lower:
            tienda = self._extraer_tienda_de_texto(text)
            return self._handle_command(chat_id, f"/saldo {tienda}", sender_name, user_role)

        # Si Anthropic está configurado y el usuario es GERENCIA, delegamos a Claude
        if settings.anthropic_api_key and user_role == self.ROL_GERENCIA:
            try:
                from app.agent.core import run_agent
                messages = [
                    {
                        "role": "user",
                        "content": f"Mensaje de Telegram de Gerencia ({sender_name}):\n{text}",
                    }
                ]
                agent_res = run_agent(messages)
                resp_text = agent_res.get("response", "Sin respuesta del agente.")
                self.send_message(chat_id, f"🤖 {resp_text}")
                return {"status": "ok", "action": "ai_agent", "response": resp_text}
            except Exception as e:
                logger.error(f"Error en agente IA para Gerencia: {e}")

        # Mensaje por defecto para Gerencia
        self.send_message(
            chat_id,
            f"👔 <b>Panel de Gerencia:</b> He recibido tu mensaje: <i>\"{text}\"</i>\n\n"
            "Comandos disponibles:\n"
            "• <code>/transacciones</code> — Ver entregas y recogidas de conductores\n"
            "• <code>/saldo &lt;tienda&gt;</code> — Consultar balance\n"
            "• <code>/criticas</code> — Tiendas críticas\n"
            "• <code>/resumen</code> — Resumen de tiendas",
        )
        return {"status": "ok", "action": "gerencia_default_sent"}

    def poll_forever(self, interval: float = 2.0):
        """Bucle de polling para ejecutar el bot localmente."""
        if not self.is_configured:
            print("❌ TELEGRAM_BOT_TOKEN no configurado en .env")
            return

        print(f"🤖 RETORNA Bot activo en Telegram (Token: {self.token[:8]}...)...")
        last_offset = 0

        try:
            with httpx.Client(timeout=10.0) as client:
                client.post(f"{self.api_url}/deleteWebhook")
        except Exception:
            pass

        while True:
            try:
                url = f"{self.api_url}/getUpdates"
                params = {"offset": last_offset + 1, "timeout": 20}
                with httpx.Client(timeout=25.0) as client:
                    resp = client.get(url, params=params)
                    if resp.status_code == 200:
                        updates = resp.json().get("result", [])
                        for update in updates:
                            last_offset = max(last_offset, update.get("update_id", 0))
                            print(f"📩 Actualización Telegram #{last_offset}")
                            self.process_update(update)
            except Exception as e:
                logger.error(f"Error en polling de Telegram: {e}")
                time.sleep(interval)


telegram_bot = TelegramBot()

if __name__ == "__main__":
    telegram_bot.poll_forever()

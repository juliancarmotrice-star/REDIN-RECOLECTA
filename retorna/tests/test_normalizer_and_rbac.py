"""
RETORNA — Pruebas unitarias de Normalización de Nombres y RBAC del Bot.
"""

from app.services.normalizer import normalizar_texto, normalizar_nombre_tienda, coinciden_tiendas
from app.telegram.bot import telegram_bot


class TestNormalizer:
    def test_normalizar_texto_basico(self):
        assert normalizar_texto("  TIENDA   GENERAL  ") == "tienda general"
        assert normalizar_texto("Éxito Calle 80") == "exito calle 80"
        assert normalizar_texto("OLÍMPICA") == "olimpica"

    def test_tiendas_coinciden(self):
        assert coinciden_tiendas("tienda general", "Tienda General")
        assert coinciden_tiendas("ÉXITO CALLE 80", "exito calle 80")
        assert coinciden_tiendas("Olímpica", "olimpica")
        assert not coinciden_tiendas("Carulla", "Exito")

    def test_normalizar_nombre_tienda(self):
        assert normalizar_nombre_tienda("tienda general") == "Tienda General"
        assert normalizar_nombre_tienda("TIENDA GENERAL") == "Tienda General"
        assert normalizar_nombre_tienda("") == "Tienda General"


class TestBotRBAC:
    def test_rol_por_defecto_es_conductor(self):
        # Un usuario nuevo siempre empieza como conductor
        chat_id = 99999999
        rol = telegram_bot.get_user_role(chat_id)
        assert rol == telegram_bot.ROL_CONDUCTOR

    def test_conductor_no_puede_consultar_saldos(self):
        chat_id = 99999998
        telegram_bot.set_user_role(chat_id, telegram_bot.ROL_CONDUCTOR)
        # Intenta ejecutar un comando de gerencia
        res = telegram_bot.handle_update({
            "message": {
                "chat": {"id": chat_id},
                "from": {"first_name": "Pedro Conductor"},
                "text": "/saldo",
            }
        })
        assert res.get("status") == "forbidden"

    def test_gerencia_con_clave_autorizada(self):
        chat_id = 99999997
        res = telegram_bot.handle_update({
            "message": {
                "chat": {"id": chat_id},
                "from": {"first_name": "Laura Gerente"},
                "text": "/gerencia gerencia2026",
            }
        })
        assert res.get("status") == "ok"
        assert telegram_bot.get_user_role(chat_id) == telegram_bot.ROL_GERENCIA

    def test_conductor_extraccion_tienda_flexible(self):
        # Probar extracción de tienda sin importar mayúsculas
        t1 = telegram_bot._extraer_tienda_de_texto("entrega en tienda general 10 5")
        assert "Tienda General" in t1 or "tienda general" in t1.lower()


class TestFuzzyAndCatalog:
    def test_correccion_typos_y_abreviaturas(self):
        from app.services.normalizer import resolver_tienda, es_tienda_o_cliente, obtener_info_tienda
        # Typo y abreviatura cll 80 -> Exito Calle 80
        assert resolver_tienda("extio cll 80") == "Exito Calle 80"
        assert resolver_tienda("exito 80") == "Exito Calle 80"
        assert resolver_tienda("Éxito Calle 80") == "Exito Calle 80"
        assert resolver_tienda("carula 140") == "Carulla 140"
        assert resolver_tienda("olimpca 68") == "Olímpica Calle 68"
        assert resolver_tienda("jumbo suba") == "Jumbo Suba"

    def test_distincion_cliente_vs_proveedor(self):
        from app.services.normalizer import es_tienda_o_cliente
        # Clientes / Tiendas
        assert es_tienda_o_cliente("Éxito Calle 80") is True
        assert es_tienda_o_cliente("extio 80") is True
        assert es_tienda_o_cliente("carulla 140") is True
        # Proveedores reales (NO son tiendas)
        assert es_tienda_o_cliente("Avícola Santa Anita S.A.S.") is False
        assert es_tienda_o_cliente("Nutresa") is False
        assert es_tienda_o_cliente("Huevos Oro") is False

    def test_obtener_ubicacion_tienda(self):
        from app.services.normalizer import obtener_info_tienda
        info = obtener_info_tienda("extio cll 80")
        assert info is not None
        assert "Calle 80" in info["direccion"]
        assert info["ciudad"] == "Bogotá, D.C."

    def test_rechazo_tienda_como_nuevo_proveedor(self):
        # Gerencia intenta registrar 'Éxito Calle 80' como nuevo proveedor por error
        chat_id = 99999996
        telegram_bot.set_user_role(chat_id, telegram_bot.ROL_GERENCIA)
        res = telegram_bot.handle_update({
            "message": {
                "chat": {"id": chat_id},
                "from": {"first_name": "Gerente"},
                "text": "/nuevo_proveedor Éxito Calle 80 | Contacto | 123",
            }
        })
        assert res.get("status") == "rejected_is_client"
        assert res.get("tienda_res") == "Exito Calle 80"

    def test_rechazo_tienda_como_nuevo_transportador(self):
        # Gerencia intenta registrar 'Éxito Calle 80' como nuevo transportador por error
        chat_id = 99999994
        telegram_bot.set_user_role(chat_id, telegram_bot.ROL_GERENCIA)
        res = telegram_bot.handle_update({
            "message": {
                "chat": {"id": chat_id},
                "from": {"first_name": "Gerente"},
                "text": "/nuevo_transportador Éxito Calle 80 | Flota Logística | 3105550000",
            }
        })
        assert res.get("status") == "rejected_is_client"
        assert res.get("tienda_res") == "Exito Calle 80"

    def test_consulta_donde_tienda(self):
        # Conductor pregunta dónde queda una tienda con typo
        chat_id = 99999995
        res = telegram_bot.handle_update({
            "message": {
                "chat": {"id": chat_id},
                "from": {"first_name": "Conductor"},
                "text": "/donde extio cll 80",
            }
        })
        assert res.get("status") == "ok"
        assert res.get("action") == "donde_tienda"
        assert res.get("tienda") == "Exito Calle 80"


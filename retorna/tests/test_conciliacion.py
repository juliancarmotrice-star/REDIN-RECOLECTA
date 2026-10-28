"""
RETORNA — Tests unitarios del servicio de conciliación y visión.
"""

from io import BytesIO
from PIL import Image

from app.services.conciliacion import conciliar_tienda, conciliar_transportador, conciliar_proveedor, tiendas_criticas
from app.services.vision import contar_canastas_en_imagen, optimizar_imagen


class TestConciliacion:
    def test_conciliar_tienda_estructura(self):
        """Verifica que conciliar_tienda retorne la estructura esperada."""
        res = conciliar_tienda("Exito Calle 80")
        assert "nombre_tienda" in res
        assert "entregas" in res
        assert "recogidas" in res
        assert "saldo" in res
        assert "total" in res["saldo"]
        assert "tasa_no_retorno" in res

    def test_conciliar_transportador_estructura(self):
        """Verifica que conciliar_transportador retorne los saldos y tasas."""
        res = conciliar_transportador(2)
        assert "id_transportador" in res
        assert "nombre_transportador" in res
        assert "saldo_canastas" in res
        assert "tasa_no_retorno" in res

    def test_conciliar_proveedor_compatibilidad(self):
        """Verifica compatibilidad de conciliar_proveedor hacia atrás."""
        res = conciliar_proveedor(2)
        assert "id_proveedor" in res
        assert "nombre_proveedor" in res
        assert "saldo_canastas" in res
        assert "tasa_no_retorno" in res


class TestVision:
    def test_contar_canastas_imagen_sintetica(self):
        """Verifica que el servicio de visión procese imágenes y devuelva conteos válidos."""
        img = Image.new("RGB", (500, 800), color=(50, 100, 150))
        buf = BytesIO()
        img.save(buf, format="JPEG")
        image_bytes = buf.getvalue()

        res = contar_canastas_en_imagen(image_bytes)
        assert "total" in res
        assert res["total"] > 0
        assert "canastas_pequenas" in res
        assert "canastas_grandes" in res
        assert "confianza" in res
        assert res["canastas_pequenas"] + res["canastas_grandes"] == res["total"]

    def test_optimizar_imagen(self):
        """Verifica que el optimizador reduzca imágenes gigantes manteniendo el formato."""
        big_img = Image.new("RGB", (2500, 2500), color=(100, 100, 100))
        buf = BytesIO()
        big_img.save(buf, format="JPEG")

        opt_bytes, mime = optimizar_imagen(buf.getvalue(), max_size=1000)
        opt_img = Image.open(BytesIO(opt_bytes))
        assert max(opt_img.size) <= 1000
        assert mime == "image/jpeg"

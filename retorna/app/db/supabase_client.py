"""
RETORNA — Cliente REST para Supabase.

Wrapper liviano sobre httpx para las 4 tablas del piloto:
proveedor, canasta, entregas, recogidas.
"""

import httpx
from app.config import settings


class SupabaseClient:
    """Cliente HTTP para la API REST de Supabase (PostgREST)."""

    def __init__(self):
        self.base_url = f"{settings.supabase_url}/rest/v1"
        self.headers = {
            "apikey": settings.supabase_key,
            "Authorization": f"Bearer {settings.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _url(self, table: str) -> str:
        return f"{self.base_url}/{table}"

    # ─── Operaciones genéricas ───

    def select(self, table: str, params: dict = None) -> list[dict]:
        """SELECT * FROM table con filtros opcionales."""
        with httpx.Client() as client:
            resp = client.get(self._url(table), headers=self.headers, params=params or {})
            resp.raise_for_status()
            return resp.json()

    def select_one(self, table: str, pk_column: str, pk_value) -> dict | None:
        """SELECT un registro por su PK."""
        params = {pk_column: f"eq.{pk_value}"}
        rows = self.select(table, params)
        return rows[0] if rows else None

    def insert(self, table: str, data: dict) -> dict:
        """INSERT INTO table."""
        with httpx.Client() as client:
            resp = client.post(self._url(table), headers=self.headers, json=data)
            resp.raise_for_status()
            result = resp.json()
            return result[0] if isinstance(result, list) else result

    def update(self, table: str, pk_column: str, pk_value, data: dict) -> dict:
        """UPDATE table SET ... WHERE pk = value."""
        headers = {**self.headers}
        params = {pk_column: f"eq.{pk_value}"}
        with httpx.Client() as client:
            resp = client.patch(self._url(table), headers=headers, params=params, json=data)
            resp.raise_for_status()
            result = resp.json()
            return result[0] if isinstance(result, list) and result else {}

    def delete(self, table: str, pk_column: str, pk_value) -> bool:
        """DELETE FROM table WHERE pk = value."""
        params = {pk_column: f"eq.{pk_value}"}
        with httpx.Client() as client:
            resp = client.delete(self._url(table), headers=self.headers, params=params)
            resp.raise_for_status()
            return True

    def count(self, table: str, params: dict = None) -> int:
        """Cuenta registros."""
        headers = {**self.headers, "Prefer": "count=exact"}
        with httpx.Client() as client:
            resp = client.get(
                self._url(table), headers=headers,
                params={**(params or {}), "select": "*"}
            )
            resp.raise_for_status()
            # El count viene en el header Content-Range
            content_range = resp.headers.get("content-range", "")
            if "/" in content_range:
                return int(content_range.split("/")[1])
            return len(resp.json())

    # ─── Transportadores / Proveedores (Mapeo transparente con tabla Supabase) ───

    _transp_table_meta = None

    def _get_transp_meta(self) -> tuple[str, str, str]:
        """Detecta dinámicamente si existe la tabla 'transportador' o si se usa 'proveedor'."""
        if self._transp_table_meta:
            return self._transp_table_meta
        try:
            with httpx.Client() as client:
                resp = client.get(self._url("transportador"), headers=self.headers, params={"limit": 1})
                if resp.status_code == 200:
                    self._transp_table_meta = ("transportador", "id_transportador", "nombre_transportador")
                    return self._transp_table_meta
        except Exception:
            pass
        self._transp_table_meta = ("proveedor", "id_proveedor", "nombre_proveedor")
        return self._transp_table_meta

    def _enrich_transportador(self, row: dict | None) -> dict | None:
        if not row or not isinstance(row, dict):
            return row
        row = dict(row)
        t_id = row.get("id_transportador") or row.get("id_proveedor")
        t_nom = row.get("nombre_transportador") or row.get("nombre_proveedor")
        row["id_transportador"] = t_id
        row["id_proveedor"] = t_id
        row["nombre_transportador"] = t_nom
        row["nombre_proveedor"] = t_nom
        return row

    def listar_transportadores(self) -> list[dict]:
        table, pk, _ = self._get_transp_meta()
        rows = self.select(table, {"order": f"{pk}.asc"})
        return [self._enrich_transportador(r) for r in rows]

    def listar_proveedores(self) -> list[dict]:
        return self.listar_transportadores()

    def obtener_transportador(self, id_transportador: int) -> dict | None:
        table, pk, _ = self._get_transp_meta()
        row = self.select_one(table, pk, id_transportador)
        return self._enrich_transportador(row)

    def obtener_proveedor(self, id_proveedor: int) -> dict | None:
        return self.obtener_transportador(id_proveedor)

    def crear_transportador(self, data: dict) -> dict:
        table, pk, name_col = self._get_transp_meta()
        d = dict(data)
        nom = d.get("nombre_transportador") or d.get("nombre_proveedor")
        if table == "transportador":
            d["nombre_transportador"] = nom
            d.pop("nombre_proveedor", None)
            d.pop("id_proveedor", None)
        else:
            d["nombre_proveedor"] = nom
            d.pop("nombre_transportador", None)
            d.pop("id_transportador", None)
        res = self.insert(table, d)
        return self._enrich_transportador(res)

    def crear_proveedor(self, data: dict) -> dict:
        return self.crear_transportador(data)

    def actualizar_transportador(self, id_transportador: int, data: dict) -> dict:
        table, pk, name_col = self._get_transp_meta()
        d = dict(data)
        nom = d.get("nombre_transportador") or d.get("nombre_proveedor")
        if nom:
            if table == "transportador":
                d["nombre_transportador"] = nom
                d.pop("nombre_proveedor", None)
            else:
                d["nombre_proveedor"] = nom
                d.pop("nombre_transportador", None)
        d.pop("id_transportador", None)
        d.pop("id_proveedor", None)
        res = self.update(table, pk, id_transportador, d)
        return self._enrich_transportador(res)

    def actualizar_proveedor(self, id_proveedor: int, data: dict) -> dict:
        return self.actualizar_transportador(id_proveedor, data)

    def eliminar_transportador(self, id_transportador: int, cascade: bool = False) -> bool:
        table, pk, _ = self._get_transp_meta()
        if cascade:
            try:
                self.delete("entregas", "id_proveedor", id_transportador)
                self.delete("recogidas", "id_proveedor", id_transportador)
            except Exception:
                pass
            try:
                self.delete("entregas", "id_transportador", id_transportador)
                self.delete("recogidas", "id_transportador", id_transportador)
            except Exception:
                pass
        return self.delete(table, pk, id_transportador)

    def eliminar_proveedor(self, id_proveedor: int, cascade: bool = False) -> bool:
        return self.eliminar_transportador(id_proveedor, cascade=cascade)

    # ─── Canastas ───

    def listar_canastas(self, params: dict = None) -> list[dict]:
        return self.select("canasta", params)

    def crear_canasta(self, data: dict) -> dict:
        return self.insert("canasta", data)

    # ─── Entregas ───

    def listar_entregas(self, params: dict = None) -> list[dict]:
        return self.select("entregas", {**(params or {}), "order": "fecha.desc"})

    def registrar_entrega(self, data: dict) -> dict:
        from app.services.normalizer import normalizar_nombre_tienda
        d = dict(data)
        if "nombre_tienda" in d and d["nombre_tienda"]:
            d["nombre_tienda"] = normalizar_nombre_tienda(d["nombre_tienda"])
        if "id_transportador" in d and "id_proveedor" not in d:
            d["id_proveedor"] = d["id_transportador"]
        return self.insert("entregas", d)

    def entregas_por_transportador(self, id_transportador: int) -> list[dict]:
        return self.select("entregas", {
            "id_proveedor": f"eq.{id_transportador}",
            "order": "fecha.desc",
        })

    def entregas_por_proveedor(self, id_proveedor: int) -> list[dict]:
        return self.entregas_por_transportador(id_proveedor)

    def entregas_por_tienda(self, nombre_tienda: str) -> list[dict]:
        clean = (nombre_tienda or "").strip()
        return self.select("entregas", {
            "nombre_tienda": f"ilike.{clean}",
            "order": "fecha.desc",
        })

    # ─── Recogidas ───

    def listar_recogidas(self, params: dict = None) -> list[dict]:
        return self.select("recogidas", {**(params or {}), "order": "fecha.desc"})

    def registrar_recogida(self, data: dict) -> dict:
        from app.services.normalizer import normalizar_nombre_tienda
        d = dict(data)
        if "nombre_tienda" in d and d["nombre_tienda"]:
            d["nombre_tienda"] = normalizar_nombre_tienda(d["nombre_tienda"])
        if "id_transportador" in d and "id_proveedor" not in d:
            d["id_proveedor"] = d["id_transportador"]
        return self.insert("recogidas", d)

    def recogidas_por_transportador(self, id_transportador: int) -> list[dict]:
        return self.select("recogidas", {
            "id_proveedor": f"eq.{id_transportador}",
            "order": "fecha.desc",
        })

    def recogidas_por_proveedor(self, id_proveedor: int) -> list[dict]:
        return self.recogidas_por_transportador(id_proveedor)

    def recogidas_por_tienda(self, nombre_tienda: str) -> list[dict]:
        clean = (nombre_tienda or "").strip()
        return self.select("recogidas", {
            "nombre_tienda": f"ilike.{clean}",
            "order": "fecha.desc",
        })


# Instancia global
db = SupabaseClient()


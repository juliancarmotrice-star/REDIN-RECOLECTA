"""
RETORNA — Implementacion de cada herramienta del agente.

Cada handler usa el cliente de Supabase para leer/escribir
en las tablas: proveedor, canasta, entregas, recogidas.
"""

from datetime import date, datetime
from app.db.supabase_client import db
from app.services.conciliacion import (
    conciliar_tienda,
    conciliar_transportador,
    conciliar_proveedor,
    resumen_por_tienda,
    resumen_por_transportador,
    resumen_por_proveedor,
    tiendas_criticas,
)


def handle_listar_transportadores(**kwargs) -> dict:
    """Lista todos los transportadores."""
    transportadores = db.listar_transportadores()
    items = [
        {
            "id": t["id_transportador"],
            "id_transportador": t["id_transportador"],
            "id_proveedor": t["id_transportador"],
            "nombre": t.get("nombre_transportador", ""),
            "nombre_transportador": t.get("nombre_transportador", ""),
            "nombre_proveedor": t.get("nombre_transportador", ""),
            "contacto": t.get("contacto", ""),
            "telefono": t.get("telefono", ""),
            "estado": t.get("estado", ""),
        }
        for t in transportadores
    ]
    return {
        "total": len(transportadores),
        "transportadores": items,
        "proveedores": items,
    }


handle_listar_proveedores = handle_listar_transportadores


def handle_consultar_saldo_tienda(nombre_tienda: str, **kwargs) -> dict:
    """Consulta saldo de canastas en una tienda."""
    return conciliar_tienda(nombre_tienda)


def handle_consultar_saldo_transportador(id_transportador: int = None, id_proveedor: int = None, **kwargs) -> dict:
    """Consulta resumen de un transportador."""
    _id = id_transportador or id_proveedor or 1
    return conciliar_transportador(_id)


handle_consultar_saldo_proveedor = handle_consultar_saldo_transportador


def handle_registrar_entrega(
    id_transportador: int = None,
    id_proveedor: int = None,
    nombre_tienda: str = "",
    cantidad_canastas_pequenas: int = 0,
    cantidad_canastas_grandes: int = 0,
    **kwargs,
) -> dict:
    """Registra una entrega de canastas."""
    ahora = datetime.now()
    _id = id_transportador or id_proveedor or 1
    data = {
        "id_proveedor": _id,
        "id_transportador": _id,
        "nombre_tienda": nombre_tienda,
        "fecha": ahora.strftime("%Y-%m-%d"),
        "hora": ahora.strftime("%H:%M:%S"),
        "cantidad_canastas_pequenas": cantidad_canastas_pequenas,
        "cantidad_canastas_grandes": cantidad_canastas_grandes,
    }
    resultado = db.registrar_entrega(data)

    # Recalcular saldo
    saldo = conciliar_tienda(nombre_tienda)

    return {
        "registrado": True,
        "tipo": "entrega",
        "id_entrega": resultado.get("id_entrega"),
        "tienda": nombre_tienda,
        "canastas_pequenas": cantidad_canastas_pequenas,
        "canastas_grandes": cantidad_canastas_grandes,
        "saldo_actual": saldo["saldo"],
    }


def handle_registrar_recogida(
    id_transportador: int = None,
    id_proveedor: int = None,
    nombre_tienda: str = "",
    cantidad_canastas_pequenas: int = 0,
    cantidad_canastas_grandes: int = 0,
    **kwargs,
) -> dict:
    """Registra una recogida de canastas."""
    ahora = datetime.now()
    _id = id_transportador or id_proveedor or 1
    data = {
        "id_proveedor": _id,
        "id_transportador": _id,
        "nombre_tienda": nombre_tienda,
        "fecha": ahora.strftime("%Y-%m-%d"),
        "hora": ahora.strftime("%H:%M:%S"),
        "cantidad_canastas_pequenas": cantidad_canastas_pequenas,
        "cantidad_canastas_grandes": cantidad_canastas_grandes,
    }
    resultado = db.registrar_recogida(data)

    # Recalcular saldo
    saldo = conciliar_tienda(nombre_tienda)

    return {
        "registrado": True,
        "tipo": "recogida",
        "id_recogida": resultado.get("id_recogida"),
        "tienda": nombre_tienda,
        "canastas_pequenas": cantidad_canastas_pequenas,
        "canastas_grandes": cantidad_canastas_grandes,
        "saldo_actual": saldo["saldo"],
    }


def handle_ver_resumen_general(**kwargs) -> dict:
    """Resumen general por tienda y por transportador."""
    res_t = resumen_por_transportador()
    return {
        "por_tienda": resumen_por_tienda(),
        "por_transportador": res_t,
        "por_proveedor": res_t,
    }


def handle_ver_tiendas_criticas(**kwargs) -> dict:
    """Tiendas con problemas."""
    criticas = tiendas_criticas()
    return {
        "total_criticas": len(criticas),
        "tiendas": criticas,
    }


def handle_crear_transportador(
    nombre_transportador: str = "",
    nombre_proveedor: str = "",
    contacto: str = "",
    telefono: str = "",
    correo: str = "",
    direccion: str = "",
    estado: str = "activo",
    **kwargs,
) -> dict:
    """Registra un nuevo transportador en Supabase."""
    nombre = nombre_transportador or nombre_proveedor
    data = {
        "nombre_proveedor": nombre,
        "nombre_transportador": nombre,
        "contacto": contacto,
        "telefono": telefono,
        "correo": correo,
        "direccion": direccion,
        "estado": estado,
    }
    resultado = db.crear_transportador(data)
    return {
        "creado": True,
        "transportador": resultado,
        "proveedor": resultado,
    }


handle_crear_proveedor = handle_crear_transportador


def handle_eliminar_transportador(
    id_transportador: int = None,
    id_proveedor: int = None,
    **kwargs,
) -> dict:
    """Elimina un transportador de Supabase."""
    _id = id_transportador or id_proveedor
    db.eliminar_transportador(_id)
    return {
        "eliminado": True,
        "id_transportador": _id,
        "id_proveedor": _id,
    }


handle_eliminar_proveedor = handle_eliminar_transportador


# ─── Dispatcher ───

HANDLER_MAP = {
    "listar_transportadores": handle_listar_transportadores,
    "listar_proveedores": handle_listar_proveedores,
    "consultar_saldo_tienda": handle_consultar_saldo_tienda,
    "consultar_saldo_transportador": handle_consultar_saldo_transportador,
    "consultar_saldo_proveedor": handle_consultar_saldo_proveedor,
    "registrar_entrega": handle_registrar_entrega,
    "registrar_recogida": handle_registrar_recogida,
    "ver_resumen_general": handle_ver_resumen_general,
    "ver_tiendas_criticas": handle_ver_tiendas_criticas,
    "crear_transportador": handle_crear_transportador,
    "crear_proveedor": handle_crear_proveedor,
    "eliminar_transportador": handle_eliminar_transportador,
    "eliminar_proveedor": handle_eliminar_proveedor,
}


def dispatch(tool_name: str, tool_input: dict) -> dict:
    """Ejecuta la herramienta indicada por el agente."""
    handler = HANDLER_MAP.get(tool_name)
    if handler is None:
        return {"error": f"Herramienta desconocida: {tool_name}"}
    return handler(**tool_input)


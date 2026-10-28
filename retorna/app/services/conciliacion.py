"""
RETORNA — Servicio de conciliación.

Reglas de negocio sobre entregas vs recogidas.
Trabaja con las tablas de Supabase: entregas, recogidas, proveedor.
Compara e indexa de forma insensible a mayúsculas, minúsculas, espacios y tildes.
"""

from app.db.supabase_client import db
from app.services.normalizer import normalizar_texto, normalizar_nombre_tienda, resolver_tienda, coinciden_tiendas


def conciliar_tienda(nombre_tienda: str) -> dict:
    """
    Concilia entregas vs recogidas para una tienda.
    Retorna saldo de canastas pendientes por tipo.
    Funciona sin importar si el usuario escribe en mayúsculas, minúsculas, con tildes o con typos.
    """
    todas_entregas = db.listar_entregas()
    todas_recogidas = db.listar_recogidas()

    tiendas_existentes = set(
        e.get("nombre_tienda") for e in (todas_entregas + todas_recogidas) if e.get("nombre_tienda")
    )
    tienda_resuelta = resolver_tienda(nombre_tienda, tiendas_existentes)

    entregas = [
        e for e in todas_entregas
        if coinciden_tiendas(e.get("nombre_tienda"), tienda_resuelta)
    ]
    recogidas = [
        r for r in todas_recogidas
        if coinciden_tiendas(r.get("nombre_tienda"), tienda_resuelta)
    ]

    total_ent_peq = sum(e.get("cantidad_canastas_pequenas", 0) or 0 for e in entregas)
    total_ent_grd = sum(e.get("cantidad_canastas_grandes", 0) or 0 for e in entregas)
    total_rec_peq = sum(r.get("cantidad_canastas_pequenas", 0) or 0 for r in recogidas)
    total_rec_grd = sum(r.get("cantidad_canastas_grandes", 0) or 0 for r in recogidas)

    saldo_peq = total_ent_peq - total_rec_peq
    saldo_grd = total_ent_grd - total_rec_grd
    total_entregadas = total_ent_peq + total_ent_grd
    total_recogidas = total_rec_peq + total_rec_grd
    saldo_total = saldo_peq + saldo_grd

    tasa = round(1 - (total_recogidas / total_entregadas), 3) if total_entregadas > 0 else 0.0

    # Nombre oficial representativo
    nombre_mostrar = (
        entregas[0].get("nombre_tienda")
        if entregas
        else (recogidas[0].get("nombre_tienda") if recogidas else normalizar_nombre_tienda(nombre_tienda))
    )

    return {
        "nombre_tienda": nombre_mostrar,
        "entregas": {
            "pequenas": total_ent_peq,
            "grandes": total_ent_grd,
            "total": total_entregadas,
        },
        "recogidas": {
            "pequenas": total_rec_peq,
            "grandes": total_rec_grd,
            "total": total_recogidas,
        },
        "saldo": {
            "pequenas": saldo_peq,
            "grandes": saldo_grd,
            "total": saldo_total,
        },
        "tasa_no_retorno": tasa,
        "total_movimientos": len(entregas) + len(recogidas),
    }


def conciliar_transportador(id_transportador: int) -> dict:
    """
    Concilia entregas vs recogidas para un transportador.
    """
    transportador = db.obtener_transportador(id_transportador)
    entregas = db.entregas_por_transportador(id_transportador)
    recogidas = db.recogidas_por_transportador(id_transportador)

    total_ent_peq = sum(e.get("cantidad_canastas_pequenas", 0) or 0 for e in entregas)
    total_ent_grd = sum(e.get("cantidad_canastas_grandes", 0) or 0 for e in entregas)
    total_rec_peq = sum(r.get("cantidad_canastas_pequenas", 0) or 0 for r in recogidas)
    total_rec_grd = sum(r.get("cantidad_canastas_grandes", 0) or 0 for r in recogidas)

    saldo_total = (total_ent_peq + total_ent_grd) - (total_rec_peq + total_rec_grd)
    total_ent = total_ent_peq + total_ent_grd
    total_rec = total_rec_peq + total_rec_grd
    tasa = round(1 - (total_rec / total_ent), 3) if total_ent > 0 else 0.0

    nombre = (
        transportador.get("nombre_transportador")
        or transportador.get("nombre_proveedor", "Desconocido")
        if transportador
        else "No encontrado"
    )

    return {
        "id_transportador": id_transportador,
        "nombre_transportador": nombre,
        # Compatibilidad con integraciones previas
        "id_proveedor": id_transportador,
        "nombre_proveedor": nombre,
        "total_entregadas": total_ent,
        "total_recogidas": total_rec,
        "saldo_canastas": saldo_total,
        "saldo_pequenas": total_ent_peq - total_rec_peq,
        "saldo_grandes": total_ent_grd - total_rec_grd,
        "tasa_no_retorno": tasa,
        "total_entregas": len(entregas),
        "total_recogidas_count": len(recogidas),
    }


# Alias de compatibilidad hacia atrás
conciliar_proveedor = conciliar_transportador


def resumen_por_tienda() -> list[dict]:
    """
    Resumen de saldo por cada tienda única registrada en entregas o recogidas,
    unificando tiendas con variaciones de mayúsculas o espacios.
    """
    entregas = db.listar_entregas()
    recogidas = db.listar_recogidas()

    # Mapeo normalizado: norm_key -> nombre_representativo oficial
    tiendas_map = {}
    for mov in (entregas + recogidas):
        nom = mov.get("nombre_tienda")
        if nom and str(nom).strip():
            nom_resuelto = resolver_tienda(nom)
            k = normalizar_texto(nom_resuelto)
            if k not in tiendas_map:
                tiendas_map[k] = nom_resuelto

    return [conciliar_tienda(t) for t in sorted(tiendas_map.values())]


def resumen_por_transportador() -> list[dict]:
    """Resumen de saldo por cada transportador."""
    transportadores = db.listar_transportadores()
    return [conciliar_transportador(t["id_transportador"]) for t in transportadores]


# Alias de compatibilidad hacia atrás
resumen_por_proveedor = resumen_por_transportador


def tiendas_criticas(umbral_saldo: int = 5, umbral_tasa: float = 0.25) -> list[dict]:
    """Tiendas con saldo alto o tasa de no retorno preocupante."""
    resumen = resumen_por_tienda()
    criticas = [
        r for r in resumen
        if r["saldo"]["total"] >= umbral_saldo or r["tasa_no_retorno"] >= umbral_tasa
    ]
    return sorted(criticas, key=lambda x: x["saldo"]["total"], reverse=True)


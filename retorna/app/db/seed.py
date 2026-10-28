"""
RETORNA — Generador de datos sintéticos para desarrollo.

Genera 5 tiendas, 3 rutas, 4 conductores y 90 días de movimientos
con una tasa de no retorno ~20%, concentrada en pocas rutas/tiendas.
"""

import random
from datetime import date, timedelta, datetime, timezone

from app.db.models import (
    init_db, SessionLocal,
    Tienda, Ruta, Conductor, Movimiento, Saldo
)


def seed():
    """Pobla la BD con datos sintéticos realistas."""
    init_db()
    db = SessionLocal()

    # Limpiar datos existentes
    for model in [Movimiento, Saldo, Conductor, Ruta, Tienda]:
        db.query(model).delete()
    db.commit()

    # ─── Rutas ───
    rutas = [
        Ruta(id=1, nombre="Ruta Norte", ciudad="Bogotá", zona="Norte"),
        Ruta(id=2, nombre="Ruta Sur", ciudad="Bogotá", zona="Sur"),
        Ruta(id=3, nombre="Ruta Centro", ciudad="Medellín", zona="Centro"),
    ]
    db.add_all(rutas)

    # ─── Conductores ───
    conductores = [
        Conductor(id=1, codigo="COND-001", nombre="Conductor A", ruta_id=1),
        Conductor(id=2, codigo="COND-002", nombre="Conductor B", ruta_id=2),
        Conductor(id=3, codigo="COND-003", nombre="Conductor C", ruta_id=3),
        Conductor(id=4, codigo="COND-004", nombre="Conductor D", ruta_id=1),
    ]
    db.add_all(conductores)

    # ─── Tiendas ───
    tiendas = [
        Tienda(id=1, nombre="Éxito Calle 80", cadena="Éxito", ciudad="Bogotá",
               zona="Norte", contacto_nombre="María López", contacto_whatsapp="+573001234567"),
        Tienda(id=2, nombre="Éxito Suba", cadena="Éxito", ciudad="Bogotá",
               zona="Norte", contacto_nombre="Carlos Ruiz", contacto_whatsapp="+573009876543"),
        Tienda(id=3, nombre="Jumbo Autopista", cadena="Jumbo", ciudad="Bogotá",
               zona="Sur", contacto_nombre="Ana García", contacto_whatsapp="+573005551234"),
        Tienda(id=4, nombre="Carulla Poblado", cadena="Carulla", ciudad="Medellín",
               zona="Centro", contacto_nombre="Pedro Martínez", contacto_whatsapp="+573007779999"),
        Tienda(id=5, nombre="Éxito Laureles", cadena="Éxito", ciudad="Medellín",
               zona="Centro", contacto_nombre="Laura Díaz", contacto_whatsapp="+573006668888"),
    ]
    db.add_all(tiendas)
    db.commit()

    # ─── Movimientos (90 días) ───
    # Tasas de pérdida por tienda (simulan concentración: H6)
    # Tiendas 3 y 5 tienen pérdida alta (~35-40%), las demás ~8-12%
    tasas_perdida = {1: 0.10, 2: 0.08, 3: 0.38, 4: 0.12, 5: 0.35}
    # Conductor asignado por tienda
    conductor_tienda = {1: 1, 2: 4, 3: 2, 4: 3, 5: 3}

    hoy = date.today()
    inicio = hoy - timedelta(days=90)
    random.seed(42)  # reproducibilidad

    for tienda_id, tasa in tasas_perdida.items():
        dia = inicio
        while dia <= hoy:
            # Saltar domingos
            if dia.weekday() == 6:
                dia += timedelta(days=1)
                continue

            entregadas = random.randint(15, 40)

            # Más pérdida los viernes y sábados (H7: estacionalidad)
            factor_dia = 1.0
            if dia.weekday() in (4, 5):  # viernes, sábado
                factor_dia = 1.4

            tasa_efectiva = min(tasa * factor_dia, 0.6)
            perdida = int(entregadas * tasa_efectiva * random.uniform(0.5, 1.5))
            recogidas = max(0, entregadas - perdida)

            mov = Movimiento(
                fecha=dia,
                tienda_id=tienda_id,
                conductor_id=conductor_tienda[tienda_id],
                entregadas=entregadas,
                recogidas=recogidas,
            )
            db.add(mov)

            dia += timedelta(days=1)

    db.commit()

    # ─── Calcular saldos actuales ───
    for tienda in tiendas:
        movs = db.query(Movimiento).filter(Movimiento.tienda_id == tienda.id).all()
        total_entregadas = sum(m.entregadas for m in movs)
        total_recogidas = sum(m.recogidas for m in movs)
        saldo_actual = total_entregadas - total_recogidas

        # Días desde la primera entrega sin recogida total
        primer_mov = min(movs, key=lambda m: m.fecha) if movs else None
        dias = (hoy - primer_mov.fecha).days if primer_mov else 0

        db.add(Saldo(
            tienda_id=tienda.id,
            bandejas_estimadas=saldo_actual,
            dias_en_consignacion=dias,
            ultima_actualizacion=datetime.now(timezone.utc),
        ))

    db.commit()

    # ─── Resumen ───
    print("[OK] Seed completado:")
    print(f"   - {len(tiendas)} tiendas")
    print(f"   - {len(rutas)} rutas")
    print(f"   - {len(conductores)} conductores")
    total_movs = db.query(Movimiento).count()
    print(f"   - {total_movs} movimientos (90 dias)")
    for tienda in tiendas:
        saldo = db.query(Saldo).filter(Saldo.tienda_id == tienda.id).first()
        print(f"   - {tienda.nombre}: saldo = {saldo.bandejas_estimadas} bandejas")

    db.close()


if __name__ == "__main__":
    seed()

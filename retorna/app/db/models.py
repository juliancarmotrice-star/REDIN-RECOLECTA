"""
RETORNA — Modelos de base de datos con SQLAlchemy.
Esquema simplificado para el MVP: tiendas, movimientos, saldos, alertas.
"""

from datetime import datetime, date
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Date,
    DateTime, Text, ForeignKey, CheckConstraint
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    echo=False,
)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Tienda(Base):
    __tablename__ = "tiendas"

    id = Column(Integer, primary_key=True)
    nombre = Column(String, nullable=False)
    cadena = Column(String)
    ciudad = Column(String)
    zona = Column(String)
    contacto_nombre = Column(String)
    contacto_whatsapp = Column(String)

    movimientos = relationship("Movimiento", back_populates="tienda")
    saldo = relationship("Saldo", back_populates="tienda", uselist=False)
    alertas = relationship("Alerta", back_populates="tienda")

    def __repr__(self):
        return f"<Tienda {self.id}: {self.nombre} ({self.cadena})>"


class Ruta(Base):
    __tablename__ = "rutas"

    id = Column(Integer, primary_key=True)
    nombre = Column(String, nullable=False)
    ciudad = Column(String)
    zona = Column(String)

    conductores = relationship("Conductor", back_populates="ruta")


class Conductor(Base):
    __tablename__ = "conductores"

    id = Column(Integer, primary_key=True)
    codigo = Column(String, unique=True, nullable=False)  # código anónimo
    nombre = Column(String)
    ruta_id = Column(Integer, ForeignKey("rutas.id"))

    ruta = relationship("Ruta", back_populates="conductores")
    movimientos = relationship("Movimiento", back_populates="conductor")


class Movimiento(Base):
    """Datos importados de la app del conductor: cada entrega/recogida."""
    __tablename__ = "movimientos"

    id = Column(Integer, primary_key=True)
    fecha = Column(Date, nullable=False)
    tienda_id = Column(Integer, ForeignKey("tiendas.id"), nullable=False)
    conductor_id = Column(Integer, ForeignKey("conductores.id"))
    entregadas = Column(Integer, nullable=False, default=0)
    recogidas = Column(Integer, nullable=False, default=0)
    creado_en = Column(DateTime, default=datetime.utcnow)

    tienda = relationship("Tienda", back_populates="movimientos")
    conductor = relationship("Conductor", back_populates="movimientos")


class Saldo(Base):
    """Saldo actual de bandejas por tienda (calculado a partir de movimientos)."""
    __tablename__ = "saldos"

    tienda_id = Column(Integer, ForeignKey("tiendas.id"), primary_key=True)
    bandejas_estimadas = Column(Integer, default=0)
    dias_en_consignacion = Column(Integer, default=0)
    ultima_actualizacion = Column(DateTime, default=datetime.utcnow)

    tienda = relationship("Tienda", back_populates="saldo")


class Alerta(Base):
    """Alertas generadas por el agente o el sistema de conciliación."""
    __tablename__ = "alertas"

    id = Column(Integer, primary_key=True)
    tienda_id = Column(Integer, ForeignKey("tiendas.id"), nullable=False)
    tipo = Column(String, nullable=False)  # diferencia, vencida, sin_respuesta
    detalle = Column(Text)
    estado = Column(String, default="abierta")  # abierta, resuelta, escalada
    creado_en = Column(DateTime, default=datetime.utcnow)

    tienda = relationship("Tienda", back_populates="alertas")


def init_db():
    """Crea todas las tablas si no existen."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Generador de sesiones para inyección de dependencias en FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

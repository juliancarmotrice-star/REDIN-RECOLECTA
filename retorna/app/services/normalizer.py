"""
RETORNA — Utilidades avanzadas de normalización, fuzzy matching y catálogo maestro de clientes/tiendas.

Permite que las consultas de tiendas y comandos funcionen con máxima tolerancia a fallos:
- Insensible a mayúsculas, minúsculas y tildes (éxito == exito == ÉXITO == extio)
- Tolerancia a errores tipográficos (typos como 'extio', 'carula', 'olimpca', 'genral')
- Expansión de abreviaciones viales ('cll', 'clle' -> 'calle', 'cra', 'kr' -> 'carrera')
- Catálogo maestro de clientes / tiendas (grandes superficies) con ubicación física
- Distinción estricta entre CLIENTE/TIENDA (punto de entrega) y PROVEEDOR (productor)
"""

import difflib
import re
import unicodedata


# ─── Catálogo Maestro de Clientes / Tiendas (Grandes Superficies) ───
CATALOGO_CLIENTES_TIENDAS = {
    "Exito Calle 80": {
        "nombre_oficial": "Exito Calle 80",
        "cadena": "Grupo Éxito",
        "tipo": "Hipermercado / Gran Superficie",
        "direccion": "Calle 80 # 69-70",
        "ciudad": "Bogotá, D.C.",
        "zona": "Occidente",
        "aliases": [
            "exito calle 80", "exito 80", "exito cll 80", "exito clle 80",
            "extio 80", "extio calle 80", "extio cll 80", "exito c80",
            "exito ochenta", "hiper exito 80", "exito de la 80", "exito"
        ],
    },
    "Carulla 140": {
        "nombre_oficial": "Carulla 140",
        "cadena": "Grupo Éxito",
        "tipo": "Supermercado Premium",
        "direccion": "Calle 140 # 11-45, Cedritos",
        "ciudad": "Bogotá, D.C.",
        "zona": "Norte",
        "aliases": [
            "carulla 140", "carulla cll 140", "carulla calle 140",
            "carula 140", "carula", "carulla", "carulla cedritos", "carulla 140 cedritos"
        ],
    },
    "Olímpica Calle 68": {
        "nombre_oficial": "Olímpica Calle 68",
        "cadena": "Supertiendas Olímpica",
        "tipo": "Superalmacén",
        "direccion": "Calle 68 # 15-20, Chapinero",
        "ciudad": "Bogotá, D.C.",
        "zona": "Centro-Norte",
        "aliases": [
            "olimpica calle 68", "olimpica 68", "olimpica cll 68",
            "olimpca 68", "olimpca calle 68", "olimpica", "olimpca", "supertiendas olimpica"
        ],
    },
    "Jumbo Suba": {
        "nombre_oficial": "Jumbo Suba",
        "cadena": "Cencosud",
        "tipo": "Hipermercado",
        "direccion": "Avenida Suba # 115-58, CC Centro Suba",
        "ciudad": "Bogotá, D.C.",
        "zona": "Suba",
        "aliases": [
            "jumbo suba", "jumbo av suba", "jumbo centro suba", "jumbo", "cencosud suba"
        ],
    },
    "Tienda General": {
        "nombre_oficial": "Tienda General",
        "cadena": "Punto Genérico / Varios",
        "tipo": "Punto de Venta General",
        "direccion": "Bodega Principal / Sin especificar",
        "ciudad": "Bogotá, D.C.",
        "zona": "Principal",
        "aliases": [
            "tienda general", "tienda genral", "tienda gral", "general", "gral", "bodega general"
        ],
    },
}

# Diccionario de correcciones tipográficas frecuentes en pedidos de conductores
CORRECCIONES_TYPOS = {
    "extio": "exito",
    "exitoo": "exito",
    "exito": "exito",
    "carula": "carulla",
    "carrulla": "carulla",
    "olimpca": "olimpica",
    "olimpika": "olimpica",
    "genral": "general",
    "tiendageneral": "tienda general",
    "cll": "calle",
    "clle": "calle",
    "c/": "calle",
    "cra": "carrera",
    "crra": "carrera",
    "kr": "carrera",
    "kra": "carrera",
    "av": "avenida",
    "ave": "avenida",
    "diag": "diagonal",
    "transv": "transversal",
}


def normalizar_texto(texto: str | None) -> str:
    """
    Convierte a minúsculas, remueve tildes/acentos, corrige caracteres corruptos,
    normaliza abreviaturas viales y typos comunes.
    Ejemplo:
        '  Éxito   Cll 80  ' -> 'exito calle 80'
        'extio clle 80' -> 'exito calle 80'
        'TIENDA GENRAL' -> 'tienda general'
    """
    if not texto:
        return ""

    # Reemplazar caracteres corruptos de codificación (ej: \ufffd -> e)
    t = str(texto).replace("\ufffd", "e")

    # Remover tildes y diacríticos con descomposición Unicode NFKD
    nfkd = unicodedata.normalize("NFKD", t)
    sin_tildes = "".join(c for c in nfkd if not unicodedata.combining(c))

    # Limpiar signos de puntuación no deseados excepto números y letras
    limpio = re.sub(r"[^\w\s/]", " ", sin_tildes.lower())
    palabras = limpio.strip().split()

    # Reemplazar abreviaciones y typos conocidos palabra por palabra
    normalizadas = [CORRECCIONES_TYPOS.get(p, p) for p in palabras]
    return " ".join(normalizadas)


def resolver_tienda(nombre_o_texto: str | None, tiendas_existentes_db: set[str] | list[str] | None = None) -> str:
    """
    Resuelve el nombre canónico de la tienda aplicando:
    1. Búsqueda exacta normalizada en catálogo maestro
    2. Búsqueda de alias en catálogo maestro
    3. Búsqueda contra tiendas registradas en Supabase (entregas y recogidas)
    4. Similitud difusa (fuzzy matching) para tolerar errores ortográficos / tildes erróneas
    """
    if not nombre_o_texto or not str(nombre_o_texto).strip():
        return "Tienda General"

    texto_norm = normalizar_texto(nombre_o_texto)

    # 1. Búsqueda directa por alias en el Catálogo Maestro
    for nombre_oficial, info in CATALOGO_CLIENTES_TIENDAS.items():
        if texto_norm == normalizar_texto(nombre_oficial):
            return nombre_oficial
        for alias in info["aliases"]:
            alias_norm = normalizar_texto(alias)
            if alias_norm == texto_norm:
                return nombre_oficial

    # 2. Búsqueda por subcadena / presencia de alias en texto más largo
    # (Priorizando nombres con más palabras como 'exito calle 80' antes que 'exito')
    candidatos_sub = []
    for nombre_oficial, info in CATALOGO_CLIENTES_TIENDAS.items():
        for alias in info["aliases"]:
            alias_norm = normalizar_texto(alias)
            if alias_norm in texto_norm:
                candidatos_sub.append((len(alias_norm), nombre_oficial))
    if candidatos_sub:
        candidatos_sub.sort(key=lambda x: x[0], reverse=True)
        return candidatos_sub[0][1]

    # 3. Búsqueda en tiendas existentes en Supabase
    tiendas_db = list(tiendas_existentes_db or [])
    for t_db in tiendas_db:
        if t_db and normalizar_texto(t_db) == texto_norm:
            return t_db

    # 4. Búsqueda difusa (Fuzzy Matching) con SequenceMatcher
    mejor_similitud = 0.0
    mejor_match = None

    # Comparar con alias del catálogo
    for nombre_oficial, info in CATALOGO_CLIENTES_TIENDAS.items():
        for alias in info["aliases"]:
            alias_norm = normalizar_texto(alias)
            sim = difflib.SequenceMatcher(None, texto_norm, alias_norm).ratio()
            if sim > mejor_similitud:
                mejor_similitud = sim
                mejor_match = nombre_oficial

    # Comparar con tiendas en base de datos
    for t_db in tiendas_db:
        if not t_db:
            continue
        sim = difflib.SequenceMatcher(None, texto_norm, normalizar_texto(t_db)).ratio()
        if sim > mejor_similitud:
            mejor_similitud = sim
            mejor_match = t_db

    # Umbral de tolerancia a typos: 0.65 es suficiente para 'extio' -> 'exito', 'carula' -> 'carulla'
    if mejor_similitud >= 0.65 and mejor_match:
        return mejor_match

    # 5. Formato por defecto respetable
    limpio = " ".join(str(nombre_o_texto).strip().split())
    if limpio.isupper() or limpio.islower():
        return limpio.title()
    return limpio


def normalizar_nombre_tienda(nombre: str | None) -> str:
    """Mantiene compatibilidad hacia atrás llamando a resolver_tienda."""
    return resolver_tienda(nombre)


def coinciden_tiendas(tienda_a: str | None, tienda_b: str | None) -> bool:
    """Verifica si dos tiendas corresponden a la misma sede/cliente."""
    res_a = resolver_tienda(tienda_a)
    res_b = resolver_tienda(tienda_b)
    if res_a == res_b:
        return True
    return normalizar_texto(tienda_a) == normalizar_texto(tienda_b)


def es_tienda_o_cliente(nombre_o_texto: str | None) -> bool:
    """
    Determina si un nombre corresponde a una tienda/cliente (gran superficie),
    evitando que sea registrado erróneamente como un nuevo proveedor.
    """
    if not nombre_o_texto:
        return False
    texto_norm = normalizar_texto(nombre_o_texto)

    # Palabras clave de tiendas/cadenas de retail en Colombia
    palabras_tienda = ["exito", "carulla", "olimpica", "jumbo", "metro", "d1", "ara", "isimo", "tienda", "supermercado"]
    if any(p in texto_norm for p in palabras_tienda):
        return True

    # Comprobar contra catálogo maestro
    for info in CATALOGO_CLIENTES_TIENDAS.values():
        for alias in info["aliases"]:
            if normalizar_texto(alias) in texto_norm or texto_norm in normalizar_texto(alias):
                return True
    return False


def obtener_info_tienda(nombre: str | None) -> dict | None:
    """Retorna la ficha del catálogo maestro para una tienda."""
    nombre_resuelto = resolver_tienda(nombre)
    return CATALOGO_CLIENTES_TIENDAS.get(nombre_resuelto)

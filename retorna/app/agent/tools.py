"""
RETORNA — Definicion de herramientas (tools) del agente.

Herramientas ajustadas a las tablas de Supabase:
proveedor, canasta, entregas, recogidas.
"""

TOOLS = [
    {
        "name": "listar_transportadores",
        "description": (
            "Lista todos los transportadores registrados con su información de contacto. "
            "Usa esta herramienta cuando necesites ver los transportadores o empresas de transporte disponibles."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "listar_proveedores",
        "description": (
            "Alias de listar_transportadores. Lista transportadores registrados con su informacion de contacto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "consultar_saldo_transportador",
        "description": (
            "Consulta el resumen de entregas y recogidas de un transportador por su ID. "
            "Muestra cuántas canastas ha entregado y cuántas ha recogido en total."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id_transportador": {
                    "type": "integer",
                    "description": "ID del transportador.",
                },
            },
            "required": ["id_transportador"],
        },
    },
    {
        "name": "consultar_saldo_tienda",
        "description": (
            "Consulta el saldo actual de canastas en una tienda: cuantas se han entregado, "
            "cuantas recogidas, el saldo pendiente (pequenas y grandes) y la tasa de no retorno. "
            "Usa esta herramienta SIEMPRE antes de dar informacion sobre una tienda."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre_tienda": {
                    "type": "string",
                    "description": "Nombre exacto de la tienda tal como aparece en los registros.",
                },
            },
            "required": ["nombre_tienda"],
        },
    },
    {
        "name": "consultar_saldo_proveedor",
        "description": (
            "Consulta el resumen de entregas y recogidas de un proveedor. "
            "Muestra cuantas canastas ha entregado y cuantas ha recogido en total."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id_proveedor": {
                    "type": "integer",
                    "description": "ID del proveedor.",
                },
            },
            "required": ["id_proveedor"],
        },
    },
    {
        "name": "registrar_entrega",
        "description": (
            "Registra una entrega de canastas a una tienda. "
            "Requiere el ID del proveedor, nombre de la tienda, y las cantidades."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id_proveedor": {
                    "type": "integer",
                    "description": "ID del proveedor que entrega.",
                },
                "nombre_tienda": {
                    "type": "string",
                    "description": "Nombre de la tienda donde se entregan las canastas.",
                },
                "cantidad_canastas_pequenas": {
                    "type": "integer",
                    "description": "Numero de canastas pequenas entregadas. 0 si no aplica.",
                },
                "cantidad_canastas_grandes": {
                    "type": "integer",
                    "description": "Numero de canastas grandes entregadas. 0 si no aplica.",
                },
            },
            "required": ["id_proveedor", "nombre_tienda"],
        },
    },
    {
        "name": "registrar_recogida",
        "description": (
            "Registra una recogida de canastas de una tienda. "
            "Requiere el ID del proveedor, nombre de la tienda, y las cantidades recogidas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id_proveedor": {
                    "type": "integer",
                    "description": "ID del proveedor que recoge.",
                },
                "nombre_tienda": {
                    "type": "string",
                    "description": "Nombre de la tienda donde se recogen las canastas.",
                },
                "cantidad_canastas_pequenas": {
                    "type": "integer",
                    "description": "Numero de canastas pequenas recogidas. 0 si no aplica.",
                },
                "cantidad_canastas_grandes": {
                    "type": "integer",
                    "description": "Numero de canastas grandes recogidas. 0 si no aplica.",
                },
            },
            "required": ["id_proveedor", "nombre_tienda"],
        },
    },
    {
        "name": "ver_resumen_general",
        "description": (
            "Muestra un resumen general: saldo por tienda y por proveedor. "
            "Util para ver el panorama completo de canastas pendientes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "ver_tiendas_criticas",
        "description": (
            "Lista las tiendas con saldo alto o tasa de no retorno preocupante. "
            "Util para priorizar donde actuar primero."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "crear_transportador",
        "description": (
            "Registra un nuevo transportador en la base de datos de Supabase. "
            "Requiere nombre_transportador y opcionalmente contacto, telefono, correo, direccion."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre_transportador": {
                    "type": "string",
                    "description": "Nombre de la empresa o transportador.",
                },
                "contacto": {
                    "type": "string",
                    "description": "Nombre de la persona o contacto principal.",
                },
                "telefono": {
                    "type": "string",
                    "description": "Número telefónico del transportador.",
                },
                "correo": {
                    "type": "string",
                    "description": "Correo electrónico de contacto.",
                },
                "direccion": {
                    "type": "string",
                    "description": "Dirección física de despacho u oficina.",
                },
                "estado": {
                    "type": "string",
                    "description": "Estado del transportador (ej: activo, inactivo). Por defecto 'activo'.",
                },
            },
            "required": ["nombre_transportador"],
        },
    },
    {
        "name": "crear_proveedor",
        "description": (
            "Alias de crear_transportador. Registra un nuevo transportador en Supabase."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre_proveedor": {
                    "type": "string",
                    "description": "Nombre del transportador.",
                },
                "contacto": {"type": "string"},
                "telefono": {"type": "string"},
                "correo": {"type": "string"},
                "direccion": {"type": "string"},
                "estado": {"type": "string"},
            },
            "required": ["nombre_proveedor"],
        },
    },
    {
        "name": "eliminar_transportador",
        "description": (
            "Elimina un transportador de la base de datos de Supabase por su id_transportador."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id_transportador": {
                    "type": "integer",
                    "description": "ID numérico del transportador a eliminar.",
                },
            },
            "required": ["id_transportador"],
        },
    },
    {
        "name": "eliminar_proveedor",
        "description": (
            "Alias de eliminar_transportador. Elimina un transportador de Supabase."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id_proveedor": {
                    "type": "integer",
                    "description": "ID numérico a eliminar.",
                },
            },
            "required": ["id_proveedor"],
        },
    },
]

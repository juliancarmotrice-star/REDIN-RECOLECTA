-- ============================================================
-- RETORNA — Esquema completo de base de datos
-- Trazabilidad de bandejas/canastas en consignación
-- ============================================================

-- ─────────────────────────────────────────────────────────────
-- TABLAS MAESTRAS
-- ─────────────────────────────────────────────────────────────

-- Tipos de canasta/bandeja
CREATE TABLE IF NOT EXISTS tipos_canasta (
    id              SERIAL PRIMARY KEY,
    codigo          VARCHAR(20) UNIQUE NOT NULL,       -- ej: 'CAN-STD', 'CAN-GRD', 'BAN-PEQ'
    nombre          VARCHAR(100) NOT NULL,             -- ej: 'Canasta estándar', 'Canasta grande'
    descripcion     TEXT,
    material        VARCHAR(50),                       -- plástico, metal, madera
    capacidad_kg    NUMERIC(6,2),                      -- capacidad en kg
    costo_unitario  NUMERIC(10,2),                     -- costo de reposición
    activo          BOOLEAN DEFAULT TRUE,
    creado_en       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cadenas comerciales (grandes superficies)
CREATE TABLE IF NOT EXISTS cadenas (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(100) UNIQUE NOT NULL,      -- ej: 'Éxito', 'Jumbo', 'Carulla'
    nit             VARCHAR(20),
    contacto_nombre VARCHAR(100),
    contacto_email  VARCHAR(100),
    contacto_tel    VARCHAR(20),
    activo          BOOLEAN DEFAULT TRUE,
    creado_en       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tiendas / Puntos de venta
CREATE TABLE IF NOT EXISTS tiendas (
    id              SERIAL PRIMARY KEY,
    codigo          VARCHAR(20) UNIQUE NOT NULL,       -- código interno de la tienda
    nombre          VARCHAR(150) NOT NULL,
    cadena_id       INT REFERENCES cadenas(id),
    ciudad          VARCHAR(100),
    zona            VARCHAR(50),                       -- Norte, Sur, Centro, etc.
    direccion       TEXT,
    contacto_nombre VARCHAR(100),
    contacto_whatsapp VARCHAR(20),
    contacto_email  VARCHAR(100),
    latitud         NUMERIC(10,7),
    longitud        NUMERIC(10,7),
    activo          BOOLEAN DEFAULT TRUE,
    creado_en       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Zonas / Regiones
CREATE TABLE IF NOT EXISTS zonas (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL,
    ciudad          VARCHAR(100),
    descripcion     TEXT
);

-- Rutas de distribución
CREATE TABLE IF NOT EXISTS rutas (
    id              SERIAL PRIMARY KEY,
    codigo          VARCHAR(20) UNIQUE NOT NULL,       -- ej: 'RUT-BOG-N01'
    nombre          VARCHAR(100) NOT NULL,
    zona_id         INT REFERENCES zonas(id),
    ciudad          VARCHAR(100),
    dia_programado  VARCHAR(20),                       -- lunes, martes, etc. (si aplica)
    activo          BOOLEAN DEFAULT TRUE,
    creado_en       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Relación ruta-tiendas (qué tiendas visita cada ruta)
CREATE TABLE IF NOT EXISTS rutas_tiendas (
    ruta_id         INT REFERENCES rutas(id),
    tienda_id       INT REFERENCES tiendas(id),
    orden_visita    INT,                               -- orden en que se visitan
    PRIMARY KEY (ruta_id, tienda_id)
);

-- Conductores / Transportistas
CREATE TABLE IF NOT EXISTS conductores (
    id              SERIAL PRIMARY KEY,
    codigo          VARCHAR(20) UNIQUE NOT NULL,       -- código anónimo para análisis
    nombre          VARCHAR(100),
    cedula          VARCHAR(20),                       -- encriptada en producción
    telefono        VARCHAR(20),
    ruta_id         INT REFERENCES rutas(id),          -- ruta asignada actualmente
    activo          BOOLEAN DEFAULT TRUE,
    creado_en       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Centros de distribución (CEDIS)
CREATE TABLE IF NOT EXISTS centros_distribucion (
    id              SERIAL PRIMARY KEY,
    codigo          VARCHAR(20) UNIQUE NOT NULL,
    nombre          VARCHAR(150) NOT NULL,
    ciudad          VARCHAR(100),
    direccion       TEXT,
    activo          BOOLEAN DEFAULT TRUE
);


-- ─────────────────────────────────────────────────────────────
-- TABLAS TRANSACCIONALES
-- ─────────────────────────────────────────────────────────────

-- Pedidos (orden de despacho desde el CEDIS)
CREATE TABLE IF NOT EXISTS pedidos (
    id                  SERIAL PRIMARY KEY,
    codigo_pedido       VARCHAR(30) UNIQUE NOT NULL,   -- número de pedido / remisión
    fecha_pedido        DATE NOT NULL,
    tienda_id           INT NOT NULL REFERENCES tiendas(id),
    centro_dist_id      INT REFERENCES centros_distribucion(id),
    conductor_id        INT REFERENCES conductores(id),
    ruta_id             INT REFERENCES rutas(id),
    estado              VARCHAR(30) DEFAULT 'pendiente'
                        CHECK (estado IN (
                            'pendiente',       -- creado, aún no despachado
                            'despachado',      -- salió del CEDIS
                            'entregado',       -- llegó a la tienda
                            'parcial',         -- entrega parcial
                            'recogido',        -- bandejas recogidas
                            'cerrado',         -- conciliado y cerrado
                            'cancelado'
                        )),
    observaciones       TEXT,
    creado_en           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizado_en      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Detalle del pedido por tipo de canasta
-- (un pedido puede tener múltiples tipos de canasta)
CREATE TABLE IF NOT EXISTS pedido_detalle (
    id                  SERIAL PRIMARY KEY,
    pedido_id           INT NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
    tipo_canasta_id     INT NOT NULL REFERENCES tipos_canasta(id),
    cantidad            INT NOT NULL CHECK (cantidad > 0),
    UNIQUE (pedido_id, tipo_canasta_id)
);

-- Movimientos de bandejas/canastas
-- Cada fila = una acción sobre canastas (entrega, recogida, conteo)
CREATE TABLE IF NOT EXISTS movimientos (
    id                  SERIAL PRIMARY KEY,
    pedido_id           INT REFERENCES pedidos(id),         -- pedido asociado (si aplica)
    tienda_id           INT NOT NULL REFERENCES tiendas(id),
    conductor_id        INT REFERENCES conductores(id),
    ruta_id             INT REFERENCES rutas(id),
    tipo_canasta_id     INT REFERENCES tipos_canasta(id),

    -- Tipo de movimiento
    es_entrega          BOOLEAN NOT NULL,                   -- TRUE = entrega, FALSE = recogida
    tipo                VARCHAR(20) NOT NULL
                        CHECK (tipo IN ('entrega', 'recogida', 'conteo', 'ajuste')),

    -- Cantidades
    cantidad_despachada INT DEFAULT 0,      -- lo que salió del CEDIS (según el pedido)
    cantidad_declarada  INT NOT NULL,       -- lo que reporta el conductor en la app
    cantidad_recibida   INT,                -- lo que confirma la tienda (si aplica)
    cantidad_vision     INT,                -- lo que cuenta la visión por computador
    confianza_vision    NUMERIC(3,2),       -- 0.00 a 1.00

    -- Fechas
    fecha               DATE NOT NULL,
    hora_registro       TIME,
    fecha_programada    DATE,               -- fecha en que se programó la recogida

    -- Trazabilidad
    origen_id           VARCHAR(50),        -- ID del registro en la app del conductor
    foto_url            TEXT,               -- URL de la foto de verificación
    reportado_por       VARCHAR(50),        -- 'conductor', 'jefe_tienda', 'supervisor'
    metodo_registro     VARCHAR(30),        -- 'app_conductor', 'whatsapp', 'manual', 'sistema'

    -- Auditoría
    creado_en           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizado_en      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Evita duplicados al reimportar desde la app
    CONSTRAINT uq_origen UNIQUE (origen_id)
);

-- Saldos por tienda y tipo de canasta (vista materializada / tabla calculada)
CREATE TABLE IF NOT EXISTS saldos (
    id                  SERIAL PRIMARY KEY,
    tienda_id           INT NOT NULL REFERENCES tiendas(id),
    tipo_canasta_id     INT REFERENCES tipos_canasta(id),
    bandejas_en_tienda  INT DEFAULT 0,      -- saldo acumulado
    dias_en_consignacion INT DEFAULT 0,     -- días desde la primera entrega sin recogida total
    ultima_entrega      DATE,
    ultima_recogida     DATE,
    ultima_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tienda_id, tipo_canasta_id)
);

-- Alertas generadas por el agente o el sistema
CREATE TABLE IF NOT EXISTS alertas (
    id                  SERIAL PRIMARY KEY,
    tienda_id           INT NOT NULL REFERENCES tiendas(id),
    pedido_id           INT REFERENCES pedidos(id),
    movimiento_id       INT REFERENCES movimientos(id),
    tipo                VARCHAR(30) NOT NULL
                        CHECK (tipo IN (
                            'diferencia',      -- discrepancia entre declarado y contado
                            'saldo_alto',      -- saldo acumulado por encima del umbral
                            'vencida',         -- consignación por más de N días
                            'sin_respuesta',   -- tienda no respondió al mensaje
                            'anomalia',        -- patrón atípico detectado
                            'foto_requerida'   -- se requiere verificación por foto
                        )),
    severidad           VARCHAR(10) DEFAULT 'media'
                        CHECK (severidad IN ('baja', 'media', 'alta', 'critica')),
    detalle             TEXT,
    estado              VARCHAR(20) DEFAULT 'abierta'
                        CHECK (estado IN ('abierta', 'en_revision', 'resuelta', 'escalada', 'descartada')),
    asignada_a          VARCHAR(100),       -- persona/rol responsable
    resuelta_en         TIMESTAMP,
    creado_en           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Verificaciones por foto (muestreo o por anomalía)
CREATE TABLE IF NOT EXISTS verificaciones (
    id                  SERIAL PRIMARY KEY,
    movimiento_id       INT REFERENCES movimientos(id),
    tienda_id           INT NOT NULL REFERENCES tiendas(id),
    motivo              VARCHAR(30)
                        CHECK (motivo IN ('muestreo', 'anomalia', 'saldo_alto', 'solicitud')),
    cantidad_declarada  INT,
    cantidad_vision     INT,
    confianza           NUMERIC(3,2),
    diferencia          INT,                -- declarada - vision
    foto_url            TEXT,
    verificado_por      VARCHAR(50),        -- 'conductor', 'supervisor', 'mercaderista'
    resultado           VARCHAR(20)
                        CHECK (resultado IN ('coincide', 'diferencia_menor', 'diferencia_mayor', 'pendiente')),
    creado_en           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Historial de mensajes (WhatsApp u otros canales)
CREATE TABLE IF NOT EXISTS mensajes (
    id                  SERIAL PRIMARY KEY,
    tienda_id           INT REFERENCES tiendas(id),
    conductor_id        INT REFERENCES conductores(id),
    direccion           VARCHAR(10) NOT NULL
                        CHECK (direccion IN ('entrante', 'saliente')),
    canal               VARCHAR(20) DEFAULT 'whatsapp'
                        CHECK (canal IN ('whatsapp', 'email', 'sms', 'sistema')),
    contenido           TEXT NOT NULL,
    leido               BOOLEAN DEFAULT FALSE,
    creado_en           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Programación de recogidas
CREATE TABLE IF NOT EXISTS recogidas_programadas (
    id                  SERIAL PRIMARY KEY,
    tienda_id           INT NOT NULL REFERENCES tiendas(id),
    ruta_id             INT REFERENCES rutas(id),
    conductor_id        INT REFERENCES conductores(id),
    fecha_programada    DATE NOT NULL,
    tipo_canasta_id     INT REFERENCES tipos_canasta(id),
    cantidad_estimada   INT,                -- bandejas que se espera recoger
    estado              VARCHAR(20) DEFAULT 'programada'
                        CHECK (estado IN ('programada', 'confirmada', 'completada', 'cancelada')),
    notas               TEXT,
    creado_en           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ─────────────────────────────────────────────────────────────
-- ÍNDICES para rendimiento
-- ─────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_movimientos_tienda      ON movimientos(tienda_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_fecha        ON movimientos(fecha);
CREATE INDEX IF NOT EXISTS idx_movimientos_pedido       ON movimientos(pedido_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_conductor    ON movimientos(conductor_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_tipo         ON movimientos(tipo);
CREATE INDEX IF NOT EXISTS idx_pedidos_tienda           ON pedidos(tienda_id);
CREATE INDEX IF NOT EXISTS idx_pedidos_fecha            ON pedidos(fecha_pedido);
CREATE INDEX IF NOT EXISTS idx_pedidos_estado           ON pedidos(estado);
CREATE INDEX IF NOT EXISTS idx_alertas_tienda           ON alertas(tienda_id);
CREATE INDEX IF NOT EXISTS idx_alertas_estado           ON alertas(estado);
CREATE INDEX IF NOT EXISTS idx_saldos_tienda            ON saldos(tienda_id);
CREATE INDEX IF NOT EXISTS idx_verificaciones_tienda    ON verificaciones(tienda_id);


-- ─────────────────────────────────────────────────────────────
-- VISTAS útiles
-- ─────────────────────────────────────────────────────────────

-- Vista: Tasa de no retorno por tienda (últimos 90 días)
CREATE OR REPLACE VIEW v_tasa_no_retorno_tienda AS
SELECT
    t.id                AS tienda_id,
    t.nombre            AS tienda,
    c.nombre            AS cadena,
    t.zona,
    SUM(CASE WHEN m.es_entrega THEN m.cantidad_declarada ELSE 0 END)     AS total_entregadas,
    SUM(CASE WHEN NOT m.es_entrega THEN m.cantidad_declarada ELSE 0 END) AS total_recogidas,
    SUM(CASE WHEN m.es_entrega THEN m.cantidad_declarada ELSE 0 END)
      - SUM(CASE WHEN NOT m.es_entrega THEN m.cantidad_declarada ELSE 0 END) AS saldo,
    CASE
        WHEN SUM(CASE WHEN m.es_entrega THEN m.cantidad_declarada ELSE 0 END) > 0
        THEN ROUND(1 - SUM(CASE WHEN NOT m.es_entrega THEN m.cantidad_declarada ELSE 0 END)::numeric
                      / SUM(CASE WHEN m.es_entrega THEN m.cantidad_declarada ELSE 0 END), 3)
        ELSE 0
    END                 AS tasa_no_retorno
FROM movimientos m
JOIN tiendas t ON t.id = m.tienda_id
LEFT JOIN cadenas c ON c.id = t.cadena_id
WHERE m.fecha >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY t.id, t.nombre, c.nombre, t.zona
ORDER BY tasa_no_retorno DESC;

-- Vista: Concentración de pérdida por ruta
CREATE OR REPLACE VIEW v_perdida_por_ruta AS
SELECT
    r.id                AS ruta_id,
    r.nombre            AS ruta,
    r.ciudad,
    COUNT(DISTINCT m.tienda_id)  AS tiendas_atendidas,
    SUM(CASE WHEN m.es_entrega THEN m.cantidad_declarada ELSE 0 END)     AS entregadas,
    SUM(CASE WHEN NOT m.es_entrega THEN m.cantidad_declarada ELSE 0 END) AS recogidas,
    SUM(CASE WHEN m.es_entrega THEN m.cantidad_declarada ELSE 0 END)
      - SUM(CASE WHEN NOT m.es_entrega THEN m.cantidad_declarada ELSE 0 END) AS perdida,
    CASE
        WHEN SUM(CASE WHEN m.es_entrega THEN m.cantidad_declarada ELSE 0 END) > 0
        THEN ROUND(1 - SUM(CASE WHEN NOT m.es_entrega THEN m.cantidad_declarada ELSE 0 END)::numeric
                      / SUM(CASE WHEN m.es_entrega THEN m.cantidad_declarada ELSE 0 END), 3)
        ELSE 0
    END                 AS tasa_no_retorno
FROM movimientos m
JOIN rutas r ON r.id = m.ruta_id
WHERE m.fecha >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY r.id, r.nombre, r.ciudad
ORDER BY perdida DESC;

-- Vista: Estado de pedidos con detalle
CREATE OR REPLACE VIEW v_estado_pedidos AS
SELECT
    p.id,
    p.codigo_pedido,
    p.fecha_pedido,
    t.nombre            AS tienda,
    c.nombre            AS cadena,
    cd.nombre           AS conductor,
    p.estado,
    COALESCE(SUM(pd.cantidad), 0) AS canastas_pedidas,
    p.creado_en
FROM pedidos p
JOIN tiendas t ON t.id = p.tienda_id
LEFT JOIN cadenas c ON c.id = t.cadena_id
LEFT JOIN conductores cd ON cd.id = p.conductor_id
LEFT JOIN pedido_detalle pd ON pd.pedido_id = p.id
GROUP BY p.id, p.codigo_pedido, p.fecha_pedido, t.nombre, c.nombre, cd.nombre, p.estado, p.creado_en
ORDER BY p.fecha_pedido DESC;

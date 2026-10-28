-- ==============================================================================
-- RETORNA — Script SQL para Supabase
-- Tablas para Control y Conciliación de Canastas con TRANSPORTADORES
-- ==============================================================================
-- Instrucciones:
-- 1. Abre tu proyecto en Supabase (https://supabase.com/dashboard)
-- 2. En el menú lateral izquierdo, haz clic en "SQL Editor"
-- 3. Crea una "New query", pega este script completo y haz clic en "RUN".
-- ==============================================================================

-- 1. TABLA DE TRANSPORTADORES
-- (Empresas o flotas de distribución encargadas del traslado de bandejas/canastas)
CREATE TABLE IF NOT EXISTS transportador (
    id_transportador        SERIAL PRIMARY KEY,
    nombre_transportador    VARCHAR(150) NOT NULL,
    contacto                VARCHAR(100),
    telefono                VARCHAR(50),
    correo                  VARCHAR(100),
    direccion               TEXT,
    estado                  VARCHAR(20) DEFAULT 'activo',
    creado_en               TIMESTAMPTZ DEFAULT NOW()
);

-- Migración automática si ya existía la tabla anterior 'proveedor':
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'proveedor' AND table_type = 'BASE TABLE') THEN
        INSERT INTO transportador (id_transportador, nombre_transportador, contacto, telefono, correo, direccion, estado)
        SELECT id_proveedor, nombre_proveedor, contacto, telefono, correo, direccion, estado
        FROM proveedor
        ON CONFLICT (id_transportador) DO NOTHING;
    END IF;
END $$;

-- 2. TABLA DE CANASTAS / BANDEJAS
CREATE TABLE IF NOT EXISTS canasta (
    id_canasta              SERIAL PRIMARY KEY,
    codigo_qr               VARCHAR(50) UNIQUE,
    tipo_canasta            VARCHAR(50) DEFAULT 'estándar',
    estado_canasta          VARCHAR(50) DEFAULT 'disponible',
    creado_en               TIMESTAMPTZ DEFAULT NOW()
);

-- 3. TABLA DE ENTREGAS
-- (Registro de canastas entregadas a tiendas por los transportadores)
CREATE TABLE IF NOT EXISTS entregas (
    id_entrega                  SERIAL PRIMARY KEY,
    id_transportador            INT REFERENCES transportador(id_transportador) ON DELETE SET NULL,
    id_proveedor                INT, -- Compatibilidad
    nombre_tienda               VARCHAR(150) NOT NULL,
    fecha                       DATE NOT NULL DEFAULT CURRENT_DATE,
    hora                        TIME NOT NULL DEFAULT CURRENT_TIME,
    cantidad_canastas_pequenas  INT DEFAULT 0,
    cantidad_canastas_grandes   INT DEFAULT 0,
    creado_en                   TIMESTAMPTZ DEFAULT NOW()
);

-- Si la tabla entregas ya existía, asegurar la columna id_transportador:
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'entregas') THEN
        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'entregas' AND column_name = 'id_transportador') THEN
            ALTER TABLE entregas ADD COLUMN id_transportador INT;
            UPDATE entregas SET id_transportador = id_proveedor WHERE id_transportador IS NULL;
        END IF;
    END IF;
END $$;

-- 4. TABLA DE RECOGIDAS
-- (Registro de canastas recuperadas desde tiendas por los transportadores)
CREATE TABLE IF NOT EXISTS recogidas (
    id_recogida                 SERIAL PRIMARY KEY,
    id_transportador            INT REFERENCES transportador(id_transportador) ON DELETE SET NULL,
    id_proveedor                INT, -- Compatibilidad
    nombre_tienda               VARCHAR(150) NOT NULL,
    fecha                       DATE NOT NULL DEFAULT CURRENT_DATE,
    hora                        TIME NOT NULL DEFAULT CURRENT_TIME,
    cantidad_canastas_pequenas  INT DEFAULT 0,
    cantidad_canastas_grandes   INT DEFAULT 0,
    creado_en                   TIMESTAMPTZ DEFAULT NOW()
);

-- Si la tabla recogidas ya existía, asegurar la columna id_transportador:
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'recogidas') THEN
        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'recogidas' AND column_name = 'id_transportador') THEN
            ALTER TABLE recogidas ADD COLUMN id_transportador INT;
            UPDATE recogidas SET id_transportador = id_proveedor WHERE id_transportador IS NULL;
        END IF;
    END IF;
END $$;

-- 5. POLÍTICAS DE SEGURIDAD (Row Level Security para acceso desde API / App)
ALTER TABLE transportador ENABLE ROW LEVEL SECURITY;
ALTER TABLE entregas ENABLE ROW LEVEL SECURITY;
ALTER TABLE recogidas ENABLE ROW LEVEL SECURITY;
ALTER TABLE canasta ENABLE ROW LEVEL SECURITY;

-- Reglas permisivas para el entorno del piloto / desarrollo
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Permitir todo en transportador') THEN
        CREATE POLICY "Permitir todo en transportador" ON transportador FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Permitir todo en entregas') THEN
        CREATE POLICY "Permitir todo en entregas" ON entregas FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Permitir todo en recogidas') THEN
        CREATE POLICY "Permitir todo en recogidas" ON recogidas FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Permitir todo en canasta') THEN
        CREATE POLICY "Permitir todo en canasta" ON canasta FOR ALL USING (true) WITH CHECK (true);
    END IF;
END $$;

-- 6. DATOS DE PRUEBA INICIALES (Flotas y Transportadores)
INSERT INTO transportador (id_transportador, nombre_transportador, contacto, telefono, correo, direccion, estado)
VALUES
    (1, 'Transportes Bimbo Flota Propia', 'Carlos Pérez (Coordinador Despachos)', '3101234567', 'despachos@bimbo.com', 'Calle 13 # 68-40, Bogotá', 'activo'),
    (2, 'Logística y Distribución Andina', 'Marcela Restrepo (Operaciones)', '3128889900', 'operaciones@andinalogistica.co', 'Av. Boyacá # 72-10, Bogotá', 'activo')
ON CONFLICT (id_transportador) DO UPDATE 
SET nombre_transportador = EXCLUDED.nombre_transportador;

-- Ajustar la secuencia del ID para futuros registros autoincrementables
SELECT setval(pg_get_serial_sequence('transportador', 'id_transportador'), COALESCE(MAX(id_transportador), 1)) FROM transportador;

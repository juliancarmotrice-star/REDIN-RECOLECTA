# RETORNA: adenda con el contexto real del reto

Este documento ajusta el diseño original de RETORNA con dos datos nuevos del reto:

1. **Hoy el conteo lo hace cada conductor a mano y lo digitaliza en una app en su teléfono.**
2. **Cerca del 20% de las bandejas diarias no retorna.**

Con esto cambia el enfoque. Ya no se trata de crear un sistema de captura desde cero, sino de **montar una capa de inteligencia sobre el proceso y los datos que ya existen**, y de encontrar dónde se pierde ese 20%.

---

## 1. Qué cambia respecto al diseño original

| Tema | Diseño original | Ajuste con el contexto real |
|---|---|---|
| Captura principal | Foto de la pila por el conductor | **La app actual del conductor sigue siendo la fuente.** RETORNA se conecta a ella |
| Rol de la foto | Conteo principal | **Verificación independiente por muestreo** (auditoría) |
| Problema central | Falta de trazabilidad | **Un 20% de fuga**: hay que diagnosticar dónde ocurre y por qué |
| Primer entregable | Piloto con WhatsApp y fotos | **Fase 0 de diagnóstico con los datos existentes**, antes de construir |
| Agente | Registra y concilia | Además **detecta anomalías, prioriza y recomienda acciones** |
| Cambio para el conductor | Aprender un flujo nuevo | **Cambio mínimo**: sigue usando su app y su rutina |

La idea central: no pedirle más trabajo al conductor, sino sacarle más valor a lo que ya registra.

---

## 2. Situación actual (AS-IS)

```
Conductor entrega producto y deja bandejas
        ↓
Cuenta a mano las bandejas
        ↓
Digita el conteo en su app del teléfono
        ↓
(En la próxima visita) cuenta de nuevo y digita lo recogido
        ↓
Nadie cruza sistemáticamente lo dejado vs. lo recogido
        ↓
≈ 20% de las bandejas diarias no retorna
```

**Debilidades del proceso actual:**
- El conteo es **autorreportado**: la misma persona que entrega y recoge es quien registra. No hay verificación independiente.
- No se distingue entre **retraso** (la bandeja vuelve días después) y **pérdida** (nunca vuelve).
- El dato existe, pero **no se analiza** por conductor, ruta, tienda, cadena o día de la semana.
- Sin ese análisis, no se sabe dónde actuar primero.

---

## 3. Hipótesis sobre el 20% que no retorna

Estas son hipótesis a **validar con datos**, no conclusiones. La Fase 0 sirve para confirmarlas o descartarlas.

| # | Hipótesis | Qué dato la confirmaría |
|---|---|---|
| H1 | **Acumulación en tienda:** se deja más de lo que se recoge y el saldo crece | Saldo por tienda que sube semana a semana |
| H2 | **Recogida incompleta:** el conductor no alcanza a recoger todo en la visita | Tiendas con saldo recurrente pese a visitas frecuentes |
| H3 | **Error de conteo o digitación** | Diferencias entre entregado y recogido que se corrigen de forma irregular |
| H4 | **Uso de bandejas por terceros:** reutilización por la tienda u otros proveedores | Tiendas o cadenas con pérdida sistemáticamente mayor |
| H5 | **Daño o desecho:** bandejas rotas que no se registran | Tasa alta de pérdida sin acumulación visible |
| H6 | **Concentración en pocos actores:** la pérdida no es pareja | Un pequeño grupo de rutas, conductores o tiendas explica la mayor parte |
| H7 | **Estacionalidad:** más pérdida en ciertos días o temporadas | Patrones por día de la semana o fecha |
| H8 | **Fallas del proceso en el centro de distribución** | Diferencias entre lo despachado y lo registrado como cargado |

Expectativa útil: en problemas de este tipo la pérdida suele concentrarse en pocos puntos. Si la H6 se confirma, **atacar el 20% del universo que explica la mayor parte de la fuga** da el mayor retorno con el menor esfuerzo.

---

## 4. Principio de diseño: montarse sobre la app existente

RETORNA **no reemplaza** la app del conductor. Se conecta a ella.

**Formas de integración (de menor a mayor esfuerzo):**
1. **Exportación periódica** (CSV o reporte) de la app a una carpeta o bucket. Es lo más rápido para arrancar la Fase 0.
2. **API o base de datos de la app**, si existe. Permite datos casi en tiempo real.
3. **Webhook o evento** al registrar una entrega o recogida. Es lo ideal para alertas inmediatas.
4. **Extensión de la app**: agregar un botón opcional de "foto de verificación". Solo en fases posteriores.

**Pregunta clave para el cliente:** ¿la app actual tiene API o exportación de datos? Esto define el cronograma de la Fase 1.

---

## 5. Arquitectura ajustada

```
┌────────────────────────────────────────────────────────┐
│ CAPA 1 · FUENTES DE DATOS (ya existen)                 │
│  App del conductor · ERP/WMS · Rutas y tiendas         │
└────────────────────────────────────────────────────────┘
                         ↓  (ingesta)
┌────────────────────────────────────────────────────────┐
│ CAPA 2 · DATOS                                         │
│  Almacén de eventos · Saldos por tienda · Histórico    │
└────────────────────────────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────┐
│ CAPA 3 · AGENTE RETORNA                                │
│  Conciliación en 3 vías · Detección de anomalías       │
│  Predicción de no retorno · Priorización de acciones   │
└────────────────────────────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────┐
│ CAPA 4 · ACCIÓN                                        │
│  Alertas al supervisor · Mensajes a tienda (WhatsApp)  │
│  Rutas de recogida · Tablero · Verificación por foto   │
└────────────────────────────────────────────────────────┘
```

**Diferencia clave:** la foto pasa de ser la fuente principal a ser **una herramienta de verificación** que el agente solicita solo cuando algo no cuadra o por muestreo.

---

## 6. Nuevo rol de la foto: verificación por muestreo

Como el conteo actual es autorreportado, hace falta una forma de **contrastarlo** sin añadirle trabajo a todos.

**Estrategia:**
- El agente solicita una **foto de verificación** solo en casos seleccionados:
  - tiendas con saldo anómalo,
  - visitas donde el conteo cambia de forma sospechosa,
  - un porcentaje aleatorio pequeño (por ejemplo 5% a 10% de las visitas) para mantener una verificación constante.
- Quien la toma puede ser el conductor, un supervisor o el mercaderista, según el caso.
- La visión por computador compara la foto con el conteo digitado y marca la diferencia.

**Beneficios:**
- Se verifica sin cargar a todo el equipo.
- El muestreo aleatorio funciona como **disuasión suave**: todos saben que cualquier visita puede ser verificada.
- Genera fotos reales etiquetadas para, más adelante, entrenar un modelo de visión propio.

**Cuidado con el enfoque:** no debe sentirse como vigilancia al conductor. Ver sección 12.

---

## 7. Qué hace el agente con los datos existentes

### 7.1 Conciliación en 3 vías
Se cruzan tres fuentes:
1. **Despachado** (lo que sale del centro de distribución).
2. **Reportado por el conductor** (entregas y recogidas digitadas en la app).
3. **Verificado** (fotos de muestreo y reportes de tienda).

Las diferencias entre las tres señalan en qué eslabón se pierde la bandeja.

### 7.2 Detección de anomalías
El agente compara a cada conductor, ruta y tienda contra su propio historial y contra sus pares. Ejemplo mínimo con pandas:

```python
import pandas as pd

def detectar_anomalias(df: pd.DataFrame, umbral_z: float = 2.0) -> pd.DataFrame:
    """
    df columnas: conductor, ruta, tienda, fecha, entregadas, recogidas
    Devuelve las filas con tasa de no retorno anómala dentro de su ruta.
    """
    df = df.copy()
    df["no_retorno"] = (df["entregadas"] - df["recogidas"]) / df["entregadas"].clip(lower=1)
    stats = df.groupby("ruta")["no_retorno"].agg(["mean", "std"]).rename(
        columns={"mean": "media", "std": "desv"}
    )
    df = df.join(stats, on="ruta")
    df["z"] = (df["no_retorno"] - df["media"]) / df["desv"].replace(0, 1)
    return df[df["z"] > umbral_z].sort_values("z", ascending=False)
```

Esto es una **señal para revisar**, no una acusación. Una tasa alta puede deberse a la ruta, la tienda o la temporada, no al conductor.

### 7.3 Predicción de no retorno
Un modelo simple (regresión o árboles) que estime la probabilidad de que una entrega termine sin retorno completo, usando: tienda, cadena, día, volumen entregado, historial de saldo y antigüedad del saldo. Sirve para **anticipar la visita de recogida** antes de que se acumule.

### 7.4 Priorización de acciones
El agente no solo avisa: **ordena dónde actuar primero**, por ejemplo por valor de bandejas en riesgo.

> "Estas 8 tiendas concentran el 60% de las bandejas acumuladas. Recomiendo recoger primero en la zona norte el jueves."

### 7.5 Acciones automáticas
- Mensaje a la tienda con el saldo y la fecha de recogida propuesta.
- Aviso al supervisor cuando una ruta supera el umbral.
- Propuesta de ruta de recogida agrupada por zona.
- Solicitud de foto de verificación cuando corresponde.

---

## 8. Fase 0: diagnóstico (antes de construir el sistema)

**Duración sugerida:** 2 semanas. **Objetivo:** entender el 20% con datos reales.

**Datos a pedir (idealmente 3 a 6 meses):**
- Entregas y recogidas por conductor, ruta, tienda y fecha.
- Catálogo de tiendas y cadenas.
- Despachos desde el centro de distribución.
- Cualquier registro de bandejas dañadas, perdidas o reclamadas.

**Análisis a realizar:**
1. **Línea base**: tasa de retorno el mismo día, a 7 días y a 30 días.
2. **Retraso vs. pérdida**: qué parte del 20% termina volviendo y qué parte se pierde de forma definitiva.
3. **Concentración**: qué porcentaje de la fuga explican las 10 peores rutas, conductores y tiendas.
4. **Patrones temporales**: por día de la semana y por temporada.
5. **Calidad del dato**: huecos, duplicados y correcciones tardías en la app.
6. **Valor económico**: costo de las bandejas que no retornan.

**Entregable:** un informe corto con las 3 a 5 causas principales y una lista priorizada de dónde actuar.

**Consulta de ejemplo (SQL):**

```sql
-- Tasa de no retorno por tienda en los últimos 90 días
SELECT
  t.nombre,
  t.cadena,
  SUM(e.entregadas)                                   AS entregadas,
  SUM(e.recogidas)                                    AS recogidas,
  ROUND(1 - SUM(e.recogidas)::numeric
            / NULLIF(SUM(e.entregadas), 0), 3)        AS tasa_no_retorno
FROM movimientos e
JOIN tiendas t ON t.id = e.tienda_id
WHERE e.fecha >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY t.nombre, t.cadena
ORDER BY tasa_no_retorno DESC
LIMIT 20;
```

---

## 9. Ajustes al modelo de datos

Agregar a las tablas del diseño original:

```sql
CREATE TABLE conductores (
  id SERIAL PRIMARY KEY,
  codigo TEXT UNIQUE NOT NULL,      -- usar código anónimo en análisis
  ruta_id INT
);

CREATE TABLE rutas (
  id SERIAL PRIMARY KEY,
  nombre TEXT,
  ciudad TEXT,
  zona TEXT
);

CREATE TABLE movimientos (          -- datos importados de la app del conductor
  id SERIAL PRIMARY KEY,
  origen_id TEXT,                   -- id del registro en la app original
  fecha DATE NOT NULL,
  tienda_id INT REFERENCES tiendas(id),
  conductor_id INT REFERENCES conductores(id),
  ruta_id INT REFERENCES rutas(id),
  entregadas INT NOT NULL,
  recogidas INT NOT NULL,
  importado_en TIMESTAMPTZ DEFAULT now(),
  UNIQUE (origen_id)                -- evita duplicados al reimportar
);

CREATE TABLE verificaciones (
  id SERIAL PRIMARY KEY,
  movimiento_id INT REFERENCES movimientos(id),
  motivo TEXT,                      -- muestreo, anomalia, saldo_alto
  cantidad_declarada INT,
  cantidad_vision INT,
  confianza NUMERIC(3,2),
  foto_url TEXT,
  creado_en TIMESTAMPTZ DEFAULT now()
);
```

Para el análisis se recomienda usar un **código de conductor anonimizado**, de modo que el diagnóstico se centre en patrones y no en personas.

---

## 10. Métricas y línea base

**Definiciones (acordarlas con el cliente desde el inicio):**

| Métrica | Fórmula |
|---|---|
| Tasa de no retorno (día) | `1 − recogidas / entregadas` en el mismo día |
| Tasa de retorno a 7 días | bandejas recuperadas en 7 días / entregadas |
| Pérdida definitiva | bandejas no recuperadas tras N días (definir N) |
| Saldo en tienda | entregadas acumuladas − recogidas acumuladas |
| Concentración | % de la fuga explicado por el 10% peor de rutas o tiendas |
| Precisión de la alerta | alertas confirmadas / alertas emitidas |

**Impacto económico (plantilla para rellenar con datos reales):**

```
Bandejas perdidas por año = bandejas_diarias × tasa_pérdida_definitiva × días_operados
Costo anual de reposición = bandejas perdidas por año × costo_unitario_bandeja
Ahorro estimado           = costo anual × reducción_lograda
```

**Metas:** no se fijan hasta tener la línea base de la Fase 0. Después se definen metas de reducción escalonadas por fase, y se miden contra esa línea base.

---

## 11. Plan ajustado

| Fase | Duración | Contenido | Resultado |
|---|---|---|---|
| **0. Diagnóstico** | 2 semanas | Análisis de datos existentes | Informe de causas y línea base |
| **1. Ingesta y conciliación** | 3 semanas | Conexión con la app, base de datos, conciliación en 3 vías | Tablero con saldos y diferencias |
| **2. Agente y alertas** | 3 semanas | Detección de anomalías, mensajes, priorización | Alertas útiles al supervisor |
| **3. Verificación por foto** | 2 semanas | Muestreo con visión por computador | Verificación independiente |
| **4. Piloto controlado** | 4 semanas | 1 ciudad, rutas seleccionadas, grupo de control | Medición de reducción de fuga |

**Grupo de control:** para demostrar impacto, se compara un grupo de rutas con RETORNA contra otro similar sin él durante el mismo periodo. Así se separa el efecto del sistema de otros factores.

---

## 12. Riesgos y consideraciones humanas

- **Percepción de vigilancia:** si los conductores sienten que se les audita, pueden dejar de registrar bien. Comunicar que el objetivo es **detectar fallas del proceso**, no sancionar personas.
- **Tratar las anomalías como señales:** una cifra alta no prueba una falta. Siempre requiere revisión humana.
- **Incentivos alineados:** reconocer a los conductores y tiendas con buen retorno funciona mejor que solo señalar a los peores.
- **Calidad del dato de origen:** si la app permite correcciones tardías o campos libres, el análisis se ensucia. Documentarlo en la Fase 0.
- **Privacidad y normativa laboral:** el análisis por conductor debe cumplir la normativa de datos personales (por ejemplo, la Ley 1581 de 2012 en Colombia) y las políticas internas. Validarlo con el área jurídica y de talento humano.
- **Dependencia de la integración:** si la app no ofrece datos, se retrasa la Fase 1. Tener el plan B de exportación manual.
- **Atribución del impacto:** sin grupo de control es difícil demostrar que la mejora viene de RETORNA.

---

## 13. Preguntas para aclarar con el cliente

1. ¿Qué app usan los conductores y quién la administra? ¿Tiene API o exportación?
2. ¿Qué es exactamente el "20% que no retorna": bandejas que vuelven tarde o pérdida definitiva?
3. ¿Cada cuánto visita un conductor la misma tienda?
4. ¿Existe un registro de bandejas dañadas o reclamadas a las tiendas?
5. ¿Qué dicen los acuerdos de consignación con las grandes superficies sobre bandejas perdidas?
6. ¿Cuál es el costo unitario de una bandeja y cuántas se mueven al día?
7. ¿Quién actuaría sobre las alertas: supervisores, el área comercial o logística?
8. ¿Hay restricciones para analizar datos por conductor?

---

## 14. Cambios a las instrucciones del LLM (`README_LLM_DESARROLLO.md`)

Si usas el README de desarrollo para un asistente de código, aplica estos ajustes:

1. **Nuevo PASO 0, Diagnóstico:** crear un notebook o script que cargue un CSV de movimientos (reales o sintéticos), calcule la línea base, el ranking de concentración y los patrones por día. Entregar un informe en `docs/diagnostico.md`.
2. **PASO 2:** agregar las tablas `conductores`, `rutas`, `movimientos` y `verificaciones` de la sección 9.
3. **PASO 3 (seed):** generar datos con una tasa de no retorno cercana al 20%, **concentrada en pocas rutas y tiendas** (por ejemplo, 3 rutas explican la mayor parte), con patrones por día de la semana.
4. **Nuevo paso, Ingesta:** `app/services/ingesta.py` que lea el CSV exportado de la app, valide columnas, evite duplicados con `origen_id` y registre filas rechazadas.
5. **PASO 4 (conciliación):** añadir la conciliación en 3 vías y las métricas de la sección 10 (tasa de no retorno, retorno a 7 días, concentración).
6. **Nuevo paso, Anomalías:** `app/services/anomalias.py` con la detección de la sección 7.2 y tests con el seed.
7. **PASO 6 (visión):** la visión se usa para **verificaciones por muestreo**, no como captura principal. Agregar la lógica que decide cuándo pedir una foto (anomalía, saldo alto o muestreo aleatorio).
8. **PASO 7 (herramientas):** agregar `consultar_anomalias`, `solicitar_verificacion` y `priorizar_recogidas`.
9. **PASO 13 (tablero):** incluir el ranking de concentración, la tasa de no retorno por ruta y el seguimiento de la línea base.

**Regla adicional para el LLM:** al presentar anomalías, usar siempre el código anónimo del conductor y un lenguaje neutral ("ruta con tasa atípica"), nunca conclusiones sobre personas.

---

## 15. Cómo contarlo en la presentación

**Problema:** cerca de 1 de cada 5 bandejas diarias no regresa, y hoy nadie sabe con precisión dónde ni por qué se pierde.

**Solución en una frase:**
> "No le pedimos nada nuevo al conductor: usamos los datos que ya registra para encontrar dónde se escapa cada bandeja, y un agente de IA que actúa antes de que se pierda."

**Tres mensajes clave:**
1. **Primero entendemos:** un diagnóstico con datos reales ubica el origen del 20%.
2. **Luego automatizamos:** un agente concilia, prioriza y avisa sin trabajo manual extra.
3. **Verificamos con evidencia:** fotos por muestreo contrastan el conteo sin cargar a todo el equipo.

**Lo que lo diferencia:** se integra con la operación actual, el cambio para el conductor es mínimo y el impacto se mide contra una línea base y un grupo de control.

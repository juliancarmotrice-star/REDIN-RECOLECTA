# RETORNA: guía para montar el piloto en GitHub

Agente de IA para trazabilidad, conciliación y logística inversa de bandejas en consignación (canal autoservicio / grandes superficies).

> Objetivo del piloto: demostrar en 4 a 6 semanas, con 3 a 5 tiendas, que el sistema concilia bandejas automáticamente y programa recogidas sin trabajo manual.

---

## 1. Alcance del piloto (MVP)

Lo que SÍ entra:
- Registro de entregas y recogidas por foto de pila de bandejas (vía WhatsApp).
- Conteo de bandejas por visión y comparación contra lo esperado.
- Conciliación automática: despachado vs. reportado vs. devuelto.
- Agente que avisa por WhatsApp al jefe de tienda y escala si no hay respuesta.
- Tablero web simple con el estado por tienda.
- Acta de entrega/recogida generada en PDF.

Lo que NO entra (fase 2):
- RFID/BLE, optimización avanzada de rutas, incentivos, integración real con ERP.

---

## 2. Stack recomendado

| Capa | Tecnología | Por qué |
|---|---|---|
| Backend / API | Python + FastAPI | Rápido de montar, ideal para IA |
| Agente | Claude API (Anthropic SDK) con tool use | Razonamiento, visión y herramientas en una sola API |
| Base de datos | PostgreSQL (Supabase o Docker local) | Relacional, gratis para piloto |
| Mensajería | WhatsApp Cloud API (Meta) | Sin apps nuevas para el usuario |
| Tablero | Next.js o Streamlit | Streamlit es más rápido para un piloto |
| Tareas programadas | APScheduler o cron | Alertas y recogidas programadas |
| Despliegue | Docker + Railway / Render / Fly.io | Barato y simple |
| CI | GitHub Actions | Tests y lint automáticos |

Para el piloto, usa la visión del propio modelo para contar bandejas y no entrenes un modelo propio. Cuando tengas fotos reales etiquetadas, evalúas si conviene entrenar uno especializado (YOLO).

---

## 3. Estructura del repositorio

```
retorna/
├── README.md
├── docker-compose.yml
├── .env.example
├── .github/
│   ├── workflows/ci.yml
│   └── ISSUE_TEMPLATE/
├── docs/
│   ├── arquitectura.md
│   ├── flujo-conductor.md
│   └── decisiones.md          # ADRs: por qué elegiste cada cosa
├── app/
│   ├── main.py                # FastAPI
│   ├── config.py
│   ├── db/
│   │   ├── models.py
│   │   ├── schema.sql
│   │   └── seed.py            # datos sintéticos
│   ├── api/
│   │   ├── whatsapp.py        # webhook
│   │   ├── tiendas.py
│   │   └── reportes.py
│   ├── agent/
│   │   ├── core.py            # bucle del agente
│   │   ├── prompts.py         # system prompt
│   │   ├── tools.py           # definiciones de herramientas
│   │   └── handlers.py        # implementación de cada herramienta
│   ├── services/
│   │   ├── vision.py          # conteo de bandejas por foto
│   │   ├── conciliacion.py    # reglas de negocio
│   │   ├── rutas.py           # agrupar recogidas
│   │   └── actas.py           # PDF
│   └── jobs/
│       └── scheduler.py       # revisiones diarias
├── dashboard/                 # Streamlit o Next.js
├── tests/
│   ├── test_conciliacion.py
│   ├── test_agent_tools.py
│   └── fixtures/              # fotos de ejemplo
└── scripts/
    └── simular_conductor.py   # simula mensajes sin WhatsApp real
```

---

## 4. Modelo de datos (mínimo)

```sql
CREATE TABLE tiendas (
  id SERIAL PRIMARY KEY,
  nombre TEXT NOT NULL,
  cadena TEXT,
  ciudad TEXT,
  contacto_nombre TEXT,
  contacto_whatsapp TEXT
);

CREATE TABLE eventos (
  id SERIAL PRIMARY KEY,
  tienda_id INT REFERENCES tiendas(id),
  tipo TEXT CHECK (tipo IN ('entrega','recogida','conteo')),
  cantidad_declarada INT,
  cantidad_vision INT,
  confianza NUMERIC(3,2),
  foto_url TEXT,
  reportado_por TEXT,          -- conductor, jefe de tienda
  creado_en TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE saldos (
  tienda_id INT PRIMARY KEY REFERENCES tiendas(id),
  bandejas_estimadas INT,
  dias_en_consignacion INT,
  ultima_actualizacion TIMESTAMPTZ
);

CREATE TABLE alertas (
  id SERIAL PRIMARY KEY,
  tienda_id INT REFERENCES tiendas(id),
  tipo TEXT,                   -- diferencia, vencida, sin_respuesta
  detalle TEXT,
  estado TEXT DEFAULT 'abierta',
  creado_en TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE mensajes (
  id SERIAL PRIMARY KEY,
  tienda_id INT REFERENCES tiendas(id),
  direccion TEXT,              -- entrante, saliente
  contenido TEXT,
  creado_en TIMESTAMPTZ DEFAULT now()
);
```

Regla de oro: el saldo se calcula a partir de eventos. No se edita a mano, así queda trazabilidad completa.

---

## 5. Diseño del agente

### 5.1 Responsabilidades
1. Interpretar mensajes entrantes (texto o foto) de conductores y tiendas.
2. Registrar eventos usando herramientas, sin inventar datos.
3. Detectar diferencias y decidir si abrir una alerta.
4. Redactar y enviar mensajes a las tiendas.
5. Proponer recogidas agrupadas por zona.

### 5.2 Herramientas (tools) que debe tener

| Herramienta | Qué hace |
|---|---|
| `contar_bandejas_foto` | Envía la foto a visión y devuelve conteo y confianza |
| `registrar_evento` | Guarda entrega, recogida o conteo |
| `consultar_saldo_tienda` | Devuelve bandejas estimadas y días de consignación |
| `listar_tiendas_vencidas` | Tiendas con más de N días o más de X bandejas |
| `crear_alerta` | Abre una alerta de diferencia o vencimiento |
| `enviar_whatsapp` | Envía mensaje a una tienda |
| `programar_recogida` | Agrupa tiendas por zona y fecha |
| `generar_acta` | Crea el PDF de entrega o recogida |

### 5.3 Definición de una herramienta (ejemplo)

```python
# app/agent/tools.py
TOOLS = [
    {
        "name": "registrar_evento",
        "description": "Registra una entrega, recogida o conteo de bandejas en una tienda.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tienda_id": {"type": "integer"},
                "tipo": {"type": "string", "enum": ["entrega", "recogida", "conteo"]},
                "cantidad_declarada": {"type": "integer"},
                "cantidad_vision": {"type": "integer"},
                "confianza": {"type": "number"},
                "reportado_por": {"type": "string"},
            },
            "required": ["tienda_id", "tipo"],
        },
    },
    # ... resto de herramientas
]
```

### 5.4 Bucle del agente

```python
# app/agent/core.py
import json
import anthropic
from .prompts import SYSTEM_PROMPT
from .tools import TOOLS
from .handlers import dispatch

client = anthropic.Anthropic()          # lee ANTHROPIC_API_KEY del entorno
MODEL = "claude-sonnet-5-5"             # verifica el nombre vigente en docs.claude.com

def run_agent(messages: list, max_turns: int = 8) -> str:
    for _ in range(max_turns):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text")

        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                try:
                    out = dispatch(block.name, block.input)
                except Exception as e:
                    out = {"error": str(e)}
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(out, default=str),
                })
        messages.append({"role": "user", "content": results})
    return "No pude completar la tarea; escalo a un humano."
```

### 5.5 System prompt (punto de partida)

```python
# app/agent/prompts.py
SYSTEM_PROMPT = """
Eres RETORNA, un agente que gestiona la trazabilidad de bandejas en consignación
en grandes superficies. Hablas en español, de forma breve y cordial.

Reglas:
- Nunca inventes cantidades, tiendas ni fechas: usa siempre las herramientas.
- Si una foto tiene confianza menor a 0.7, pide una segunda foto antes de registrar.
- Si la diferencia entre lo declarado y lo contado por visión es mayor a 10%,
  crea una alerta y avisa al responsable.
- Antes de enviar un mensaje a una tienda, confirma el saldo actual.
- Si no tienes información suficiente, pregunta una sola cosa clara.
- Acciones irreversibles o de alto impacto (por ejemplo, reclamar bandejas
  perdidas) las propones, no las ejecutas: requieren aprobación humana.
"""
```

### 5.6 Visión: contar bandejas con el modelo

```python
# app/services/vision.py
import base64, json, anthropic

client = anthropic.Anthropic()

def contar_bandejas(image_bytes: bytes, esperado: int | None = None) -> dict:
    b64 = base64.standard_b64encode(image_bytes).decode()
    pregunta = (
        "Cuenta las bandejas apiladas en la imagen. Responde SOLO con JSON: "
        '{"cantidad": int, "confianza": 0-1, "observaciones": str}. '
        "Indica baja confianza si hay bandejas ocultas o la foto es borrosa."
    )
    if esperado is not None:
        pregunta += f" Se espera aproximadamente {esperado}."
    resp = client.messages.create(
        model="claude-sonnet-5-5",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image",
                 "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": pregunta},
            ],
        }],
    )
    return json.loads(resp.content[0].text)
```

### 5.7 Conciliación: reglas de negocio (código, no IA)

Esta parte debe ser determinista y testeable. El agente decide qué hacer con el resultado, pero no calcula los números.

```python
# app/services/conciliacion.py
def conciliar(despachado: int, contado_vision: int, devuelto: int, tolerancia=0.10):
    esperado_en_tienda = despachado - devuelto
    if esperado_en_tienda <= 0:
        return {"estado": "ok", "diferencia": 0}
    diff = esperado_en_tienda - contado_vision
    pct = abs(diff) / esperado_en_tienda
    return {
        "estado": "ok" if pct <= tolerancia else "alerta",
        "diferencia": diff,
        "porcentaje": round(pct, 3),
    }
```

---

## 6. Integración con WhatsApp

1. Crea una app en Meta for Developers y activa WhatsApp Cloud API (te dan un número de prueba).
2. Expón tu webhook (`/webhook/whatsapp`). En desarrollo usa `ngrok` o `cloudflared`.
3. Verifica el webhook (Meta envía un `hub.challenge`).
4. Al recibir un mensaje: identifica al remitente, descarga la imagen si la hay, arma el historial y llama a `run_agent`.
5. Responde con la API de envío de mensajes.

Para no depender de WhatsApp desde el día 1, crea `scripts/simular_conductor.py`, que envía mensajes y fotos de ejemplo directamente a tu endpoint. Así desarrollas y haces pruebas sin esperar aprobaciones.

---

## 7. Plan de trabajo por sprints (6 semanas)

### Sprint 0 (3 días): cimientos
- [ ] Crear repo, `README`, licencia, `.gitignore`, `.env.example`.
- [ ] Configurar `docker-compose` con Postgres + API.
- [ ] Configurar CI básico con lint y tests.

### Sprint 1 (semana 1): datos y conciliación
- [ ] Esquema de BD y `seed.py` con 5 tiendas y 30 días de eventos sintéticos.
- [ ] Servicio de conciliación con tests unitarios.
- [ ] Endpoint `GET /tiendas/{id}/saldo`.

### Sprint 2 (semana 2): visión
- [ ] Servicio `contar_bandejas`.
- [ ] Reunir 30 a 50 fotos reales o simuladas de pilas de bandejas.
- [ ] Medir error de conteo y definir umbral de confianza.

### Sprint 3 (semanas 3-4): agente
- [ ] Definir herramientas y handlers.
- [ ] Bucle del agente y system prompt.
- [ ] Pruebas con conversaciones simuladas (conductor entrega, tienda reporta, hay diferencia).
- [ ] Integrar webhook de WhatsApp.

### Sprint 4 (semana 5): automatización y salidas
- [ ] Job diario que detecta tiendas vencidas y notifica.
- [ ] Generación de actas en PDF.
- [ ] Agrupación simple de recogidas por ciudad o zona.

### Sprint 5 (semana 6): tablero y piloto
- [ ] Dashboard: saldo por tienda, alertas abiertas, historial.
- [ ] Prueba end-to-end con 3 a 5 tiendas reales.
- [ ] Medir métricas y documentar resultados.

---

## 8. Métricas para evaluar el piloto

| Métrica | Meta sugerida |
|---|---|
| Error de conteo por visión | menor a 10% en pilas visibles |
| Tiempo de conciliación | de semanas a minutos |
| Tiempo del conductor por tienda | menor a 2 minutos extra |
| Alertas útiles (no falsos positivos) | mayor a 80% |
| Bandejas recuperadas vs. línea base | tu criterio de éxito principal |
| Respuesta de tienda a mensajes del agente | mayor a 70% en 24 h |

Define la línea base antes de arrancar: cuántas bandejas hay hoy en las tiendas piloto y cuánto tarda hoy una conciliación manual.

---

## 9. Pruebas

- Unitarias: reglas de conciliación (muchos casos de borde).
- De herramientas: cada handler con BD de prueba.
- De agente: un set de 15 a 20 conversaciones esperadas y qué herramientas debería llamar el agente en cada una.
- De visión: conjunto fijo de fotos con conteo real conocido.
- Registra cada llamada del agente (entrada, herramientas, salida) para poder revisar errores.

---

## 10. Seguridad y buenas prácticas

- Nunca subas llaves al repo: usa `.env` y secretos de GitHub.
- Valida la firma de los webhooks de WhatsApp.
- Guarda solo los datos necesarios del personal (nombre y número de contacto).
- Limita permisos del agente: solo las herramientas definidas, sin acceso libre a la BD.
- Pon un límite de turnos y de costo por conversación.
- Mantén a un humano en el circuito para acciones con impacto comercial.

---

## 11. Variables de entorno (`.env.example`)

```
ANTHROPIC_API_KEY=
DATABASE_URL=postgresql://retorna:retorna@db:5432/retorna
WHATSAPP_TOKEN=
WHATSAPP_PHONE_ID=
WHATSAPP_VERIFY_TOKEN=
APP_ENV=dev
```

---

## 12. Cómo presentarlo en GitHub

- `README` con: problema, diagrama de arquitectura, demo en GIF y cómo correrlo con `docker compose up`.
- Carpeta `docs/decisiones.md` con las decisiones clave (por qué foto por pila, por qué visión del modelo en el piloto).
- Tablero de Projects con los sprints de la sección 7 como issues y milestones.
- Etiquetas: `agente`, `visión`, `backend`, `dashboard`, `datos`.
- Un release `v0.1-piloto` al final de la semana 6.

---

## 13. Próximos pasos inmediatos

1. Crear el repositorio y la estructura de carpetas.
2. Levantar Postgres con `docker compose` y cargar datos sintéticos.
3. Programar la conciliación y sus tests (es lo más seguro de avanzar sin depender de nada externo).
4. Probar la visión con 10 fotos.
5. Armar el agente con 3 herramientas (`consultar_saldo_tienda`, `registrar_evento`, `crear_alerta`) antes de agregar las demás.

Empieza pequeño: un agente con 3 herramientas que funcione bien vale más que uno con 8 que falle.

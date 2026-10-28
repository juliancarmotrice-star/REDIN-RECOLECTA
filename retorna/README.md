# RETORNA

Agente de IA para trazabilidad, conciliación y logística inversa de bandejas en consignación (canal autoservicio / grandes superficies).

## 🚀 Inicio rápido

### 1. Instalar dependencias

```bash
cd retorna
pip install -r requirements.txt
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Edita .env y agrega tu ANTHROPIC_API_KEY
```

### 3. Poblar la base de datos con datos de prueba

```bash
python -m app.db.seed
```

### 4. Levantar el servidor

```bash
uvicorn app.main:app --reload
```

Abre http://localhost:8000 para ver el dashboard.

### 5. Probar el agente (terminal)

```bash
python -m scripts.simular_conductor
```

## 📡 API Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/ping` | Health check |
| GET | `/api/tiendas` | Lista todas las tiendas con saldo |
| GET | `/api/tiendas/criticas` | Tiendas con saldo o tasa alarmante |
| GET | `/api/tiendas/{id}/saldo` | Saldo de una tienda |
| GET | `/api/tiendas/{id}/historial` | Historial de movimientos |
| GET | `/api/alertas` | Alertas abiertas |
| POST | `/api/alertas/{id}/resolver` | Resolver una alerta |
| POST | `/api/agent/chat` | Enviar mensaje al agente |

## 🏗️ Estructura

```
retorna/
├── app/
│   ├── main.py              # FastAPI + Dashboard
│   ├── config.py             # Configuración
│   ├── dashboard.html        # Interfaz web
│   ├── db/
│   │   ├── models.py         # SQLAlchemy models
│   │   └── seed.py           # Datos sintéticos
│   ├── services/
│   │   └── conciliacion.py   # Reglas de negocio
│   └── agent/
│       ├── core.py           # Bucle del agente
│       ├── prompts.py        # System prompt
│       ├── tools.py          # Definición de herramientas
│       └── handlers.py       # Implementación de herramientas
├── scripts/
│   └── simular_conductor.py  # Simulador de conversación
└── tests/
    └── test_conciliacion.py  # Tests unitarios
```

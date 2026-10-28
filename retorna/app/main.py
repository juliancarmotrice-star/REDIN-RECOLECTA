"""
RETORNA — API principal con FastAPI.

Endpoints:
- /ping                              -> health check
- /api/proveedores                   -> CRUD proveedores
- /api/entregas                      -> lista entregas
- /api/recogidas                     -> lista recogidas
- /api/resumen/tiendas               -> saldo por tienda
- /api/resumen/proveedores           -> saldo por proveedor
- /api/resumen/criticas              -> tiendas criticas
- /api/agent/chat                    -> enviar mensaje al agente
- /                                  -> dashboard web
"""

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from datetime import datetime
import os

from app.db.supabase_client import db
from app.services.conciliacion import (
    conciliar_tienda,
    conciliar_transportador,
    conciliar_proveedor,
    resumen_por_tienda,
    resumen_por_transportador,
    resumen_por_proveedor,
    tiendas_criticas,
)

app = FastAPI(
    title="RETORNA",
    description="Agente de IA para trazabilidad de canastas en consignacion",
    version="0.1.0",
)


# ─── Health ───

@app.get("/ping")
def ping():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ─── Transportadores (CRUD completo con alias Proveedores) ───

@app.get("/api/transportadores")
@app.get("/api/proveedores")
def api_listar_transportadores():
    return db.listar_transportadores()


@app.get("/api/transportadores/{id_transportador}")
@app.get("/api/proveedores/{id_transportador}")
def api_obtener_transportador(id_transportador: int):
    prov = db.obtener_transportador(id_transportador)
    if not prov:
        return JSONResponse(status_code=404, content={"error": "Transportador no encontrado"})
    return prov


@app.post("/api/transportadores")
@app.post("/api/proveedores")
async def api_crear_transportador(request: Request):
    body = await request.json()
    nombre = body.get("nombre_transportador") or body.get("nombre_proveedor")
    if not nombre:
        return JSONResponse(status_code=400, content={"error": "Campo requerido: nombre_transportador"})
    try:
        result = db.crear_transportador(body)
        return JSONResponse(status_code=201, content=result)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.put("/api/transportadores/{id_transportador}")
@app.put("/api/proveedores/{id_transportador}")
async def api_actualizar_transportador(id_transportador: int, request: Request):
    body = await request.json()
    try:
        result = db.actualizar_transportador(id_transportador, body)
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.delete("/api/transportadores/{id_transportador}")
@app.delete("/api/proveedores/{id_transportador}")
def api_eliminar_transportador(id_transportador: int, cascade: bool = False):
    import httpx
    try:
        db.eliminar_transportador(id_transportador, cascade=cascade)
        return {"eliminado": True, "id_transportador": id_transportador, "id_proveedor": id_transportador}
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 409:
            return JSONResponse(
                status_code=409,
                content={
                    "error": "No se puede eliminar el transportador porque tiene entregas o recogidas asociadas en Supabase.",
                    "code": "FOREIGN_KEY_VIOLATION",
                    "can_cascade": True,
                },
            )
        return JSONResponse(status_code=500, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ─── Entregas y Recogidas ───

@app.get("/api/entregas")
def api_listar_entregas():
    return db.listar_entregas()


@app.post("/api/entregas")
async def api_registrar_entrega(request: Request):
    body = await request.json()
    try:
        result = db.registrar_entrega(body)
        return JSONResponse(status_code=201, content=result)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/recogidas")
def api_listar_recogidas():
    return db.listar_recogidas()


@app.post("/api/recogidas")
async def api_registrar_recogida(request: Request):
    body = await request.json()
    try:
        result = db.registrar_recogida(body)
        return JSONResponse(status_code=201, content=result)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ─── Resumen / Conciliacion ───

@app.get("/api/resumen/tiendas")
def api_resumen_tiendas():
    return resumen_por_tienda()


@app.get("/api/resumen/transportadores")
@app.get("/api/resumen/proveedores")
def api_resumen_transportadores():
    return resumen_por_transportador()


@app.get("/api/resumen/criticas")
def api_resumen_criticas():
    return tiendas_criticas()


@app.get("/api/resumen/tienda/{nombre_tienda}")
def api_saldo_tienda(nombre_tienda: str):
    return conciliar_tienda(nombre_tienda)


# ─── Agente ───

@app.post("/api/agent/chat")
async def api_agent_chat(request: Request):
    body = await request.json()
    user_message = body.get("message", "")

    if not user_message:
        return JSONResponse(status_code=400, content={"error": "Mensaje vacio"})

    try:
        from app.agent.core import run_agent

        messages = [{"role": "user", "content": user_message}]
        result = run_agent(messages)

        return {
            "response": result["response"],
            "tools_used": [
                {"tool": t["tool"], "input": t["input"]}
                for t in result["tools_used"]
            ],
        }
    except ValueError as e:
        return JSONResponse(
            status_code=503,
            content={
                "error": str(e),
                "hint": "Configura ANTHROPIC_API_KEY en el archivo .env",
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Error del agente: {str(e)}"},
        )


# ─── Telegram Bot Webhook & Status ───

@app.get("/api/telegram/status")
def api_telegram_status():
    from app.telegram.bot import telegram_bot
    info = telegram_bot.get_me() if telegram_bot.is_configured else None
    return {
        "configured": telegram_bot.is_configured,
        "bot_info": info,
        "token_prefix": f"{telegram_bot.token[:8]}..." if telegram_bot.token else None,
    }


@app.post("/api/telegram/webhook")
async def api_telegram_webhook(request: Request):
    from app.telegram.bot import telegram_bot
    try:
        update = await request.json()
        result = telegram_bot.process_update(update)
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.delete("/api/entregas/{id_entrega}")
def api_eliminar_entrega(id_entrega: int):
    try:
        db.delete("entregas", "id_entrega", id_entrega)
        return {"eliminado": True, "id_entrega": id_entrega}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.delete("/api/recogidas/{id_recogida}")
def api_eliminar_recogida(id_recogida: int):
    try:
        db.delete("recogidas", "id_recogida", id_recogida)
        return {"eliminado": True, "id_recogida": id_recogida}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ─── Visión por Computadora / Conteo de Canastas por Foto ───

@app.post("/api/vision/contar")
async def api_vision_contar(file: UploadFile = File(...)):
    from app.services.vision import contar_canastas_en_imagen
    try:
        contents = await file.read()
        mime = file.content_type or "image/jpeg"
        resultado = contar_canastas_en_imagen(contents, mime_type=mime)
        return resultado
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ─── Dashboard HTML ───

@app.get("/logo-bimbo.png")
def logo_bimbo():
    path = os.path.join(os.path.dirname(__file__), "logo-bimbo.png")
    return FileResponse(path, media_type="image/png")


@app.get("/", response_class=HTMLResponse)
def dashboard():
    html_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>RETORNA</h1><p>Dashboard no encontrado.</p>"

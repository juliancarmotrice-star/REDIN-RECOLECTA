"""
RETORNA — Bucle principal del agente.

Recibe mensajes, llama a Claude con tool use, ejecuta herramientas
y devuelve la respuesta final.
"""

import json
import anthropic

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import TOOLS
from app.agent.handlers import dispatch
from app.config import settings


def get_client():
    """Crea el cliente de Anthropic. Falla claro si no hay API key."""
    if not settings.anthropic_api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY no configurada. "
            "Agrégala en tu archivo .env o como variable de entorno."
        )
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def run_agent(messages: list, max_turns: int = 8) -> dict:
    """
    Ejecuta el bucle del agente.

    Args:
        messages: historial de la conversación en formato Anthropic.
        max_turns: máximo de iteraciones tool_use antes de rendirse.

    Returns:
        dict con:
            - response: texto final del agente
            - tools_used: lista de herramientas usadas en esta ejecución
            - messages: historial actualizado
    """
    client = get_client()
    tools_used = []

    for turn in range(max_turns):
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Si el modelo terminó (no pidió herramientas), extraer texto y salir
        if resp.stop_reason != "tool_use":
            text = "".join(
                block.text for block in resp.content if block.type == "text"
            )
            return {
                "response": text,
                "tools_used": tools_used,
                "messages": messages,
            }

        # Agregar la respuesta del asistente al historial
        messages.append({"role": "assistant", "content": resp.content})

        # Ejecutar cada herramienta solicitada
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input

                try:
                    output = dispatch(tool_name, tool_input)
                except Exception as e:
                    output = {"error": str(e)}

                tools_used.append({
                    "tool": tool_name,
                    "input": tool_input,
                    "output": output,
                })

                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(output, default=str, ensure_ascii=False),
                })

        # Agregar resultados al historial
        messages.append({"role": "user", "content": results})

    # Se agotaron los turnos
    return {
        "response": "No pude completar la tarea en el número máximo de pasos. Escalo a un humano.",
        "tools_used": tools_used,
        "messages": messages,
    }

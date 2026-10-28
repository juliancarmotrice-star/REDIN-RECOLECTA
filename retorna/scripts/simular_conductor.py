"""
RETORNA — Simulador de conversación con el agente.

Permite probar el agente sin WhatsApp, directamente desde la terminal.
Uso: python -m scripts.simular_conductor
"""

import sys
import os

# Asegurar que el path del proyecto esté disponible
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.supabase_client import db
from app.agent.core import run_agent


def main():
    try:
        provs = db.listar_transportadores()
        print(f"  ⚡ Conectado a Supabase ({len(provs)} transportadores encontrados)")
    except Exception as e:
        print(f"  ⚠️ Error de conexión a Supabase: {e}")

    print("=" * 60)
    print("  🔄 RETORNA — Simulador de Conversación")
    print("=" * 60)
    print()
    print("  Habla con el agente RETORNA como si fueras un conductor")
    print("  o supervisor. Escribe 'salir' para terminar.")
    print()
    print("  Ejemplos de preguntas:")
    print("  • ¿Cuál es el saldo de la tienda 1?")
    print("  • Acabo de entregar 25 bandejas en la tienda 3")
    print("  • ¿Cuáles son las tiendas más críticas?")
    print("  • Recogí 10 bandejas de la tienda 5")
    print("  • Muéstrame el historial de Éxito Calle 80")
    print()
    print("-" * 60)

    messages = []

    while True:
        try:
            user_input = input("\n👤 Tú: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input:
            continue
        if user_input.lower() in ("salir", "exit", "quit"):
            break

        messages.append({"role": "user", "content": user_input})

        print("\n⏳ Pensando...", end="", flush=True)

        try:
            result = run_agent(messages)
            print("\r" + " " * 20 + "\r", end="")  # limpiar "Pensando..."

            # Mostrar herramientas usadas
            if result["tools_used"]:
                tools = [t["tool"] for t in result["tools_used"]]
                print(f"  🔧 Herramientas: {', '.join(tools)}")

            print(f"\n🤖 RETORNA: {result['response']}")

            # Actualizar historial
            messages = result["messages"]
            messages.append({"role": "assistant", "content": result["response"]})

        except ValueError as e:
            print(f"\r\n⚠️  {e}")
            print("   Configura ANTHROPIC_API_KEY en tu archivo .env")
            messages.pop()  # quitar el mensaje que no se procesó

        except Exception as e:
            print(f"\r\n❌ Error: {e}")
            messages.pop()

    print("\n👋 ¡Hasta luego!")


if __name__ == "__main__":
    main()

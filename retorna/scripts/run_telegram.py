"""
RETORNA — Script para ejecutar el bot de Telegram en modo Polling.

Uso:
    python scripts/run_telegram.py

Requiere haber configurado TELEGRAM_BOT_TOKEN en el archivo .env.
"""

import sys
import os

# Forzar UTF-8 en la terminal de Windows para evitar errores con emojis
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Asegurar path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.telegram.bot import telegram_bot


def main():
    print("=" * 60)
    print("  ✈️ RETORNA — Bot de Telegram (Polling)")
    print("=" * 60)
    print(f"  • Supabase URL: {settings.supabase_url}")

    if not telegram_bot.is_configured:
        print("\n  ⚠️ TELEGRAM_BOT_TOKEN no está configurado en .env.")
        print("  Pasos:")
        print("  1. Abre Telegram y habla con @BotFather")
        print("  2. Escribe /newbot y sigue las instrucciones")
        print("  3. Copia el token generado")
        print("  4. Agrega a tu archivo .env:")
        print("     TELEGRAM_BOT_TOKEN=tu_token_aqui")
        print("=" * 60)
        return

    info = telegram_bot.get_me()
    if info:
        print(f"  ✅ Bot conectado: @{info.get('username')} ({info.get('first_name')})")
    else:
        print("  ⚠️ No se pudo verificar el bot con Telegram. Revisa el token.")

    print("\n  Escuchando mensajes... (Presiona Ctrl+C para detener)")
    telegram_bot.poll_forever()


if __name__ == "__main__":
    main()

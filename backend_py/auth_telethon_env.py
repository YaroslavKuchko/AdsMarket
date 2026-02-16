#!/usr/bin/env python3
"""
Telethon session authorization script.
Uses .env (PYROGRAM_API_ID, PYROGRAM_API_HASH, PYROGRAM_PHONE).
Run interactively: cd backend_py && python auth_telethon_env.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load env before importing app
from dotenv import load_dotenv
load_dotenv()

from telethon import TelegramClient
from app.core.config import settings


async def main():
    api_id = settings.pyrogram_api_id
    api_hash = settings.pyrogram_api_hash
    phone = (settings.pyrogram_phone or "").strip() or None
    session_dir = settings.pyrogram_session_dir or "sessions"
    session_path = f"{session_dir}/telethon_session"

    if not api_id or not api_hash:
        print("❌ PYROGRAM_API_ID and PYROGRAM_API_HASH must be set in .env")
        return 1

    os.makedirs(session_dir, exist_ok=True)

    client = TelegramClient(session_path, api_id, api_hash)

    await client.connect()

    if not await client.is_user_authorized():
        phone = phone or input("Enter phone (e.g. +79991234567): ").strip()
        if not phone:
            print("Phone required")
            return 1

        print(f"\n📱 Sending code to {phone}...")
        await client.send_code_request(phone)

        code = input("Enter the code from Telegram: ").strip()
        if not code:
            print("Code required")
            return 1

        try:
            await client.sign_in(phone, code)
        except Exception as e:
            err = str(e).lower()
            if "two-step" in err or "2fa" in err or "password" in err:
                password = input("Enter 2FA password: ")
                await client.sign_in(password=password)
            else:
                raise

    me = await client.get_me()
    print(f"\n✅ Authorized as: {me.first_name} (@{me.username})")
    print(f"   Session: {session_path}.session")
    print("\n🎉 Stats collection (Telethon) will now work. Restart backend if needed.")

    await client.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)

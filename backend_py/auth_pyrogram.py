#!/usr/bin/env python3
"""
First-time Pyrogram authentication script.

Run this once to create the session file.
After that, the backend will use the session automatically.
"""
import asyncio
import os
import sys

# Fix for Python 3.10+ asyncio changes
if sys.version_info >= (3, 10):
    import asyncio
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from pyrogram import Client


async def main():
    api_id = os.getenv("PYROGRAM_API_ID")
    api_hash = os.getenv("PYROGRAM_API_HASH")
    phone = os.getenv("PYROGRAM_PHONE")

    if not api_id or not api_hash:
        print("❌ PYROGRAM_API_ID and PYROGRAM_API_HASH must be set in .env")
        return

    print("🔐 Pyrogram Authentication")
    print(f"   API ID: {api_id}")
    print(f"   Phone: {phone or 'Not set (will ask)'}")
    print()

    # Create sessions directory
    os.makedirs("sessions", exist_ok=True)

    client = Client(
        name="stats_collector",
        api_id=int(api_id),
        api_hash=api_hash,
        phone_number=phone or None,
        workdir="./sessions",
    )

    print("📱 Starting authentication...")
    print("   You will receive a code in Telegram. Enter it when prompted.")
    print()

    try:
        async with client:
            me = await client.get_me()
            print()
            print("✅ Authentication successful!")
            print(f"   Logged in as: {me.first_name} (@{me.username})")
            print(f"   User ID: {me.id}")
            print()
            print("🎉 Session saved! The backend can now collect channel statistics.")
            print("   Restart the backend to start collecting stats.")
    except Exception as e:
        error_str = str(e)
        if "FLOOD_WAIT" in error_str or "FloodWait" in error_str:
            # Extract wait time
            import re
            match = re.search(r'(\d+) seconds', error_str)
            wait_time = int(match.group(1)) if match else 60
            
            print(f"⏳ Telegram rate limit! Need to wait {wait_time} seconds.")
            print(f"   Run this script again in {wait_time // 60} min {wait_time % 60} sec.")
        else:
            print(f"❌ Error: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())


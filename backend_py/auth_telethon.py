"""Telethon authorization script."""
import asyncio
from telethon import TelegramClient

API_ID = 10556434
API_HASH = "f032c46249e14f3bf2b35027995e41ae"
PHONE = "+375298205205"
SESSION_PATH = "sessions/telethon_session"

async def main():
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    
    await client.connect()
    
    if not await client.is_user_authorized():
        print(f"Sending code to {PHONE}...")
        await client.send_code_request(PHONE)
        
        code = input("Enter the code from Telegram: ")
        
        try:
            await client.sign_in(PHONE, code)
        except Exception as e:
            if "Two-step verification" in str(e) or "password" in str(e).lower():
                password = input("Enter 2FA password: ")
                await client.sign_in(password=password)
            else:
                raise
    
    me = await client.get_me()
    print(f"\n✅ Authorized as: {me.first_name} (@{me.username})")
    print(f"Session saved to: {SESSION_PATH}.session")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

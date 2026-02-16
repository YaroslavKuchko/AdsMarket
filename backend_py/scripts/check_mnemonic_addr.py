#!/usr/bin/env python3
"""
Локальная проверка: какая деривация мнемоники даёт нужный адрес кошелька.
Запуск: cd backend_py && .venv/bin/python scripts/check_mnemonic_addr.py
"""
import asyncio
import hashlib
import hmac
import os
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# NEVER commit real mnemonic! Use env: MNEMONIC="..." TARGET_ADDR="UQ..."
MNEMONIC = (os.environ.get("MNEMONIC") or "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12 word13 word14 word15 word16 word17 word18 word19 word20 word21 word22 word23 word24").strip().lower().split()
TARGET_ADDR = os.environ.get("TARGET_ADDR", "UQ...")
PBKDF_ITERATIONS = 100000


def addr_eq(a: str, b: str) -> bool:
    """Сравнение адресов (UQ/EQ — разные форматы одного адреса)."""
    try:
        from pytoniq_core.boc.address import Address
        return Address(a).hash_part == Address(b).hash_part and Address(a).wc == Address(b).wc
    except Exception:
        return a.replace("-", "").lower() == b.replace("-", "").lower()


def custom_derivation(words: list[str], hmac_key_first: bool):
    """Ручная деривация: entropy через HMAC, затем PBKDF2 + TON default seed. Возвращает private_key (64 bytes для Ed25519)."""
    from nacl.bindings import crypto_sign_seed_keypair

    joined = " ".join(words)
    if hmac_key_first:
        entropy = hmac.new(
            joined.encode("utf-8"), b"", hashlib.sha512
        ).digest()
    else:
        entropy = hmac.new(
            b"", joined.encode("utf-8"), hashlib.sha512
        ).digest()
    seed = hashlib.pbkdf2_hmac(
        "sha512", entropy, b"TON default seed", PBKDF_ITERATIONS
    )
    _, priv_k = crypto_sign_seed_keypair(seed[:32])
    return priv_k


async def test_private_key(priv_k: bytes, provider, target_addr: str) -> list[tuple[str, str, bool]]:
    from pytoniq import WalletV3R1, WalletV3R2, WalletV4R2

    results = []
    for version_name, wallet_cls in [
        ("v4r2", WalletV4R2),
        ("v3r2", WalletV3R2),
        ("v3r1", WalletV3R1),
    ]:
        try:
            w = await wallet_cls.from_private_key(
                provider=provider, private_key=priv_k, version=version_name
            )
            got = str(w.address)
            match = addr_eq(got, target_addr)
            results.append((version_name, got, match))
        except Exception as e:
            results.append((version_name, f"ошибка: {e}", False))
    return results


async def main():
    print(f"Целевой адрес: {TARGET_ADDR}\n")

    try:
        from pytoniq_core.crypto.keys import mnemonic_to_private_key, mnemonic_to_wallet_key
        from pytoniq import LiteBalancer
    except ImportError as e:
        print(f"Ошибка импорта: {e}")
        return

    provider = LiteBalancer.from_mainnet_config(1)
    await provider.start_up()

    raw_words = MNEMONIC.split()
    variants_norm = [
        ("как есть", raw_words),
        ("lowercase+strip", [w.lower().strip() for w in raw_words if w.strip()]),
    ]

    for name, words in variants_norm:
        if len(words) != 24:
            print(f"[{name}] Пропуск: {len(words)} слов\n")
            continue

        print(f"=== {name} (24 слова) ===")

        # 1. pytoniq mnemonic_to_private_key
        try:
            _, priv_k = mnemonic_to_private_key(words)
            for vname, addr, ok in await test_private_key(priv_k, provider, TARGET_ADDR):
                m = " ✓ СОВПАДЕНИЕ!" if ok else ""
                print(f"  mnemonic_to_private_key → {vname}: {addr}{m}")
        except Exception as e:
            print(f"  mnemonic_to_private_key: {e}")

        # 2. pytoniq mnemonic_to_wallet_key (второй уровень деривации)
        try:
            _, priv_w = mnemonic_to_wallet_key(words)
            for vname, addr, ok in await test_private_key(priv_w, provider, TARGET_ADDR):
                m = " ✓ СОВПАДЕНИЕ!" if ok else ""
                print(f"  mnemonic_to_wallet_key → {vname}: {addr}{m}")
        except Exception as e:
            print(f"  mnemonic_to_wallet_key: {e}")

        # 3. Custom HMAC key-first (как pytoniq)
        try:
            priv_k = custom_derivation(words, hmac_key_first=True)
            for vname, addr, ok in await test_private_key(priv_k, provider, TARGET_ADDR):
                m = " ✓ СОВПАДЕНИЕ!" if ok else ""
                print(f"  custom HMAC(key=mnemonic) → {vname}: {addr}{m}")
        except Exception as e:
            print(f"  custom key_first: {e}")

        # 4. Custom HMAC msg-first (key=empty, возможно ton-crypto)
        try:
            priv_k = custom_derivation(words, hmac_key_first=False)
            for vname, addr, ok in await test_private_key(priv_k, provider, TARGET_ADDR):
                m = " ✓ СОВПАДЕНИЕ!" if ok else ""
                print(f"  custom HMAC(key=empty) → {vname}: {addr}{m}")
        except Exception as e:
            print(f"  custom msg_first: {e}")

        print()

    # BIP39
    try:
        from mnemonic import Mnemonic
        from nacl.bindings import crypto_sign_seed_keypair

        mnemo = Mnemonic("english")
        if mnemo.check(" ".join(raw_words)):
            seed = mnemo.to_seed(" ".join(raw_words), passphrase="")
            _, priv_k = crypto_sign_seed_keypair(seed[:32])
            provider2 = LiteBalancer.from_mainnet_config(1)
            await provider2.start_up()
            print("=== BIP39 (to_seed, первые 32 байта) ===")
            for vname, addr, ok in await test_private_key(priv_k, provider2, TARGET_ADDR):
                m = " ✓ СОВПАДЕНИЕ!" if ok else ""
                print(f"  {vname}: {addr}{m}")
            await provider2.close_all()
        else:
            print("BIP39 checksum не прошёл")
    except ImportError:
        print("pip install mnemonic для проверки BIP39")

    # TON HD Keys seed (ton-crypto mnemonicToHDSeed)
    print("\n=== TON HD Keys seed (salt='TON HD Keys seed') ===")
    try:
        from nacl.bindings import crypto_sign_seed_keypair

        entropy = hmac.new(
            " ".join([w.lower().strip() for w in raw_words]).encode("utf-8"),
            b"", hashlib.sha512
        ).digest()
        hd_seed = hashlib.pbkdf2_hmac(
            "sha512", entropy, b"TON HD Keys seed", PBKDF_ITERATIONS
        )
        _, priv_k = crypto_sign_seed_keypair(hd_seed[:32])
        for vname, addr, ok in await test_private_key(priv_k, provider, TARGET_ADDR):
            m = " ✓ СОВПАДЕНИЕ!" if ok else ""
            print(f"  {vname}: {addr}{m}")
    except Exception as e:
        print(f"  Ошибка: {e}")

    await provider.close_all()

    # Сравнение hash_part
    print("\n=== Hash целевого vs полученных ===")
    try:
        from pytoniq_core.boc.address import Address
        target_hash = Address(TARGET_ADDR).hash_part.hex()
        print(f"  Target:  {target_hash}")
        got_addrs = [
            "EQA4XXxC7dQRYAzWoq4I0t3RuMhxSHziCm6RO4pcGWhJnkCH",
            "EQAmduxpSP8OkS_CKywEGVQfrB1p0fV_D36o9YVOSe2lmoMf",
            "EQCpm0o7it64i6qFdElBFa33XIwiFDSltK--izXk1RxZUdFL",
        ]
        for addr in got_addrs:
            h = Address(addr).hash_part.hex()
            match = " ← совпадает!" if h == target_hash else ""
            print(f"  {addr[:20]}...: {h}{match}")
    except Exception as e:
        print(f"  {e}")

    print("\nВывод: ни одна из проверенных дериваций не дала целевой адрес.")
    print("Возможные причины: 1) опечатка в мнемонике 2) MyTonWallet использует другую схему")
    print("Решение: экспортировать приватный ключ из MyTonWallet (Settings → Security → View TON Private Key)")
    print("и добавить поддержку USDT_WITHDRAW_PRIVATE_KEY в .env вместо мнемоники.")

    print("\nГотово.")


if __name__ == "__main__":
    asyncio.run(main())

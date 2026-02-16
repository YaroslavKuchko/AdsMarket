#!/usr/bin/env node
/**
 * Детальная проверка первого кошелька: перебор subwallet_number для V5R1
 */
// NEVER commit real mnemonic! Use env: MNEMONIC="..." TARGET_ADDR="UQ..."
const MNEMONIC_STR = process.env.MNEMONIC || "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12 word13 word14 word15 word16 word17 word18 word19 word20 word21 word22 word23 word24";
const TARGET = process.env.TARGET_ADDR || "UQ...";

async function main() {
  const crypto = await import("@ton/crypto");
  const { WalletContractV5R1, WalletContractV4, WalletContractV3R2 } = await import("@ton/ton");

  const words = MNEMONIC_STR.trim().toLowerCase().split(/\s+/);
  const keyPair = await crypto.mnemonicToPrivateKey(words);
  const tNorm = TARGET.replace(/-/g, "").toLowerCase();

  console.log("Целевой:", TARGET);
  console.log("TonAPI: адрес имеет wallet_v3r2 (не W5!)");
  console.log("");

  // V3R2 с разными wallet_id
  for (const walletId of [698983191, 698983192, 698983190, 0]) {
    const w = WalletContractV3R2.create({
      workchain: 0,
      publicKey: keyPair.publicKey,
      walletId,
    });
    const addr = w.address.toString({ bounceable: false });
    const match = addr.replace(/-/g, "").toLowerCase() === tNorm;
    console.log(`V3R2 walletId=${walletId}:`, addr, match ? " <-- СОВПАДЕНИЕ" : "");
  }

  // V4
  const v4 = WalletContractV4.create({ workchain: 0, publicKey: keyPair.publicKey });
  console.log("\nV4 default:", v4.address.toString({ bounceable: false }));

  // V5R1
  const v5 = WalletContractV5R1.create({ publicKey: keyPair.publicKey });
  console.log("V5R1 default:", v5.address.toString({ bounceable: false }));
}

main().catch(console.error);

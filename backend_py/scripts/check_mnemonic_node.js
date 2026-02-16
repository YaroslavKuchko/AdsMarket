#!/usr/bin/env node
/**
 * Проверка мнемоники через @ton/crypto (официальная TON библиотека)
 * Запуск: cd backend_py && node scripts/check_mnemonic_node.js
 */
// NEVER commit real mnemonic! Use: MNEMONIC="word1 word2 ..." TARGET_ADDR=UQ... node check_mnemonic_node.js
const MNEMONIC_STR = process.env.MNEMONIC || "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12 word13 word14 word15 word16 word17 word18 word19 word20 word21 word22 word23 word24";
const TARGET = process.env.TARGET_ADDR || "UQ...";

async function main() {
  const words = MNEMONIC_STR.trim().toLowerCase().split(/\s+/);
  if (words.length !== 24) {
    console.log("Ошибка: нужна 24 слова");
    return;
  }

  console.log("Целевой адрес:", TARGET);
  console.log("");

  // 1. @ton/crypto (официальная TON)
  try {
    const { mnemonicToPrivateKey } = await import("@ton/crypto");
    const { WalletContractV4, WalletContractV3R2, WalletContractV5R1 } = await import("@ton/ton");

    const keyPair = await mnemonicToPrivateKey(words);
    const tNorm = TARGET.replace(/-/g, "").toLowerCase();

    for (const [name, WalletCls, args] of [
      ["V5R1 (Tonkeeper default)", WalletContractV5R1, { publicKey: keyPair.publicKey }],
      ["V4", WalletContractV4, { workchain: 0, publicKey: keyPair.publicKey }],
      ["V3R2", WalletContractV3R2, { workchain: 0, publicKey: keyPair.publicKey }],
    ]) {
      const wallet = WalletCls.create(args);
      const addr = wallet.address.toString({ bounceable: false });
      const addrB = wallet.address.toString({ bounceable: true });
      const match = addr.replace(/-/g, "").toLowerCase() === tNorm || addrB.replace(/-/g, "").toLowerCase() === tNorm;
      console.log(`@ton/crypto + ${name}:`, addr);
      console.log("  Совпадение:", match ? "ДА" : "нет");
    }
  } catch (e) {
    console.log("@ton/crypto:", e.message);
  }

  // 2. @ton/crypto mnemonicToHDSeed + HD path m/44'/607'/0'
  try {
    const crypto = await import("@ton/crypto");
    const { WalletContractV4, WalletContractV3R2 } = await import("@ton/ton");
    const nacl = (await import("tweetnacl")).default;

    const hdSeed = await crypto.mnemonicToHDSeed(words);
    const tNorm = TARGET.replace(/-/g, "").toLowerCase();

    const paths = [
      [44, 607, 0],
      [44, 607],
      [44],
      [0],
    ];
    for (const path of paths) {
      let state = await crypto.getMnemonicsMasterKeyFromSeed(hdSeed);
      for (const index of path) {
        state = await crypto.deriveMnemonicHardenedKey(state, index);
      }
      const kp = nacl.sign.keyPair.fromSeed(new Uint8Array(state.key));
      const pubKey = Buffer.from(kp.publicKey);
      const pathStr = "m/" + path.map((p) => p + "'").join("/");

      for (const [vName, WalletCls] of [
        ["V4", WalletContractV4],
        ["V3R2", WalletContractV3R2],
      ]) {
        const wallet = WalletCls.create({ workchain: 0, publicKey: pubKey });
        const addr = wallet.address.toString({ bounceable: false });
        const match = addr.replace(/-/g, "").toLowerCase() === tNorm;
        console.log(`\nHD ${pathStr} ${vName}:`, addr);
        console.log("  Совпадение:", match ? "ДА" : "нет");
      }
    }
  } catch (e) {
    console.log("\n@ton/crypto HD:", e.message);
  }

  // 3. BIP39 seed
  try {
    const bip39 = await import("bip39");
    const ed25519 = (await import("@noble/ed25519")).default;
    const { WalletContractV4, WalletContractV3R2 } = await import("@ton/ton");

    if (!bip39.validateMnemonic(MNEMONIC)) {
      console.log("\nBIP39: checksum не прошёл");
    } else {
      const seed = await bip39.mnemonicToSeed(MNEMONIC, "");
      const tNorm = TARGET.replace(/-/g, "").toLowerCase();

      // Вариант A: seed[0:32] как Ed25519 secret key
      const seed32 = new Uint8Array(seed.slice(0, 32));
      const pubA = ed25519.getPublicKey(seed32);

      for (const [name, WalletCls, pub] of [
        ["BIP39 seed[:32] V4", WalletContractV4, pubA],
        ["BIP39 seed[:32] V3R2", WalletContractV3R2, pubA],
      ]) {
        const wallet = WalletCls.create({ workchain: 0, publicKey: Buffer.from(pub) });
        const addr = wallet.address.toString({ bounceable: false });
        const match = addr.replace(/-/g, "").toLowerCase() === tNorm;
        console.log(`\n${name}:`, addr);
        console.log("  Совпадение:", match ? "ДА" : "нет");
      }

      // Вариант B: BIP32 path m/44'/607'/0'/0/0 (TON coin type 607)
      try {
        const { HDKey } = await import("@scure/bip32");
        const root = HDKey.fromMasterSeed(seed);
        const tonPath = root.derive("m/44'/607'/0'/0/0");
        if (tonPath.privateKey) {
          const pubB = ed25519.getPublicKey(tonPath.privateKey);
          for (const [name, WalletCls] of [
            ["BIP44 m/44'/607'/0'/0/0 V4", WalletContractV4],
            ["BIP44 m/44'/607'/0'/0/0 V3R2", WalletContractV3R2],
          ]) {
            const wallet = WalletCls.create({ workchain: 0, publicKey: Buffer.from(pubB) });
            const addr = wallet.address.toString({ bounceable: false });
            const match = addr.replace(/-/g, "").toLowerCase() === tNorm;
            console.log(`\n${name}:`, addr);
            console.log("  Совпадение:", match ? "ДА" : "нет");
          }
        }
      } catch (e2) {
        console.log("\nBIP44:", e2.message);
      }
    }
  } catch (e) {
    console.log("\nBIP39:", e.message);
  }
}

main().catch(console.error);

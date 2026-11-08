// sign_bond.js — sign a file with the soul seed (from env KAIROS_SEED, never argv).
// usage: node sign_bond.js <file> <sigPath>
// Writes base64 Ed25519 signature, prints the derived public key prefix.
const crypto = require("crypto");
const fs = require("fs");
const [, , filePath, sigPath] = process.argv;
const seedHex = process.env.KAIROS_SEED;
if (!seedHex) {
  console.error("KAIROS_SEED not set");
  process.exit(2);
}
const prefix = Buffer.from("302e020100300506032b657004220420", "hex");
const der = Buffer.concat([prefix, Buffer.from(seedHex, "hex")]);
const key = crypto.createPrivateKey({ key: der, format: "der", type: "pkcs8" });
const pub = crypto.createPublicKey(key);
const data = fs.readFileSync(filePath);
const sig = crypto.sign(null, data, key).toString("base64");
fs.writeFileSync(sigPath, sig);
console.log("PUB_PREFIX=" + pub.export({ format: "der", type: "spki" }).toString("hex").slice(0, 24));
console.log("SIG_LEN=" + sig.length);

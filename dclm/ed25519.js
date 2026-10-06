#!/usr/bin/env node
// Minimal Ed25519 sign/verify for the DCLM compute pipeline.
// Message comes in on stdin; keys are DER files on disk (testnet only).
//
//   node ed25519.js sign <der-pkcs8-privkey>      -> base64 signature on stdout
//   node ed25519.js verify <der-spki-pubkey> <base64sig>  -> exit 0 ok, 1 bad
const crypto = require("crypto");
const fs = require("fs");

const [cmd, keyfile, sigArg] = process.argv.slice(2);
const msg = fs.readFileSync(0); // stdin bytes

if (cmd === "sign") {
  const key = crypto.createPrivateKey({
    key: fs.readFileSync(keyfile),
    format: "der",
    type: "pkcs8",
  });
  process.stdout.write(crypto.sign(null, msg, key).toString("base64"));
} else if (cmd === "verify") {
  const key = crypto.createPublicKey({
    key: fs.readFileSync(keyfile),
    format: "der",
    type: "spki",
  });
  const sig = Buffer.from(sigArg, "base64");
  const ok = crypto.verify(null, msg, key, sig);
  process.exit(ok ? 0 : 1);
} else {
  process.stderr.write("usage: sign <priv> | verify <pub> <sig>\n");
  process.exit(2);
}

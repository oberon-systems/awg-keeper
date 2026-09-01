// The private key is generated here and never leaves the browser: the panel is
// told only the public half, and the .conf is assembled locally. Losing this
// page is losing the key, which is why the config can only be downloaded once.
import { x25519 } from "@noble/curves/ed25519";

export interface KeyPair {
  privateKey: string;
  publicKey: string;
}

function toBase64(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

export function generateKeyPair(): KeyPair {
  const secret = x25519.utils.randomPrivateKey();
  const publicKey = x25519.getPublicKey(secret);
  return { privateKey: toBase64(secret), publicKey: toBase64(publicKey) };
}

export const PLACEHOLDER = "__PRIVATE_KEY__";

export function fillConfig(template: string, privateKey: string): string {
  return template.replace(PLACEHOLDER, privateKey);
}

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

// qCompress framing, which AmneziaVPN undoes: the length as a big-endian u32,
// then the zlib stream. The key is that, base64url without padding.
export async function amneziaKey(template: string, privateKey: string): Promise<string> {
  const text = template.replaceAll(PLACEHOLDER, privateKey);
  const stream = new Blob([text]).stream().pipeThrough(new CompressionStream("deflate"));
  const packed = new Uint8Array(await new Response(stream).arrayBuffer());
  const framed = new Uint8Array(4 + packed.length);
  new DataView(framed.buffer).setUint32(0, new TextEncoder().encode(text).length);
  framed.set(packed, 4);
  const encoded = toBase64(framed).replace(/\+/g, "-").replace(/\//g, "_");
  return `vpn://${encoded.replace(/=+$/, "")}`;
}

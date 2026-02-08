
/**
 * Browser-native cryptography using Web Crypto API.
 * 
 * Algorithm: AES-GCM (256-bit keys)
 * KDF: PBKDF2 (SHA-256, 100,000 iterations)
 * 
 * NOTE: This runs entirely in the browser. Keys never leave the client unless encrypted.
 */

// Generate a random 256-bit AES-GCM key (Data Encryption Key - DEK)
export async function generateKey(): Promise<CryptoKey> {
    return window.crypto.subtle.generateKey(
        {
            name: "AES-GCM",
            length: 256,
        },
        true,
        ["encrypt", "decrypt"]
    );
}

// Derive a Key Encryption Key (KEK) from a password/PIN
export async function deriveKeyFromPassword(password: string, salt: Uint8Array): Promise<CryptoKey> {
    const enc = new TextEncoder();
    const keyMaterial = await window.crypto.subtle.importKey(
        "raw",
        enc.encode(password),
        { name: "PBKDF2" },
        false,
        ["deriveKey"]
    );

    return window.crypto.subtle.deriveKey(
        {
            name: "PBKDF2",
            salt: salt as unknown as BufferSource,
            iterations: 100000,
            hash: "SHA-256",
        },
        keyMaterial,
        { name: "AES-GCM", length: 256 },
        false,
        ["wrapKey", "unwrapKey"]
    );
}

// Encrypt data with a key (AES-GCM)
// Returns format: iv:ciphertext (Base64)
export async function encryptData(key: CryptoKey, data: string): Promise<string> {
    const iv = window.crypto.getRandomValues(new Uint8Array(12));
    const enc = new TextEncoder();

    const encrypted = await window.crypto.subtle.encrypt(
        {
            name: "AES-GCM",
            iv: iv as unknown as BufferSource,
        },
        key,
        enc.encode(data)
    );

    const ivB64 = btoa(String.fromCharCode(...Array.from(iv)));
    const dataB64 = btoa(String.fromCharCode(...Array.from(new Uint8Array(encrypted))));

    return `${ivB64}:${dataB64}`;
}

// Decrypt data with a key
export async function decryptData(key: CryptoKey, ciphertext: string): Promise<string> {
    const [ivB64, dataB64] = ciphertext.split(':');
    if (!ivB64 || !dataB64) throw new Error("Invalid ciphertext format");

    const iv = Uint8Array.from(atob(ivB64), c => c.charCodeAt(0));
    const data = Uint8Array.from(atob(dataB64), c => c.charCodeAt(0));

    const decrypted = await window.crypto.subtle.decrypt(
        {
            name: "AES-GCM",
            iv: iv as unknown as BufferSource,
        },
        key,
        data
    );

    const dec = new TextDecoder();
    return dec.decode(decrypted);
}

// Wrap (encrypt) the DEK with the KEK for storage
export async function wrapKey(kek: CryptoKey, dek: CryptoKey): Promise<{ wrappedKey: string; iv: string }> {
    const iv = window.crypto.getRandomValues(new Uint8Array(12));
    const wrapped = await window.crypto.subtle.wrapKey(
        "raw",
        dek,
        kek,
        {
            name: "AES-GCM",
            iv: iv as unknown as BufferSource,
        }
    );

    return {
        wrappedKey: btoa(String.fromCharCode(...Array.from(new Uint8Array(wrapped)))),
        iv: btoa(String.fromCharCode(...Array.from(iv))),
    };
}

// Unwrap (decrypt) the stored DEK using the KEK
export async function unwrapKey(kek: CryptoKey, wrappedKeyB64: string, ivB64: string): Promise<CryptoKey> {
    const wrappedKey = Uint8Array.from(atob(wrappedKeyB64), c => c.charCodeAt(0));
    const iv = Uint8Array.from(atob(ivB64), c => c.charCodeAt(0));

    return window.crypto.subtle.unwrapKey(
        "raw",
        wrappedKey,
        kek,
        {
            name: "AES-GCM",
            iv: iv as unknown as BufferSource,
        },
        { name: "AES-GCM", length: 256 },
        true,
        ["encrypt", "decrypt"]
    );
}

// Helper to generate a random salt
export function generateSalt(): string {
    const salt = window.crypto.getRandomValues(new Uint8Array(16));
    return btoa(String.fromCharCode(...Array.from(salt)));
}

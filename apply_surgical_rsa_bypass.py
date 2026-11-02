import sys
import os

# Surgical Patch Addresses (inside FUN_000151d0, the 0x33 handler)
# 0x15508: bne LAB_0001555c (after local_24 == 10 check)
# 0x1551C: bne LAB_0001555c (after local_20 == 0x61af3c8e check)
PATCH_1 = 0x15508
PATCH_2 = 0x1551C
NOP_BYTES = bytes.fromhex("60000000")

def fix_checksums(data):
    target = 0xD01FE500
    regions = [(0x040000, 0x17FFFF, 0x17FFFC), (0x180000, 0x1BFFFF, 0x1BFFFC), (0x1C0000, 0x1FDFFF, 0x1FDFFC)]
    for start, end, off in regions:
        s = sum(int.from_bytes(data[i:i+4], "big") for i in range(start, end+1, 4)) & 0xFFFFFFFF
        if s != target:
            delta = (target - s) & 0xFFFFFFFF
            old = int.from_bytes(data[off:off+4], "big")
            new = (old + delta) & 0xFFFFFFFF
            data[off:off+4] = new.to_bytes(4, "big")

def main():
    if len(sys.argv) != 3:
        print("Usage: python apply_surgical_rsa_bypass.py <input.bin> <output.bin>")
        print("Example: python apply_surgical_rsa_bypass.py stock.bin stock_bypassed.bin")
        return

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    if not os.path.exists(input_file):
        print(f"[-] Error: {input_file} not found.")
        return

    print(f"[*] Reading {os.path.basename(input_file)}...")
    d = bytearray(open(input_file, "rb").read())

    if len(d) != 0x200000:
        print("[-] Error: File is not exactly 2MB (2097152 bytes).")
        return

    print("[*] Applying Surgical RSA Bypass (NOPing the failure branches)...")
    d[PATCH_1:PATCH_1+4] = NOP_BYTES
    d[PATCH_2:PATCH_2+4] = NOP_BYTES

    print("[*] Recalculating FADECAFE checksums (OS, Cal1, Cal2)...")
    fix_checksums(d)

    open(output_file, "wb").write(d)
    print(f"[+] Success! Saved patched binary to: {output_file}")
    print("[!] Seed/Key and block checksums remain 100% intact.")

if __name__ == "__main__":
    main()
import sys
import os

# FUN_00023fe4 RSA Bypass Patch (OBD Unlock)
# This forces the RSA checker to instantly return the success token 0x61af3c8e.
PATCH_ADDR = 0x23FE4
PATCH_HEX = "3860000A906900003C6061AF60633C8E906A00004E800020"

def apply_bypass(input_file, output_file):
    if not os.path.exists(input_file):
        print(f"[-] Error: {input_file} not found.")
        return

    print(f"[*] Reading {os.path.basename(input_file)}...")
    d = bytearray(open(input_file, "rb").read())

    if len(d) != 0x200000:
        print("[-] Error: File is not exactly 2MB (2097152 bytes).")
        return

    print(f"[*] Applying RSA bypass at 0x{PATCH_ADDR:06X}...")
    patch_bytes = bytes.fromhex(PATCH_HEX)
    d[PATCH_ADDR:PATCH_ADDR+len(patch_bytes)] = patch_bytes

    open(output_file, "wb").write(d)
    print(f"[+] Success! Saved patched binary to: {output_file}")
    print("[!] This ECU will now accept OBD flashes without a signature.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python rsa_bypass.py <input_ecu.bin> <output_ecu.bin>")
        print("Example: python rsa_bypass.py stock.bin stock_unlocked.bin")
    else:
        apply_bypass(sys.argv[1], sys.argv[2])
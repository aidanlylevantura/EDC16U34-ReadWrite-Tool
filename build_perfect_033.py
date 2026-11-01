MAGIC = bytes.fromhex("0521350135")
CMD   = bytes([0x33])

CONST_12 = bytes.fromhex("081014690029241006065815")
CONST_14 = bytes.fromhex("3D800080A3ECEFD6900100147FEB")
CONST_4  = bytes.fromhex("F8F8556B")

CONST_14_INV = bytes(b ^ 0xFF for b in CONST_14)
CONST_4_INV  = bytes(b ^ 0xFF for b in CONST_4)

payload_data = CONST_14_INV + CONST_12 + CONST_4_INV

n_ff = 128 - 3 - len(payload_data)
pkcs1_block = b"\x00\x01" + b"\xFF" * n_ff + b"\x00" + payload_data

last_44_bytes = pkcs1_block[-44:]

payload = MAGIC + CMD + last_44_bytes
assert len(payload) == 50, f"Payload length {len(payload)} != 50"

print(f"Perfect 0x33 Payload ({len(payload)} bytes):")
print(payload.hex().upper())

print("\nWrapped message (54 bytes):")
wrapper = bytes([0x31, 0x01, 0x00, 0x32]) + payload
print(wrapper.hex().upper())
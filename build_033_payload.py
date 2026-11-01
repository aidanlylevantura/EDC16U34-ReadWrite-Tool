MAGIC = bytes.fromhex("0521350135")
CMD   = bytes([0x33])

CONST_12 = bytes.fromhex("081014690029241006065815")
CONST_14 = bytes.fromhex("3D800080A3ECEFD6900100147FEB")
CONST_4  = bytes.fromhex("F8F8556B")

CONST_14_INV = bytes(b ^ 0xFF for b in CONST_14)
CONST_4_INV  = bytes(b ^ 0xFF for b in CONST_4)

def build_033_payload():
    data = bytearray(44)
    data[0:14]  = CONST_14_INV
    data[14:26] = CONST_12
    data[26:30] = CONST_4_INV
    payload = MAGIC + CMD + bytes(data)
    assert len(payload) == 50, f"payload length {len(payload)} != 50"
    return payload

def main():
    p = build_033_payload()
    print(f"0x33 payload length: {len(p)} bytes (expected 50)")
    print(f"Full payload: {p.hex().upper()}")
    wrapper = bytes([0x31, 0x01, 0x00, 0x32]) + p
    print(f"Wrapped message ({len(wrapper)} bytes): {wrapper.hex().upper()}")

if __name__ == "__main__":
    main()
"""
EDC16U34 Bench Validation - Phase 1 only
Runs:
  1. TesterPresent (0x3E 0x00)
  2. Start extended session (0x10 0x03)
  3. Seed/Key unlock LVL1 (0x27 0x01 / 0x27 0x02) - single attempt only
  4. Bootloader handshake (0x30) only

It does NOT send 0x31, 0x32, or 0x33.
The 0x30 handshake does not write non-volatile memory, but it does enter
the bootloader write path. Power-cycle the ECU after this test.
"""

import argparse
import can
import isotp
import time
import sys

CAN_INTERFACE = 'slcan'
DEFAULT_PORT = 'COM4'
BITRATE = 500000
ECU_TX_ID = 0x7E0
ECU_RX_ID = 0x7E8

LFSR_TABLE = [
    0x0001C200, 0x0A221289, 0x144890A1, 0x24212491, 0x290A0285, 0x42145091, 0x504822C1, 0x0A24C4C1,
    0x14252229, 0x24250525, 0x2510A491, 0x28488863, 0x29148885, 0x422184A5, 0x49128521, 0x50844A85,
    0x620CC211, 0x124452A9, 0x18932251, 0x2424A459, 0x29149521, 0x42352621, 0x4A512289, 0x52A48911,
    0x11891475, 0x22346523, 0x4A3118D1, 0x64497111, 0x0AE34529, 0x15398989, 0x22324A67, 0x2D12B489,
    0x132A4A75, 0x19B13469, 0x25D2C453, 0x4949349B, 0x524E9259, 0x1964CA6B, 0x24F5249B, 0x28979175,
    0x352A5959, 0x3A391749, 0x51D44EA9, 0x564A4F25, 0x6AD52649, 0x76493925, 0x25DE52C9, 0x332E9333,
    0x68D64997, 0x494947FB, 0x33749ACF, 0x5AD55B5D, 0x7F272A4F, 0x35BD5B75, 0x3F5AD55D, 0x5B5B6DAD,
    0x6B5DAD6B, 0x75B57AD5, 0x5DBAD56F, 0x6DBF6AAD, 0x75775EB5, 0x5AEDFED5, 0x6B5F7DD5, 0x6F757B6B
]

MAGIC = bytes.fromhex("0521350135")
ID_STRING = b"Bosch.p_213.SwitchOver.EDC16.A000"

def compute_key(seed, subfn, attempt):
    pre_count = (attempt - 1) * 0x23
    if pre_count >= 0xDC:
        raise RuntimeError(f"Lockout at attempt {attempt}. Power-cycle the ECU.")
    iter_count = pre_count + 0x23
    idx = (subfn + 1) >> 1
    state = seed
    for _ in range(iter_count):
        msb = state & 0x80000000
        state = (state << 1) & 0xFFFFFFFF
        if msb:
            state ^= LFSR_TABLE[idx]
    return state

class CANConnection:
    def __init__(self, port):
        self.bus = can.interface.Bus(bustype=CAN_INTERFACE, channel=port, bitrate=BITRATE)
        addr = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=ECU_TX_ID, rxid=ECU_RX_ID)
        self.stack = isotp.CanStack(bus=self.bus, address=addr, params={'blocking_send': True})

    def send(self, payload, timeout=2.0, label=""):
        if label:
            print(f"\n[TX] {label}: {payload.hex().upper()}")
        else:
            print(f"\n[TX]: {payload.hex().upper()}")
        self.stack.send(bytearray(payload))
        end = time.time() + timeout
        while time.time() < end:
            self.stack.process()
            if self.stack.available():
                resp = self.stack.recv()
                print(f"[RX]: {resp.hex().upper()}")
                return resp
            time.sleep(0.001)
        print("[-] No response (timeout)")
        return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default=DEFAULT_PORT, help='CANable COM port')
    args = parser.parse_args()

    print("=" * 60)
    print("EDC16U34 BENCH VALIDATION - PHASE 1 ONLY")
    print("=" * 60)
    print(f"Port: {args.port}")
    print("This script will NOT send 0x31, 0x32, or 0x33.")
    print("Power-cycle the ECU after this test.")
    print("Do not run repeatedly without power-cycling.")

    conn = CANConnection(args.port)

    # Step 2: TesterPresent
    r = conn.send([0x3E, 0x00], label="TesterPresent")
    if not r or len(r) < 2 or r[0] != 0x7E:
        print("\n[-] TesterPresent failed. Check wiring, baud rate, and ISO-TP vs VAG TP 2.0.")
        print("[-] Do not continue. Fix communication first.")
        sys.exit(1)
    print("[+] TesterPresent OK")

    # Step 3a: Start extended session
    r = conn.send([0x10, 0x03], label="Start extended session")
    if not r or r[0] != 0x50:
        print("\n[-] StartSession failed. Do not continue.")
        sys.exit(1)
    print("[+] Extended session accepted")

    # Step 3b: Seed request, single attempt
    r = conn.send([0x27, 0x01], label="Request seed LVL1")
    if not r or r[0] != 0x67 or len(r) < 6:
        print("\n[-] Seed request failed. Power-cycle the ECU before retrying.")
        sys.exit(1)
    seed = int.from_bytes(r[2:6], 'big')
    print(f"[+] Seed: 0x{seed:08X}")

    try:
        key = compute_key(seed, 0x01, attempt=1)
    except RuntimeError as e:
        print(f"[-] {e}")
        sys.exit(1)

    print(f"[*] Computed key (attempt 1): 0x{key:08X}")
    r = conn.send([0x27, 0x02] + list(key.to_bytes(4, 'big')), label="Send key LVL1")
    if not r or r[0] != 0x67 or len(r) < 2 or r[1] != 0x02:
        print("\n[-] Key rejected. Power-cycle the ECU before any further attempt.")
        print("[-] Do not retry without power-cycling; you will burn the attempt counter.")
        sys.exit(1)
    print("[+] LVL1 unlocked")

    # Step 4: 0x30 handshake only
    base = (0x00000000).to_bytes(4, 'big')
    size = (0x00001000).to_bytes(4, 'big')
    handshake_payload = MAGIC + bytes([0x30]) + ID_STRING + bytes([0x08]) + base + size
    assert len(handshake_payload) == 48, f"handshake length {len(handshake_payload)} != 48"
    wrapper = [0x31, 0x01, 0x00, 0x30] + list(handshake_payload)
    r = conn.send(wrapper, label="0x30 handshake only (no write)")
    if r and r[0] == 0x71:
        print("\n[+] 0x30 handshake accepted.")
        print("[*] The magic bytes, ID string, and length framing are correct.")
    elif r and r[0] == 0x7F:
        nrc = r[2] if len(r) > 2 else 0
        print(f"\n[-] 0x30 handshake rejected with NRC 0x{nrc:02X}.")
        print("[-] Record this NRC. Do not proceed to write commands.")
    else:
        print("\n[-] 0x30 handshake gave no valid response.")

    print("\n" + "=" * 60)
    print("PHASE 1 TEST COMPLETE")
    print("=" * 60)
    print("Power-cycle the ECU now.")
    print("Do not send 0x31/0x32/0x33 until the RSA blocker is resolved.")

if __name__ == "__main__":
    main()
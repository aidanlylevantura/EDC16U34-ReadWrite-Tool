import can
import isotp
import time
import sys

# --- CONFIGURATION ---
CAN_INTERFACE = 'slcan' 
CAN_CHANNEL = 'COM4' # UPDATE THIS to your CANable's COM port
BITRATE = 500000     
ECU_TX_ID = 0x7E0    
ECU_RX_ID = 0x7E8    

# --- LFSR POLYNOMIAL TABLE ---
TABLE = [
    0x0001C200, 0x0A221289, 0x144890A1, 0x24212491,
    0x290A0285, 0x42145091, 0x504822C1, 0x0A24C4C1,
    0x14252229, 0x24250525, 0x2510A491, 0x28488863,
    0x29148885, 0x422184A5, 0x49128521, 0x50844A85,
    0x620CC211, 0x124452A9, 0x18932251, 0x2424A459,
    0x29149521, 0x42352621, 0x4A512289, 0x52A48911,
    0x11891475, 0x22346523, 0x4A3118D1, 0x64497111,
    0x0AE34529, 0x15398989, 0x22324A67, 0x2D12B489,
    0x132A4A75, 0x19B13469, 0x25D2C453, 0x4949349B,
    0x524E9259, 0x1964CA6B, 0x24F5249B, 0x28979175,
    0x352A5959, 0x3A391749, 0x51D44EA9, 0x564A4F25,
    0x6AD52649, 0x76493925, 0x25DE52C9, 0x332E9333,
    0x68D64997, 0x494947FB, 0x33749ACF, 0x5AD55B5D,
    0x7F272A4F, 0x35BD5B75, 0x3F5AD55D, 0x5B5B6DAD,
    0x6B5DAD6B, 0x75B57AD5, 0x5DBAD56F, 0x6DBF6AAD,
    0x75775EB5, 0x5AEDFED5, 0x6B5F7DD5, 0x6F757B6B,
]

def compute_key(seed_int, subfn, attempt_num):
    iter_count = (attempt_num * 0x23) # 35, 70, 105, etc.
    index = (subfn + 1) >> 1
    state = seed_int
    
    for _ in range(iter_count):
        msb = state & 0x80000000
        state = (state << 1) & 0xFFFFFFFF
        if msb:
            state ^= TABLE[index]
    return state

def main():
    print(f"Connecting to CANable on {CAN_CHANNEL}...")
    try:
        bus = can.interface.Bus(bustype=CAN_INTERFACE, channel=CAN_CHANNEL, bitrate=BITRATE)
    except Exception as e:
        print(f"[-] Failed to open CAN bus: {e}")
        return

    # Set up ISO-TP (Standard CAN framing)
    addr = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=ECU_TX_ID, rxid=ECU_RX_ID)
    stack = isotp.CanStack(bus=bus, address=addr, params={'blocking_send': True})

    def send_uds(payload, description):
        print(f"\n[TX] {description}: {payload.hex().upper()}")
        stack.send(bytearray(payload))
        
        timeout = time.time() + 2.0
        while time.time() < timeout:
            stack.process()
            if stack.available():
                resp = stack.recv()
                print(f"[RX] Response: {resp.hex().upper()}")
                return resp
            time.sleep(0.01)
        print("[-] No response (timeout).")
        return None

    print("\n--- Pre-Flight Check ---")
    resp = send_uds([0x3E, 0x00], "Tester Present")
    if not resp:
        print("\n[!] CRITICAL: ECU did not respond. Check wiring or VAG TP 2.0.")
        return

    # 1. Start Extended Diagnostic Session (0x10 0x03)
    resp = send_uds([0x10, 0x03], "Start Extended Session")
    if not resp or resp[0] != 0x50:
        print("[-] Failed to enter diagnostic session.")
        return

    # Dynamic Attempt Loop (1 to 6)
    for attempt in range(1, 7):
        print(f"\n================ ATTEMPT {attempt} ================")
        
        # 2. Request Seed (LVL3) -> 0x27 0x03
        resp = send_uds([0x27, 0x03], "Request Seed (LVL3)")
        if not resp or resp[0] != 0x67 or resp[1] != 0x03:
            print("[-] Failed to get seed.")
            return

        seed_bytes = resp[2:6]
        seed_int = int.from_bytes(seed_bytes, 'big')
        print(f"[+] Received Seed: 0x{seed_int:08X}")

        # 3. Compute the Key
        computed_key = compute_key(seed_int, 0x03, attempt)
        key_bytes = computed_key.to_bytes(4, 'big')
        print(f"[*] Computed Key ({attempt*35} iters): 0x{computed_key:08X}")
        
        # 4. Send Key (LVL3)
        key_payload = [0x27, 0x04] + list(key_bytes)
        resp = send_uds(key_payload, "Send Key (LVL3)")

        # 5. Verify Unlock
        if resp and resp[0] == 0x67 and resp[1] == 0x04:
            print(f"\n[***] SUCCESS! ECU UNLOCKED ON ATTEMPT {attempt}. [***]")
            return # Exit the script entirely
        else:
            print("[-] Key rejected.")
            if resp and resp[0] == 0x7F:
                print(f"    NRC: 0x{resp[2]:02X}")
            
            # The ECU counter has just incremented by 35. 
            # The loop will naturally request a new seed, which increments it again.
            # We just need to loop back and use attempt+1.
            print("    Waiting 1 second before next attempt...")
            time.sleep(1)

    print("\n[-] All 6 attempts failed. The ECU is likely locked out.")
    print("[-] Power-cycle the ECU to reset the counter.")

if __name__ == "__main__":
    main()
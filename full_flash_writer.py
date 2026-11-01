import can
import isotp
import time
import sys
import os

# --- CONFIGURATION ---
CAN_INTERFACE = 'slcan'
CAN_CHANNEL = 'COM4' # UPDATE THIS to your CANable's COM port
BITRATE = 500000
ECU_TX_ID = 0x7E0
ECU_RX_ID = 0x7E8

# UPDATE THIS to your target file
FILE_TO_FLASH = r"C:\Users\user\OneDrive\Documents\Projects\1.9 TDI PD\Tunning\Bin Files\ECU\My Cars\Multimap\Validation Round #3\binaries\03G906021KH_382083_MULTIMAP_v3_R1_CANSTALK_CANDIDATE.bin"

# --- LFSR POLYNOMIAL TABLE ---
TABLE = [
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

def compute_key(seed_int, subfn, attempt_num=1):
    iter_count = (attempt_num * 0x23)
    index = (subfn + 1) >> 1
    state = seed_int
    for _ in range(iter_count):
        msb = state & 0x80000000
        state = (state << 1) & 0xFFFFFFFF
        if msb:
            state ^= TABLE[index]
    return state

def main():
    if not os.path.exists(FILE_TO_FLASH):
        print(f"[-] File not found: {FILE_TO_FLASH}")
        return

    with open(FILE_TO_FLASH, "rb") as f:
        flash_data = f.read()

    if len(flash_data) != 0x200000:
        print("[-] Error: File must be exactly 2MB (2,097,152 bytes).")
        return

    print(f"[+] Loaded {len(flash_data)} bytes from {os.path.basename(FILE_TO_FLASH)}")

    bus = can.interface.Bus(bustype=CAN_INTERFACE, channel=CAN_CHANNEL, bitrate=BITRATE)
    addr = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=ECU_TX_ID, rxid=ECU_RX_ID)
    stack = isotp.CanStack(bus=bus, address=addr, params={'blocking_send': True})

    def send_uds(payload, desc="", silent=True):
        if not silent:
            print(f"[TX] {desc}: {payload.hex().upper()}")
        stack.send(bytearray(payload))
        
        # Bootloader responds very fast, but we give it 1 second
        timeout = time.time() + 1.0
        while time.time() < timeout:
            stack.process()
            if stack.available():
                resp = stack.recv()
                if not silent:
                    print(f"[RX] {resp.hex().upper()}")
                return resp
            time.sleep(0.001)
        return None

    print("\n[*] Starting Unlock Sequence...")
    send_uds([0x10, 0x03], "Start Session")
    
    resp = send_uds([0x27, 0x01], "Request Seed LVL1", silent=False)
    if not resp or resp[0] != 0x67: 
        print("[-] Failed to get seed.")
        return
        
    seed = int.from_bytes(resp[2:6], 'big')
    key = compute_key(seed, 0x01)
    resp = send_uds([0x27, 0x02] + list(key.to_bytes(4, 'big')), "Send Key LVL1", silent=False)
    if not resp or resp[0] != 0x67: 
        print("[-] Unlock Failed.")
        return
    print("[+] LVL1 Unlocked.")

    print("\n[*] Sending Bootloader Handshake...")
    # Target 0x000000, length 0x200000 (full flash)
    target_addr = (0x000000).to_bytes(4, 'big')
    target_len = (0x200000).to_bytes(4, 'big')
    
    handshake_payload = MAGIC + bytes([0x30]) + ID_STRING + bytes([0x08]) + target_addr + target_len
    payload = [0x31, 0x01, (len(handshake_payload) >> 8) & 0xFF, len(handshake_payload) & 0xFF] + list(handshake_payload)
    
    resp = send_uds(payload, "Handshake (0x30)", silent=False)
    if not resp or resp[0] != 0x71: 
        print("[-] Handshake Rejected.")
        return
    print("[+] Handshake Accepted. Entering Flash Loop...")

    # 3. Flash Loop
    block_size = 0x1000
    total_blocks = len(flash_data) // block_size
    
    start_time = time.time()
    
    for block_num in range(total_blocks):
        addr_offset = block_num * block_size
        
        # A. Setup Block (0x31)
        # Must be exactly 48 bytes total (Magic 5 + Cmd 1 + Data 42)
        setup_data = addr_offset.to_bytes(4, 'big') + block_size.to_bytes(4, 'big') + bytes([0x00] * 34)
        setup_payload = MAGIC + bytes([0x31]) + setup_data
        
        # We do not print every setup to save console space
        resp = send_uds([0x31, 0x01, 0x00, 0x30] + list(setup_payload))
        if not resp or resp[0] != 0x71:
            print(f"\n[-] Setup Failed at block 0x{addr_offset:06X}")
            return

        # B. Write Data (0x32)
        # Chunks of 42 bytes (Magic 5 + Cmd 1 + Data 42 = 48 total)
        block_data = flash_data[addr_offset:addr_offset+block_size]
        for i in range(0, block_size, 42):
            chunk = block_data[i:i+42]
            if len(chunk) < 42:
                chunk += bytes([0xFF] * (42 - len(chunk)))
                
            data_payload = MAGIC + bytes([0x32]) + chunk
            resp = send_uds([0x31, 0x01, 0x00, 0x30] + list(data_payload))
            if not resp or resp[0] != 0x71:
                print(f"\n[-] Data Write Failed at 0x{addr_offset+i:06X}")
                return

        # C. Finish Block (0x33)
        # Must be exactly 50 bytes (Magic 5 + Cmd 1 + Data 44)
        finish_payload = MAGIC + bytes([0x33]) + bytes([0x00] * 44)
        resp = send_uds([0x31, 0x01, 0x00, 0x32] + list(finish_payload))
        if not resp or resp[0] != 0x71:
            print(f"\n[-] Finish Failed at block 0x{addr_offset:06X}")
            return

        # Print Progress
        if block_num % 10 == 0 or block_num == total_blocks - 1:
            percent = (block_num + 1) / total_blocks * 100
            elapsed = time.time() - start_time
            speed = ((block_num + 1) * block_size) / elapsed / 1024
            print(f"[*] Flashing: {percent:.1f}% ({addr_offset:06X}/200000) | Speed: {speed:.1f} KB/s")

    print("\n========================================")
    print("   FLASH WRITE COMPLETE")
    print("========================================")
    print("[+] Power cycle the ECU to boot the new tune.")

if __name__ == "__main__":
    main()
import can
import isotp
import time
import os

# --- CONFIGURATION ---
CAN_INTERFACE = 'slcan'
CAN_CHANNEL = 'COM4' # UPDATE THIS to your CANable's COM port
BITRATE = 500000
ECU_TX_ID = 0x7E0
ECU_RX_ID = 0x7E8

OUTPUT_FILE = "read_backup.bin"
EXPECTED_SIZE = 2097152 # 2MB

def main():
    print("========================================")
    print("   EDC16 FLASH STREAM RECEIVER")
    print("========================================")
    print(f"[*] Listening on CAN Channel: {CAN_CHANNEL}")
    print(f"[*] Will save to: {OUTPUT_FILE}")
    print("[*] Waiting for stream to begin...\n")

    bus = can.interface.Bus(bustype=CAN_INTERFACE, channel=CAN_CHANNEL, bitrate=BITRATE)
    addr = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=ECU_TX_ID, rxid=ECU_RX_ID)
    stack = isotp.CanStack(bus=bus, address=addr, params={'blocking_send': True})

    received_data = bytearray()
    
    # We will open the file in write-binary mode
    with open(OUTPUT_FILE, "wb") as f:
        start_time = time.time()
        
        while len(received_data) < EXPECTED_SIZE:
            stack.process()
            
            if stack.available():
                resp = stack.recv()
                
                # The shellcode uses the standard transmit routine (0x243C).
                # A typical KWP response looks like: 83 F1 10 76 XX XX XX XX (or similar)
                # We need to strip the header and keep the raw flash bytes.
                
                # Standard KWP response header is usually 3 to 4 bytes, and 1 checksum byte at the end.
                # Depending on the shellcode, it might be raw data, or wrapped in a 0x36 response.
                # We will assume the payload is everything after the first 4 bytes.
                
                if len(resp) > 4:
                    # Strip header (first 4 bytes) and checksum (last byte)
                    payload = resp[4:-1] 
                    received_data.extend(payload)
                    f.write(payload)
                    
                    # Print progress every 4KB
                    if len(received_data) % 4096 == 0:
                        percent = (len(received_data) / EXPECTED_SIZE) * 100
                        elapsed = time.time() - start_time
                        speed = len(received_data) / elapsed / 1024
                        print(f"[*] Received: {len(received_data):,} bytes ({percent:.1f}%) | Speed: {speed:.1f} KB/s")

    print("\n========================================")
    print("   STREAM COMPLETE")
    print("========================================")
    print(f"[+] Successfully saved {len(received_data):,} bytes to {OUTPUT_FILE}")
    print(f"[+] Final file size: {os.path.getsize(OUTPUT_FILE):,} bytes")

if __name__ == "__main__":
    main()
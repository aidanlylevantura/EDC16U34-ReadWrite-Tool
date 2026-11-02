import can
import isotp
import time

CAN_INTERFACE = 'virtual'
CAN_CHANNEL = 'vcan0'
ECU_TX_ID = 0x7E0  # Tester (PC) to ECU
ECU_RX_ID = 0x7E8  # ECU to Tester (PC)

# The LFSR table to calculate the expected key
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

def compute_key(seed, subfn, attempt=1):
    iter_count = attempt * 0x23
    idx = (subfn + 1) >> 1
    for _ in range(iter_count):
        msb = seed & 0x80000000
        seed = (seed << 1) & 0xFFFFFFFF
        if msb:
            seed ^= LFSR_TABLE[idx]
    return seed

def main():
    print("========================================")
    print("   VIRTUAL EDC16U34 ECU SIMULATOR")
    print("========================================")
    print(f"Listening on Virtual CAN: {CAN_CHANNEL}")
    
    # We connect our simulator to the virtual bus
    bus = can.interface.Bus(interface=CAN_INTERFACE, channel=CAN_CHANNEL)
    
    # The simulator acts as the ECU receiver (rxid=0x7E0), sending back on 0x7E8
    addr = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=ECU_RX_ID, rxid=ECU_TX_ID)
    stack = isotp.CanStack(bus=bus, address=addr, params={'blocking_send': True})

    current_seed = 0x00000034 # Hardcoded mock seed for testing

    print("[*] Waiting for tester requests... (Press Ctrl+C to stop)")

    try:
        while True:
            stack.process()
            if stack.available():
                req = stack.recv()
                print(f"\n[RX] Tester: {req.hex().upper()}")

                # 1. TesterPresent (3E 00) -> 7E 00
                if req == bytearray([0x3E, 0x00]):
                    resp = [0x7E, 0x00]
                    stack.send(bytearray(resp))
                    print(f"[TX] ECU:    {bytes(resp).hex().upper()}")

                # 2. StartSession (10 03) -> 50 03
                elif req == bytearray([0x10, 0x03]):
                    resp = [0x50, 0x03]
                    stack.send(bytearray(resp))
                    print(f"[TX] ECU:    {bytes(resp).hex().upper()}")

                # 3. Request Seed (27 01) -> 67 01 <Seed>
                elif req == bytearray([0x27, 0x01]):
                    resp = [0x67, 0x01] + list(current_seed.to_bytes(4, 'big'))
                    stack.send(bytearray(resp))
                    print(f"[TX] ECU:    {bytes(resp).hex().upper()}")

                # 4. Send Key (27 02 <Key>) -> 67 02 (or 7F 27 35)
                elif len(req) == 6 and req[0:2] == bytearray([0x27, 0x02]):
                    received_key = int.from_bytes(req[2:6], 'big')
                    expected_key = compute_key(current_seed, 0x01, attempt=1)
                    
                    if received_key == expected_key:
                        resp = [0x67, 0x02]
                        stack.send(bytearray(resp))
                        print(f"[TX] ECU:    {bytes(resp).hex().upper()} (Unlocked!)")
                    else:
                        resp = [0x7F, 0x27, 0x35] # Invalid Key
                        stack.send(bytearray(resp))
                        print(f"[TX] ECU:    {bytes(resp).hex().upper()} (Invalid Key)")

                # 5. 0x30 Handshake (31 01 00 30 ...)
                elif len(req) > 4 and req[0:4] == bytearray([0x31, 0x01, 0x00, 0x30]):
                    resp = [0x71, 0x01, 0x00, 0x30] # Positive Response
                    stack.send(bytearray(resp))
                    print(f"[TX] ECU:    {bytes(resp).hex().upper()} (Handshake Accepted)")
                
                else:
                    print("[TX] ECU:    7F XX 11 (Service Not Supported)")
                    stack.send(bytearray([0x7F, req[0], 0x11]))

            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n[*] Simulator stopped.")

if __name__ == '__main__':
    main()
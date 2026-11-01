import can
import isotp
import time
import sys

CAN_INTERFACE = 'slcan'
DEFAULT_PORT = 'COM4'
BITRATE = 500000
ECU_TX_ID = 0x7E0
ECU_RX_ID = 0x7E8

def parse_capture(path):
    frames = []
    with open(path, 'r', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('Time'):
                continue
            parts = line.split(',')
            if len(parts) < 3:
                continue
            try:
                ts = float(parts[0])
                can_id = int(parts[2], 16)
            except ValueError:
                continue
            data_hex = ''.join(parts[3:]).replace(' ', '')
            frames.append((ts, can_id, bytes.fromhex(data_hex)))
    return frames

def reassemble(frames, tx_id=0x7E0):
    messages = []
    current = None
    expected = 0
    for ts, cid, data in frames:
        if cid != tx_id or not data:
            continue
        pci = data[0] >> 4
        if pci == 0:
            messages.append(data[1:1+(data[0] & 0x0F)])
        elif pci == 1:
            expected = ((data[0] & 0x0F) << 8) | data[1]
            current = bytearray(data[2:])
        elif pci == 2 and current is not None:
            current.extend(data[1:])
            if len(current) >= expected:
                messages.append(bytes(current[:expected]))
                current = None
    return messages

def main():
    if len(sys.argv) < 2:
        print('Usage: python replay_capture.py <capture.csv> [COMx]')
        sys.exit(1)
    port = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PORT
    messages = reassemble(parse_capture(sys.argv[1]))
    print('Reassembled', len(messages), 'tester messages')
    bus = can.interface.Bus(interface=CAN_INTERFACE, channel=port, bitrate=BITRATE)
    addr = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=ECU_TX_ID, rxid=ECU_RX_ID)
    stack = isotp.CanStack(bus=bus, address=addr, params={'blocking_send': True})
    for m in messages:
        print('[TX]', m.hex().upper())
        stack.send(bytearray(m))
        t = time.time() + 1.0
        while time.time() < t:
            stack.process()
            if stack.available():
                print('[RX]', stack.recv().hex().upper())
                break
            time.sleep(0.001)

if __name__ == '__main__':
    main()


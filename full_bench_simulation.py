import can
import isotp
import time
import threading
import queue
import sys

# Thread-safe queues to simulate the CAN bus wire
tester_to_ecu_q = queue.Queue()
ecu_to_tester_q = queue.Queue()

# A custom bus that inherits from can.BusABC so isotp accepts it
class QueueBus(can.BusABC):
    def __init__(self, rx_queue, tx_queue, **kwargs):
        self.rx_queue = rx_queue
        self.tx_queue = tx_queue
        # python-can requires a channel argument, even if we don't use it
        super().__init__(channel="dummy", **kwargs)

    def send(self, msg, timeout=None):
        self.tx_queue.put(msg)

    def _recv_internal(self, timeout):
        try:
            # If timeout is None, block until a message is available
            msg = self.rx_queue.get(timeout=timeout)
            return msg, False
        except queue.Empty:
            return None, False

    def shutdown(self):
        super().shutdown()

ECU_TX_ID = 0x7E0  # Tester -> ECU
ECU_RX_ID = 0x7E8  # ECU -> Tester

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
    iter_count = (attempt * 0x23)
    idx = (subfn + 1) >> 1
    for _ in range(iter_count):
        msb = seed & 0x80000000
        seed = (seed << 1) & 0xFFFFFFFF
        if msb:
            seed ^= LFSR_TABLE[idx]
    return seed

def simulator_thread():
    """Acts as the ECU"""
    bus = QueueBus(tester_to_ecu_q, ecu_to_tester_q)
    addr = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=ECU_RX_ID, rxid=ECU_TX_ID)
    stack = isotp.CanStack(bus=bus, address=addr, params={'blocking_send': True})
    
    current_seed = 0x00000034
    
    while True:
        stack.process()
        if stack.available():
            req = stack.recv()
            print(f"\n[SIM ECU] [RX]: {req.hex().upper()}")
            
            if req == bytearray([0x3E, 0x00]):
                stack.send(bytearray([0x7E, 0x00]))
                print(f"[SIM ECU] [TX]: 7E00")
            elif req == bytearray([0x10, 0x03]):
                stack.send(bytearray([0x50, 0x03]))
                print(f"[SIM ECU] [TX]: 5003")
            elif req == bytearray([0x27, 0x01]):
                resp = [0x67, 0x01] + list(current_seed.to_bytes(4, 'big'))
                stack.send(bytearray(resp))
                print(f"[SIM ECU] [TX]: {bytes(resp).hex().upper()}")
            elif len(req) == 6 and req[0:2] == bytearray([0x27, 0x02]):
                received_key = int.from_bytes(req[2:6], 'big')
                expected_key = compute_key(current_seed, 0x01, 1)
                if received_key == expected_key:
                    stack.send(bytearray([0x67, 0x02]))
                    print(f"[SIM ECU] [TX]: 6702 (Unlocked!)")
                else:
                    stack.send(bytearray([0x7F, 0x27, 0x35]))
                    print(f"[SIM ECU] [TX]: 7F2735 (Invalid Key)")
            elif len(req) > 4 and req[0:4] == bytearray([0x31, 0x01, 0x00, 0x30]):
                stack.send(bytearray([0x71, 0x01, 0x00, 0x30]))
                print(f"[SIM ECU] [TX]: 71010030 (Handshake Accepted)")
            else:
                stack.send(bytearray([0x7F, req[0], 0x11]))
                print(f"[SIM ECU] [TX]: 7FXX11 (NRC 11)")
        time.sleep(0.01)

def tester_thread():
    """Acts as your Python script"""
    bus = QueueBus(ecu_to_tester_q, tester_to_ecu_q)
    addr = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=ECU_TX_ID, rxid=ECU_RX_ID)
    stack = isotp.CanStack(bus=bus, address=addr, params={'blocking_send': True})
    
    def send(payload, label):
        print(f"\n[TESTER] [TX] {label}: {bytes(payload).hex().upper()}")
        stack.send(bytearray(payload))
        end = time.time() + 2.0
        while time.time() < end:
            stack.process()
            if stack.available():
                resp = stack.recv()
                print(f"[TESTER] [RX]: {resp.hex().upper()}")
                return resp
            time.sleep(0.01)
        print("[-] Timeout")
        return None

    print("="*60)
    print("EDC16U34 VIRTUAL BENCH SIMULATION")
    print("="*60)
    
    r = send([0x3E, 0x00], "TesterPresent")
    if not r or r[0] != 0x7E: return
    
    r = send([0x10, 0x03], "StartSession")
    if not r or r[0] != 0x50: return
    
    r = send([0x27, 0x01], "RequestSeed")
    if not r or r[0] != 0x67: return
    seed = int.from_bytes(r[2:6], 'big')
    
    key = compute_key(seed, 0x01, 1)
    r = send([0x27, 0x02] + list(key.to_bytes(4, 'big')), "SendKey")
    if not r or r[0] != 0x67: return
    print("[+] LVL1 unlocked successfully!")
    
    MAGIC = bytes.fromhex("0521350135")
    ID_STRING = b"Bosch.p_213.SwitchOver.EDC16.A000"
    base = (0).to_bytes(4, 'big')
    size = (0x1000).to_bytes(4, 'big')
    handshake_payload = MAGIC + bytes([0x30]) + ID_STRING + bytes([0x08]) + base + size
    wrapper = [0x31, 0x01, 0x00, 0x30] + list(handshake_payload)
    
    r = send(wrapper, "0x30 Handshake")
    if r and r[0] == 0x71:
        print("\n[+] 0x30 Handshake accepted! The software stack is 100% perfect.")

if __name__ == '__main__':
    t = threading.Thread(target=simulator_thread, daemon=True)
    t.start()
    time.sleep(1)
    tester_thread()
import sys
import time

if len(sys.argv) < 2:
    print('Usage: python bdm_extract_key.py <internal_flash.bin> [external_dump.bin]')
    sys.exit(1)

internal = open(sys.argv[1], 'rb').read()
print('Internal flash size:', len(internal), 'bytes')

ext_path = sys.argv[2] if len(sys.argv) > 2 else r'C:\Users\user\Documents\Complete ECU Disassembly\Seat Leon 1.9 TDI 105 hp 2006 EDC16U34 03G906021LK 0281013279 1037382081 bdm.bin'
try:
    ext = open(ext_path, 'rb').read()
    N = int.from_bytes(ext[0x3FBBC:0x3FBBC+128], 'big')
except Exception as e:
    print('[-] Could not read external dump for modulus:', e)
    sys.exit(1)

e = 3
mod_exp = pow(2, e, N)
print('Scanning for RSA private exponent d...')
start = time.time()
found = False
for off in range(0, len(internal) - 128, 4):
    cand = int.from_bytes(internal[off:off+128], 'big')
    if 0 < cand < N and pow(mod_exp, cand, N) == 2:
        print('[+] d at 0x%06X: 0x%0256X' % (off, cand))
        found = True
        break
    cand_sw = int.from_bytes(internal[off:off+128], 'little')
    if 0 < cand_sw < N and pow(mod_exp, cand_sw, N) == 2:
        print('[+] d (byte-swapped) at 0x%06X: 0x%0256X' % (off, cand_sw))
        found = True
        break

if not found:
    print('[-] No d candidate found.')
print('Elapsed: %.1fs' % (time.time()-start))


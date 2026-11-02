import os

base = r"C:\Users\user\Documents\Complete ECU Disassembly\EDC16U34-ReadWrite-Tool"

readme = """# EDC16U34 Read/Write & Security Tool

This repository contains the complete toolchain to unlock, checksum, and flash the Bosch EDC16U34 (VAG 03G906021KH) over OBD.

## The 0x33 RSA Bypass (OBD Unlock)
The ECU uses an RSA-1024 signature check on the `0x33` diagnostic service (Finish Flash). 
Through reverse engineering the bootloader, the signature verification function was located at `0x00023FE4`.

Instead of extracting the private key, we patch the bootloader to force a success return.
The function `FUN_00023fe4` checks the signature and outputs `0x61af3c8e` to signal a valid signature. By overwriting the beginning of this function with hardcoded assembly, we force it to always return success.

**The Patch (at `0x23FE4`):**
```assembly
li r3, 10            ; Set length/status to 10
stw r3, 0(r9)        ; Store to param_7
lis r3, 0x61AF
ori r3, r3, 0x3C8E   ; Load success token 0x61af3c8e
stw r3, 0(r10)       ; Store to param_8
blr                  ; Return
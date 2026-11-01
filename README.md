# EDC16U34 Read/Write Tool

Experimental CAN read/write tooling for Bosch EDC16U34.

Contents:
- bench_test.py: safe Phase 1 bench validation only (no 0x31/0x32/0x33).
- unlock_ecu_can.py
- full_flash_writer.py
- receive_flash_stream.py
- build_033_payload.py
- compute_key.py
- bdm_extract_key.py
- replay_capture.py
- edc16_fix_checksum.py

Limits:
- 0x33 finish requires a valid RSA-1024 signature. The private key was not found in the external 2MB flash.
- CAN read path is not validated on hardware.
- Bench-test only. Do not use on a daily-driven vehicle.

Safe first test: python bench_test.py --port COMx


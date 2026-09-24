#!/usr/bin/env python3
"""Let the stock Oplus process keep HandleFactory when PowerStats is owned elsewhere.

The original OTA binary aborts on its duplicate IPowerStats registration before it
registers the independent IHandleFactory service. Only the log severity of that
specific duplicate-registration branch changes from FATAL to ERROR.
"""

import hashlib
import pathlib
import sys


SOURCE_SHA256 = "8285a4f81cc3c85dd9636bedcc024afc135d1c4b8b04c64ab8cf7d07b96f5cb2"
PATCH_OFFSET = 0x82B4
BEFORE = bytes.fromhex("c3008052")  # AArch64: mov w3, #6 (FATAL)
AFTER = bytes.fromhex("83008052")   # AArch64: mov w3, #4 (ERROR)


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} SOURCE OUTPUT", file=sys.stderr)
        return 2

    source = pathlib.Path(sys.argv[1])
    output = pathlib.Path(sys.argv[2])
    binary = bytearray(source.read_bytes())
    actual_hash = hashlib.sha256(binary).hexdigest()
    if actual_hash != SOURCE_SHA256:
        raise SystemExit(f"unexpected source SHA-256: {actual_hash}")
    if binary[PATCH_OFFSET:PATCH_OFFSET + len(BEFORE)] != BEFORE:
        raise SystemExit("unexpected instruction at patch offset")

    binary[PATCH_OFFSET:PATCH_OFFSET + len(BEFORE)] = AFTER
    output.write_bytes(binary)
    print(hashlib.sha256(binary).hexdigest(), output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

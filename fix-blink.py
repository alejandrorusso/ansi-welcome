#!/usr/bin/env python3
"""Fix iCE color blinking in ANSI art files.

Converts SGR 5 (blink) + bg(40-47) to high-intensity background (100-107)
and removes the SGR 5. Modern terminals show actual blink instead of
high-intensity backgrounds, which is incorrect for iCE color ANSI art.

Usage: python3 fix-blink.py file1.ans [file2.ans ...]
"""

import struct
import sys


def read_sauce(data):
    if len(data) < 128:
        return len(data)
    sauce = data[-128:]
    if sauce[:7] != b'SAUCE00':
        return len(data)
    cut = len(data) - 128
    num_comments = sauce[104]
    if num_comments > 0:
        comnt_size = 5 + num_comments * 64
        if cut >= comnt_size and data[cut - comnt_size:cut - comnt_size + 5] == b'COMNT':
            cut -= comnt_size
    if cut > 0 and data[cut - 1] == 0x1A:
        cut -= 1
    return cut


def convert_ice_colors(data):
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b == 0x1B and i + 1 < n and data[i + 1] == 0x5B:
            j = i + 2
            while j < n and data[j] not in range(0x40, 0x7F):
                j += 1
            if j < n:
                j += 1
            seq = data[i:j]
            if seq[-1:] == b'm':
                params = seq[2:-1].split(b';')
                params = [p.strip() for p in params]
                has_blink = any(p == b'5' for p in params)
                if has_blink:
                    new_params = []
                    blink_used = False
                    for p in params:
                        if p == b'5' and not blink_used:
                            blink_used = True
                            continue
                        try:
                            val = int(p) if p else 0
                            if blink_used and 40 <= val <= 47:
                                new_params.append(str(val + 60).encode())
                            else:
                                new_params.append(p)
                        except ValueError:
                            new_params.append(p)
                    new_seq = b'\x1b[' + b';'.join(new_params) + b'm'
                    out.extend(new_seq)
                    i = j
                    continue
            out.extend(seq)
            i = j
            continue
        out.append(b)
        i += 1
    return bytes(out), out != bytearray(data)


if len(sys.argv) < 2:
    print(f"Usage: {sys.argv[0]} file1.ans [file2.ans ...]")
    sys.exit(1)

for filepath in sys.argv[1:]:
    with open(filepath, 'rb') as f:
        data = f.read()

    content_end = read_sauce(data)
    content = data[:content_end]
    sauce = data[content_end:]

    content, changed = convert_ice_colors(content)
    if changed:
        with open(filepath, 'wb') as f:
            f.write(content)
            f.write(sauce)
        print(f"Fixed: {filepath}")
    else:
        print(f"No blink: {filepath}")

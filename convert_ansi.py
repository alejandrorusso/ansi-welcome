#!/usr/bin/env python3
"""Convert CP437 ANSI art files to UTF-8 using iconv, then insert newlines at column boundaries."""

import os
import re
import struct
import subprocess
import sys
import tempfile


def read_sauce(path):
    """Read SAUCE record from file and return (width, content_size)."""
    with open(path, 'rb') as f:
        data = f.read()
    eof_idx = data.rfind(b'\x1a')
    if eof_idx != -1 and data[eof_idx+1:eof_idx+6] == b'SAUCE':
        sauce = data[eof_idx:]
        if len(sauce) >= 101:
            width = struct.unpack('<H', sauce[97:99])[0]
            return width, eof_idx
    return 80, len(data)


def wrap_ansi(text, width):
    """Insert newlines at column boundaries, skipping ANSI escape sequences."""
    col = 0
    out = []
    i = 0
    while i < len(text):
        ch = text[i]

        if ch == '\r':
            i += 1
            continue

        if ch == '\n':
            out.append('\n')
            col = 0
            i += 1
            continue

        # ANSI escape sequence — pass through, no column advance
        if ch == '\x1b' and i + 1 < len(text) and text[i + 1] == '[':
            j = i + 2
            while j < len(text) and ('\x30' <= text[j] <= '\x3f'):
                j += 1
            while j < len(text) and ('\x20' <= text[j] <= '\x2f'):
                j += 1
            if j < len(text):
                final = text[j]
                seq = text[i:j + 1]
                # Cursor forward ESC[nC — emit spaces
                if final == 'C':
                    m = re.search(r'\[(\d*)C', seq)
                    n = int(m.group(1)) if m and m.group(1) else 1
                    for _ in range(n):
                        if col >= width:
                            out.append('\n')
                            col = 0
                        out.append(' ')
                        col += 1
                else:
                    out.append(seq)
                i = j + 1
                continue
            out.append(ch)
            i += 1
            continue

        # Regular visible character
        if col >= width:
            out.append('\n')
            col = 0
        out.append(ch)
        col += 1
        i += 1

    return ''.join(out)


def process_file(src, dst):
    width, content_size = read_sauce(src)

    # Strip SAUCE, then let iconv do CP437→UTF-8
    with open(src, 'rb') as f:
        raw = f.read(content_size)

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ['iconv', '-f', 'CP437', '-t', 'UTF-8', tmp_path],
            capture_output=True, check=True
        )
        utf8_text = result.stdout.decode('utf-8')
    finally:
        os.unlink(tmp_path)

    wrapped = wrap_ansi(utf8_text, width)

    with open(dst, 'w', encoding='utf-8') as f:
        # Clear screen, move cursor home, reset colors
        f.write('\x1b[2J\x1b[H\x1b[0m')
        f.write(wrapped)
        f.write('\x1b[0m\n')

    return width


def sanitize_name(name):
    name = name.lower()
    out = []
    for c in name:
        if c.isalnum() or c == '.':
            out.append(c)
        else:
            out.append('_')
    result = re.sub(r'_+', '_', ''.join(out))
    result = result.lstrip('_')
    result = re.sub(r'_\.', '.', result)
    return result


def main():
    src_dir = '/vol/ansi-more'
    dst_dir = os.path.join(src_dir, 'converted')
    os.makedirs(dst_dir, exist_ok=True)

    for name in sorted(os.listdir(src_dir)):
        if not name.lower().endswith('.ans'):
            continue
        if name == '2026.utf8.ans':
            continue
        src = os.path.join(src_dir, name)
        if not os.path.isfile(src):
            continue
        new_name = sanitize_name(name)
        dst = os.path.join(dst_dir, new_name)
        width = process_file(src, dst)
        print(f'{name} -> converted/{new_name} (width={width})')


if __name__ == '__main__':
    main()

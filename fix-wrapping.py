#!/usr/bin/env python3
"""Fix ANSI art files that rely on 80-column terminal auto-wrap.

Reads each .ans file, checks if it lacks newlines (relying on auto-wrap),
and inserts \n at the correct column width (from SAUCE metadata or default 80).
Skips ANSI escape sequences when counting visible columns.

Usage: python3 fix-wrapping.py [directory]
"""

import os
import sys
import struct

def read_sauce(data):
    """Read SAUCE record from file data, return (width, sauce_start) or (None, len(data))."""
    if len(data) < 128:
        return None, len(data)
    sauce = data[-128:]
    if sauce[:7] != b'SAUCE00':
        return None, len(data)
    width = struct.unpack('<H', sauce[96:98])[0]
    cut = len(data) - 128
    # Check for COMNT block
    num_comments = sauce[104]
    if num_comments > 0:
        comnt_size = 5 + num_comments * 64
        if cut >= comnt_size and data[cut - comnt_size:cut - comnt_size + 5] == b'COMNT':
            cut -= comnt_size
    # Strip EOF marker
    if cut > 0 and data[cut - 1] == 0x1A:
        cut -= 1
    return width or 80, cut

def needs_wrapping(data, content_end):
    """Check if file has very few newlines relative to its size (relies on auto-wrap)."""
    content = data[:content_end]
    newline_count = content.count(b'\n')
    # Estimate expected lines: content bytes / width. If actual newlines are
    # less than half of expected, file probably relies on auto-wrap.
    return newline_count < 5

def add_wrapping(data, width):
    """Insert newlines at column boundaries, skipping ANSI escape sequences."""
    out = bytearray()
    col = 0
    i = 0
    n = len(data)

    while i < n:
        b = data[i]

        # ANSI escape sequence: ESC [ ... final_byte
        if b == 0x1B and i + 1 < n and data[i + 1] == 0x5B:
            j = i + 2
            while j < n and data[j] not in range(0x40, 0x7F):
                j += 1
            if j < n:
                j += 1
            out.extend(data[i:j])
            i = j
            continue

        # CR
        if b == 0x0D:
            out.append(b)
            col = 0
            i += 1
            continue

        # LF
        if b == 0x0A:
            out.append(b)
            col = 0
            i += 1
            continue

        # Visible character
        out.append(b)
        col += 1

        if col >= width:
            out.append(0x0A)  # insert newline
            col = 0

        i += 1

    return bytes(out)

def process_file(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()

    width, content_end = read_sauce(data)
    if width is None:
        width = 80

    if not needs_wrapping(data, content_end):
        return False

    content = data[:content_end]
    sauce = data[content_end:]

    fixed = add_wrapping(content, width)

    with open(filepath, 'wb') as f:
        f.write(fixed)
        f.write(sauce)

    return True

directory = sys.argv[1] if len(sys.argv) > 1 else '.'
count = 0

for fname in sorted(os.listdir(directory)):
    if not fname.endswith('.ans'):
        continue
    path = os.path.join(directory, fname)
    if process_file(path):
        print(f"Fixed: {fname}")
        count += 1
    else:
        print(f"OK:    {fname}")

print(f"\nFixed {count} files.")

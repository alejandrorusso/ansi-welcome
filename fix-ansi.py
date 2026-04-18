#!/usr/bin/env python3
"""Fix ANSI art files for modern terminal rendering.

Handles:
1. Missing newlines (auto-wrap at SAUCE width or 80 cols)
2. CP437 control characters (0x00-0x1F, 0x7F) replaced with their UTF-8 glyph equivalents
3. UTF-8 files detected and skipped for CP437 control-char replacement

Usage: python3 fix-ansi.py [directory]
"""

import os
import sys
import struct

# CP437 glyphs for bytes 0x00-0x1F and 0x7F that iconv doesn't convert
# These are visible characters in CP437 but control codes in ASCII/UTF-8
CP437_CONTROL_GLYPHS = {
    0x01: b'\xe2\x98\xba',  # ☺
    0x02: b'\xe2\x98\xbb',  # ☻
    0x03: b'\xe2\x99\xa5',  # ♥
    0x04: b'\xe2\x99\xa6',  # ♦
    0x05: b'\xe2\x99\xa3',  # ♣
    0x06: b'\xe2\x99\xa0',  # ♠
    0x07: b'\xe2\x80\xa2',  # • (bullet, for BEL)
    0x08: b'\xe2\x97\x98',  # ◘
    0x09: b'\xe2\x97\x8b',  # ○ (but keep TAB as tab? no, in ANSI art 0x09 is ○)
    0x0B: b'\xe2\x99\x82',  # ♂
    0x0C: b'\xe2\x99\x80',  # ♀
    0x0E: b'\xe2\x99\xab',  # ♫
    0x0F: b'\xe2\x98\xbc',  # ☼
    0x10: b'\xe2\x96\xba',  # ►
    0x11: b'\xe2\x97\x84',  # ◄
    0x12: b'\xe2\x86\x95',  # ↕
    0x13: b'\xe2\x80\xbc',  # ‼
    0x14: b'\xc2\xb6',      # ¶
    0x15: b'\xc2\xa7',      # §
    0x16: b'\xe2\x96\xac',  # ▬
    0x17: b'\xe2\x86\xa8',  # ↨
    0x18: b'\xe2\x86\x91',  # ↑
    0x19: b'\xe2\x86\x93',  # ↓
    0x1A: b'\xe2\x86\x92',  # →
    0x1B: b'\xe2\x86\x90',  # ← (but 0x1B is ESC - handled separately)
    0x1C: b'\xe2\x88\x9f',  # ∟
    0x1D: b'\xe2\x86\x94',  # ↔
    0x1E: b'\xe2\x96\xb2',  # ▲
    0x1F: b'\xe2\x96\xbc',  # ▼
    0x7F: b'\xe2\x8c\x82',  # ⌂
}


def read_sauce(data):
    """Read SAUCE record from file data, return (width, sauce_start) or (None, len(data))."""
    if len(data) < 128:
        return None, len(data)
    sauce = data[-128:]
    if sauce[:7] != b'SAUCE00':
        return None, len(data)
    width = struct.unpack('<H', sauce[96:98])[0]
    cut = len(data) - 128
    num_comments = sauce[104]
    if num_comments > 0:
        comnt_size = 5 + num_comments * 64
        if cut >= comnt_size and data[cut - comnt_size:cut - comnt_size + 5] == b'COMNT':
            cut -= comnt_size
    if cut > 0 and data[cut - 1] == 0x1A:
        cut -= 1
    return width or 80, cut


def is_utf8(data):
    """Check if data is valid UTF-8 with multi-byte sequences (not just ASCII)."""
    try:
        text = data.decode('utf-8')
        # Check if there are actual multi-byte chars (not just ASCII)
        return any(ord(c) > 127 for c in text)
    except UnicodeDecodeError:
        return False


def has_lines_exceeding_width(data, width):
    """Check if any line has visible characters exceeding the target width."""
    col = 0
    i = 0
    n = len(data)

    while i < n:
        b = data[i]

        # ANSI escape sequence
        if b == 0x1B and i + 1 < n and data[i + 1] == 0x5B:
            j = i + 2
            while j < n and data[j] not in range(0x40, 0x7F):
                j += 1
            if j < n:
                j += 1
            i = j
            continue

        if b in (0x0D, 0x0A):
            if col > width:
                return True
            col = 0
            i += 1
            continue

        col += 1
        i += 1

    return col > width


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

        if b == 0x0D:
            out.append(b)
            col = 0
            i += 1
            continue

        if b == 0x0A:
            out.append(b)
            col = 0
            i += 1
            continue

        out.append(b)
        col += 1

        if col >= width:
            out.append(0x0A)
            col = 0

        i += 1

    return bytes(out)


def replace_control_chars(data):
    """Replace CP437 control character glyphs with their UTF-8 equivalents.

    Must be done on raw CP437 data BEFORE iconv, so we replace the byte with
    a marker, then the marker survives iconv. Actually, since we want UTF-8 output,
    we do this AFTER iconv on the UTF-8 output. But iconv passes control chars through
    unchanged, so we can replace them in the raw CP437 data with placeholder sequences
    that won't be mangled by iconv.

    Simpler approach: replace directly in the raw bytes, since these bytes would just
    pass through iconv unchanged anyway. We replace them with multi-byte UTF-8 sequences
    that iconv will also pass through (since they're valid UTF-8 already and iconv from
    cp437 maps the individual bytes... wait, that won't work).

    Best approach: do the replacement at the byte level, and mark the file to skip
    iconv for these bytes. Since that's complex, let's just pre-convert: replace
    control chars with their CP437 glyph UTF-8 bytes, and also convert all other
    bytes from CP437 to UTF-8 ourselves, eliminating the need for iconv entirely.
    """
    out = bytearray()
    i = 0
    n = len(data)

    while i < n:
        b = data[i]

        # Don't touch ESC - it's used for ANSI escape sequences
        if b == 0x1B:
            out.append(b)
            i += 1
            continue

        # Don't touch CR, LF - they're actual line endings
        if b in (0x0A, 0x0D):
            out.append(b)
            i += 1
            continue

        # Replace control chars and DEL with CP437 glyphs
        if b in CP437_CONTROL_GLYPHS:
            out.extend(CP437_CONTROL_GLYPHS[b])
            i += 1
            continue

        # Regular byte - keep as-is (will be converted by iconv later)
        out.append(b)
        i += 1

    return bytes(out)


def fix_color_bleed(data):
    """Insert \\e[0m before newlines when a background color is active.

    Modern terminals with BCE (Background Color Erase) extend background colors
    to the right edge of the terminal. Classic ANSI art expects colors to stop
    at the last written character. This fix resets attributes before each newline
    where a non-default background is active.
    """
    out = bytearray()
    bg_active = False
    i = 0
    n = len(data)

    while i < n:
        b = data[i]

        # Parse ANSI escape sequences
        if b == 0x1B and i + 1 < n and data[i + 1] == 0x5B:
            # Find the full CSI sequence
            j = i + 2
            while j < n and data[j] not in range(0x40, 0x7F):
                j += 1
            if j < n:
                j += 1
            seq = data[i:j]

            # Check if it's an SGR sequence (ends with 'm')
            if seq[-1:] == b'm':
                params = seq[2:-1]  # between ESC[ and m
                # Parse semicolon-separated params
                for p in params.split(b';'):
                    p = p.strip()
                    if p in (b'', b'0'):
                        bg_active = False
                    elif p in (b'40', b'49'):
                        bg_active = False
                    elif len(p) <= 3:
                        try:
                            val = int(p)
                            if 41 <= val <= 47 or 100 <= val <= 107:
                                bg_active = True
                            elif val == 48:
                                bg_active = True  # 256/RGB bg
                        except ValueError:
                            pass

            out.extend(seq)
            i = j
            continue

        if b == 0x0A:
            if bg_active:
                out.extend(b'\x1b[0m')
                bg_active = False
            out.append(b)
            i += 1
            continue

        out.append(b)
        i += 1

    return bytes(out), out != bytearray(data)


def process_file(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()

    width, content_end = read_sauce(data)
    if width is None:
        width = 80

    content = data[:content_end]
    sauce = data[content_end:]

    changes = []
    utf8_file = is_utf8(content)

    # Fix 1: Replace CP437 control character glyphs (only for non-UTF8 files)
    if not utf8_file:
        has_control = any(
            b in CP437_CONTROL_GLYPHS and b != 0x1B
            for b in content
            if b not in (0x0A, 0x0D)
        )
        if has_control:
            content = replace_control_chars(content)
            changes.append("control-chars")

    # Fix 2: Add wrapping where lines exceed the target width
    if has_lines_exceeding_width(content, width):
        content = add_wrapping(content, width)
        changes.append(f"wrap@{width}")

    # Fix 3: Reset background color before newlines (BCE bleed fix)
    content, had_bleed = fix_color_bleed(content)
    if had_bleed:
        changes.append("bce-fix")

    # Fix 4: Mark UTF-8 files by renaming (so render script can skip iconv)
    if utf8_file and not filepath.endswith('.utf8.ans'):
        base = filepath.rsplit('.ans', 1)[0]
        new_path = base + '.utf8.ans'
        with open(new_path, 'wb') as f:
            f.write(content)
            f.write(sauce)
        os.remove(filepath)
        changes.append(f"renamed→{os.path.basename(new_path)}")
        return changes

    if changes:
        with open(filepath, 'wb') as f:
            f.write(content)
            f.write(sauce)

    return changes


directory = sys.argv[1] if len(sys.argv) > 1 else '.'
fixed = 0

for fname in sorted(os.listdir(directory)):
    if not fname.endswith('.ans'):
        continue
    path = os.path.join(directory, fname)
    changes = process_file(path)
    if changes:
        print(f"Fixed: {fname} [{', '.join(changes)}]")
        fixed += 1
    else:
        print(f"OK:    {fname}")

print(f"\nFixed {fixed} files.")

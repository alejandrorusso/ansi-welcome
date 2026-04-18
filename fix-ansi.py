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
    """Read SAUCE record from file data, return (width, sauce_start, ice_colors)."""
    if len(data) < 128:
        return None, len(data), False
    sauce = data[-128:]
    if sauce[:7] != b'SAUCE00':
        return None, len(data), False
    width = struct.unpack('<H', sauce[96:98])[0]
    flags = sauce[105]
    ice_colors = bool(flags & 0x01)
    cut = len(data) - 128
    num_comments = sauce[104]
    if num_comments > 0:
        comnt_size = 5 + num_comments * 64
        if cut >= comnt_size and data[cut - comnt_size:cut - comnt_size + 5] == b'COMNT':
            cut -= comnt_size
    if cut > 0 and data[cut - 1] == 0x1A:
        cut -= 1
    return width or 80, cut, ice_colors


def is_utf8(data):
    """Check if data is valid UTF-8 with multi-byte sequences (not just ASCII)."""
    try:
        text = data.decode('utf-8')
        # Check if there are actual multi-byte chars (not just ASCII)
        return any(ord(c) > 127 for c in text)
    except UnicodeDecodeError:
        return False


def parse_csi_cursor_advance(data, start, end):
    """Return how many columns a CSI sequence advances the cursor, or 0."""
    seq = data[start:end]
    final = seq[-1:]
    if final == b'C':  # Cursor Forward
        params = seq[2:-1]
        try:
            return int(params) if params else 1
        except ValueError:
            return 1
    return 0


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
            col += parse_csi_cursor_advance(data, i, j)
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
    """Insert newlines at column boundaries, accounting for cursor movement.

    Preserves original LFs at positions < width (intentional short lines).
    Suppresses original LFs right after a wrapping newline (redundant).
    Strips CR bytes.
    """
    out = bytearray()
    col = 0
    just_wrapped = False
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
            advance = parse_csi_cursor_advance(data, i, j)
            if advance > 0 and col + advance >= width:
                out.append(0x0A)
                col = 0
                just_wrapped = True
            out.extend(data[i:j])
            col += advance
            if advance > 0:
                just_wrapped = False
            i = j
            continue

        # Strip CR
        if b == 0x0D:
            i += 1
            continue

        # LF handling: suppress if redundant (right after a wrap), keep otherwise
        if b == 0x0A:
            if just_wrapped:
                just_wrapped = False
            else:
                out.append(b)
                col = 0
            i += 1
            continue

        just_wrapped = False
        out.append(b)
        col += 1

        if col >= width:
            out.append(0x0A)
            col = 0
            just_wrapped = True

        i += 1

    return bytes(out)


def full_cp437_to_utf8(data):
    """Convert CP437 data to UTF-8, handling control chars as visible glyphs.

    Does the full conversion in Python so iconv is not needed. Control chars
    (0x00-0x1F, 0x7F) that are visible glyphs in CP437 get their correct
    UTF-8 representation. ANSI escape sequences (ESC [...) are passed through
    as-is. CR and LF are kept as line endings.
    """
    out = bytearray()
    i = 0
    n = len(data)

    while i < n:
        b = data[i]

        # ANSI escape sequence: pass through raw (they're ASCII-safe)
        if b == 0x1B and i + 1 < n and data[i + 1] == 0x5B:
            j = i + 2
            while j < n and data[j] not in range(0x40, 0x7F):
                j += 1
            if j < n:
                j += 1
            out.extend(data[i:j])
            i = j
            continue

        # ESC not followed by [ — pass through raw
        if b == 0x1B:
            out.append(b)
            i += 1
            continue

        # Keep CR, LF as line endings
        if b in (0x0A, 0x0D):
            out.append(b)
            i += 1
            continue

        # Control chars and DEL → CP437 visible glyphs
        if b in CP437_CONTROL_GLYPHS:
            out.extend(CP437_CONTROL_GLYPHS[b])
            i += 1
            continue

        # Regular byte: convert from CP437 to UTF-8
        try:
            out.extend(bytes([b]).decode('cp437').encode('utf-8'))
        except (UnicodeDecodeError, UnicodeEncodeError):
            out.append(b)
        i += 1

    return bytes(out)


def convert_ice_colors(data):
    """Convert iCE color SGR sequences to modern high-intensity background codes.

    In iCE color mode, SGR 5 (blink) is repurposed to mean 'use high-intensity
    background'. Modern terminals don't support iCE — they show actual blink.
    This converts SGR 5 + bg(40-47) to bg(100-107) and removes the SGR 5.
    """
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

            # Only transform SGR sequences (ending with 'm')
            if seq[-1:] == b'm':
                params = seq[2:-1].split(b';')
                params = [p.strip() for p in params]

                has_blink = False
                for p in params:
                    if p == b'5':
                        has_blink = True
                        break

                if has_blink:
                    new_params = []
                    blink_used = False
                    for p in params:
                        if p == b'5' and not blink_used:
                            blink_used = True
                            continue  # Remove SGR 5
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


def fix_color_bleed(data):
    """Insert \\e[49m before newlines when a background color is active.

    Modern terminals with BCE (Background Color Erase) extend background colors
    to the right edge of the terminal. Classic ANSI art expects colors to stop
    at the last written character. This fix resets only the background before each
    newline, preserving foreground color and other attributes like bold.
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
                    elif p == b'49':
                        bg_active = False  # default background only
                    elif len(p) <= 3:
                        try:
                            val = int(p)
                            if 40 <= val <= 47 or 48 == val or 100 <= val <= 107:
                                bg_active = True  # any explicit bg, including black
                        except ValueError:
                            pass

            out.extend(seq)
            i = j
            continue

        if b == 0x0A:
            if bg_active:
                out.extend(b'\x1b[49m')  # reset background only, keep fg/bold
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

    width, content_end, ice_colors = read_sauce(data)
    if width is None:
        width = 80

    content = data[:content_end]
    sauce = data[content_end:]

    changes = []

    # Fix 0: Strip CR bytes — modern terminals only need LF for line breaks,
    # and CR can cause rendering artifacts (cursor reset + BCE bleed)
    if b'\r' in content:
        content = content.replace(b'\r', b'')
        changes.append("strip-cr")

    # Fix 0b: Convert iCE color blink→high-intensity background
    if ice_colors:
        content, had_ice = convert_ice_colors(content)
        if had_ice:
            changes.append("ice-colors")

    utf8_file = is_utf8(content)

    # Fix 1: Check if file has CP437 control chars that need glyph conversion
    has_control = False
    if not utf8_file:
        has_control = any(
            b in CP437_CONTROL_GLYPHS and b != 0x1B
            for b in content
            if b not in (0x0A, 0x0D)
        )

    # Fix 2: Add wrapping where lines exceed the target width
    if has_lines_exceeding_width(content, width):
        content = add_wrapping(content, width)
        changes.append(f"wrap@{width}")

    # Fix 3: Reset background color before newlines (BCE bleed fix)
    content, had_bleed = fix_color_bleed(content)
    if had_bleed:
        changes.append("bce-fix")

    # Fix 4: Full CP437→UTF-8 conversion for files with control chars
    # This does the complete conversion so iconv is not needed, avoiding
    # double-conversion of control char glyphs. Save as .utf8.ans.
    if has_control and not filepath.endswith('.utf8.ans'):
        content = full_cp437_to_utf8(content)
        base = filepath.rsplit('.ans', 1)[0]
        new_path = base + '.utf8.ans'
        with open(new_path, 'wb') as f:
            f.write(content)
            f.write(sauce)
        os.remove(filepath)
        changes.append(f"cp437→utf8→{os.path.basename(new_path)}")
        return changes

    # Fix 5: Mark already-UTF-8 files by renaming (so render script can skip iconv)
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

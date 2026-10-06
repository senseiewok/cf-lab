"""check-ascii.py — check ASCII-art blocks in Markdown files.

Usage:
    python check-ascii.py [--max-width N] [--strict] FILE [FILE ...]

Options:
    --max-width N   Maximum allowed display width (default 60)
    --strict        Warnings also cause exit code 1

Exit codes:
    0   No errors (and no warnings with --strict)
    1   One or more errors (or warnings with --strict)
    2   Usage error or file not found

Finding codes:
    ERROR: tab, control-char, invisible-char, too-wide, ragged-frame, no-description, unclosed-fence
    WARN:  trailing-space, wide-glyph

invisible-char is any Unicode format character (category Cf: zero-width space, word joiner, soft hyphen, BOM, ...).
They take no column and show nothing, so they only arrive by accident, usually when a fence is retyped by hand
instead of generated, and they survive copy-paste into other people's files. Emoji joined with U+200D are not used in
this lab's art; if a piece ever needs them, add an allowance here on purpose.
"""

import sys
import argparse
import unicodedata


def display_width(s: str) -> int:
    total = 0
    for ch in s:
        cp = ord(ch)
        if unicodedata.combining(ch) != 0:
            continue
        if cp in (0x200B, 0x200C, 0x200D, 0x2060):
            continue
        if 0xFE00 <= cp <= 0xFE0F:
            continue
        eaw = unicodedata.east_asian_width(ch)
        if eaw in ('W', 'F'):
            total += 2
        else:
            total += 1
    return total


def is_wide_glyph(ch: str) -> bool:
    cp = ord(ch)
    if unicodedata.east_asian_width(ch) in ('W', 'F'):
        return True
    if 0x2600 <= cp <= 0x27BF:
        return True
    if 0x1F000 <= cp <= 0x1FAFF:
        return True
    return False


def has_control_char(s: str) -> bool:
    for ch in s:
        cp = ord(ch)
        if cp == 9:
            continue
        if cp < 32 or 0x7F <= cp <= 0x9F:
            return True
    return False


def has_invisible_char(s: str) -> bool:
    return any(unicodedata.category(ch) == 'Cf' for ch in s)


def is_blank(s: str) -> bool:
    return s.strip() == ''


def find_closing_fence(lines, start_idx, fence_len):
    for j in range(start_idx, len(lines)):
        line = lines[j]
        if line and all(c == '`' for c in line) and len(line) >= fence_len:
            return j
    return -1


def check_block_lines(lines, start_idx, end_idx, max_width):
    findings = []

    non_blank = [(i, lines[i]) for i in range(start_idx, end_idx) if not is_blank(lines[i])]
    is_frame = False
    if non_blank:
        first_s = non_blank[0][1]
        last_s = non_blank[-1][1]
        top_left = {'+', '\u250C', '\u2554', '\u256D'}
        top_right = {'+', '\u2510', '\u2557', '\u256E'}
        bot_left = {'+', '\u2514', '\u255A', '\u2570'}
        bot_right = {'+', '\u2518', '\u255D', '\u256F'}
        fs = first_s.rstrip(' ')
        ls = last_s.rstrip(' ')
        if (fs and fs[0] in top_left and fs[-1] in top_right and
                ls and ls[0] in bot_left and ls[-1] in bot_right):
            is_frame = True

    if is_frame:
        ref_width = display_width(non_blank[0][1].rstrip(' '))
        for i, s in non_blank:
            w = display_width(s.rstrip(' '))
            if w != ref_width:
                findings.append(('ERROR', i + 1, 'ragged-frame',
                                f'line width {w} differs from frame width {ref_width}'))

    for i in range(start_idx, end_idx):
        s = lines[i]
        ln = i + 1
        if '\t' in s:
            findings.append(('ERROR', ln, 'tab', 'line contains a tab character'))
        if has_control_char(s):
            findings.append(('ERROR', ln, 'control-char', 'line contains a control character'))
        if has_invisible_char(s):
            findings.append(('ERROR', ln, 'invisible-char',
                             'line contains an invisible format character (zero-width space, word joiner, ...)'))
        w = display_width(s)
        if w > max_width:
            findings.append(('ERROR', ln, 'too-wide', f'line width {w} exceeds maximum {max_width}'))
        if s.endswith(' '):
            findings.append(('WARN', ln, 'trailing-space', 'line ends with a space'))
        if any(is_wide_glyph(ch) for ch in s):
            findings.append(('WARN', ln, 'wide-glyph', 'line contains wide or emoji characters'))

    return findings


def process_file(path, max_width):
    with open(path, 'r', encoding='utf-8', newline=None) as f:
        content = f.read()

    lines = content.split('\n')
    if lines and lines[-1] == '':
        lines = lines[:-1]

    findings = []
    num_blocks = 0
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        if line.startswith('```'):
            fence_len = 0
            for c in line:
                if c == '`':
                    fence_len += 1
                else:
                    break
            if fence_len >= 3:
                info = line[fence_len:].strip()
                valid = ('', 'text', 'ascii', 'txt')

                if info in valid:
                    close_idx = find_closing_fence(lines, i + 1, fence_len)
                    if close_idx == -1:
                        findings.append(('ERROR', i + 1, 'unclosed-fence',
                                         'art block is never closed'))
                        num_blocks += 1
                        break
                    else:
                        num_blocks += 1
                        if close_idx > i + 1:
                            findings.extend(check_block_lines(lines, i + 1, close_idx, max_width))

                        k = close_idx + 1
                        desc_found = False
                        while k < n:
                            if not is_blank(lines[k]):
                                dl = lines[k]
                                if dl.startswith('`') or dl.startswith('#') or dl.startswith('|'):
                                    desc_found = False
                                else:
                                    desc_found = True
                                break
                            k += 1
                        if not desc_found:
                            findings.append(('ERROR', close_idx + 1, 'no-description',
                                             'missing description after art block'))

                        i = close_idx + 1
                        continue
                else:
                    close_idx = find_closing_fence(lines, i + 1, fence_len)
                    if close_idx == -1:
                        break
                    else:
                        i = close_idx + 1
                        continue

        i += 1

    return findings, num_blocks


def main():
    parser = argparse.ArgumentParser(prog='check-ascii.py')
    parser.add_argument('--max-width', type=int, default=60)
    parser.add_argument('--strict', action='store_true')
    parser.add_argument('files', nargs='*')
    args = parser.parse_args()

    usage = 'Usage: python check-ascii.py [--max-width N] [--strict] FILE [FILE ...]'

    if not args.files:
        print(usage, file=sys.stderr)
        return 2

    all_findings = []
    total_blocks = 0

    for path in args.files:
        try:
            findings, num_blocks = process_file(path, args.max_width)
        except (OSError, UnicodeDecodeError):
            print(usage, file=sys.stderr)
            return 2

        total_blocks += num_blocks
        for level, ln, code, msg in findings:
            all_findings.append((level, path, ln, code, msg))

    for level, path, ln, code, msg in all_findings:
        print(f'{level} {path}:{ln}: {code}: {msg}')

    e_count = sum(1 for f in all_findings if f[0] == 'ERROR')
    w_count = sum(1 for f in all_findings if f[0] == 'WARN')
    print(f'{total_blocks} art block(s) checked: {e_count} error(s), {w_count} warning(s)')

    if e_count > 0 or (args.strict and w_count > 0):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

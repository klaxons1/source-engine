#!/usr/bin/env python3
"""Offline validation of the exact bundled TrueType fonts and Cyrillic cmaps."""
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]


def glyph(data, cmap, codepoint):
    count = struct.unpack_from('>H', data, cmap + 2)[0]
    for i in range(count):
        platform, encoding, offset = struct.unpack_from('>HHI', data, cmap + 4 + i * 8)
        if platform not in (0, 3):
            continue
        table = cmap + offset
        fmt = struct.unpack_from('>H', data, table)[0]
        if fmt == 12:
            groups = struct.unpack_from('>I', data, table + 12)[0]
            for j in range(groups):
                start, end, base = struct.unpack_from('>III', data, table + 16 + j * 12)
                if start <= codepoint <= end:
                    return base + codepoint - start
        if fmt == 4 and codepoint <= 65535:
            segments = struct.unpack_from('>H', data, table + 6)[0] // 2
            ends = table + 14
            starts = ends + segments * 2 + 2
            deltas = starts + segments * 2
            ranges = deltas + segments * 2
            for j in range(segments):
                start = struct.unpack_from('>H', data, starts + j * 2)[0]
                end = struct.unpack_from('>H', data, ends + j * 2)[0]
                if not start <= codepoint <= end:
                    continue
                delta = struct.unpack_from('>h', data, deltas + j * 2)[0]
                offset = struct.unpack_from('>H', data, ranges + j * 2)[0]
                index = codepoint if not offset else struct.unpack_from('>H', data, ranges + j * 2 + offset + (codepoint - start) * 2)[0]
                return (index + delta) & 65535 if index else 0
    return 0


def audit():
    root = ROOT / 'assets/android/fonts'
    manifest = json.loads((root / 'manifest.json').read_text())
    assert manifest['revision'] == '4aeb773422464799998d900198b35cb80e94b3e1'
    required = {'dejavusans.ttf', 'dejavusans-bold.ttf', 'dejavusans-oblique.ttf',
                'dejavusans-boldoblique.ttf', 'LiberationMono-Regular.ttf', 'LICENSE_DEJAVU.txt'}
    assert set(manifest['files']) == required
    for name, meta in manifest['files'].items():
        data = (root / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == meta['sha256'], name
        if not name.endswith('.ttf'):
            assert b'Bitstream' in data and b'DejaVu' in data
            continue
        assert data[:4] == b'\x00\x01\x00\x00', name
        count = struct.unpack_from('>H', data, 4)[0]
        tables = {}
        for i in range(count):
            tag, checksum, offset, length = struct.unpack_from('>4sIII', data, 12 + i * 16)
            assert offset + length <= len(data), name
            tables[tag] = offset
        assert {b'cmap', b'glyf', b'head', b'loca', b'name'} <= tables.keys(), name
        for char in 'UnderhellПриветЁёЯя0123456789':
            assert glyph(data, tables[b'cmap'], ord(char)), (name, char)
    print('PASS: 5 pinned TrueType fonts, Latin/Cyrillic glyph maps, SHA256 and redistribution license')


if __name__ == '__main__':
    audit()

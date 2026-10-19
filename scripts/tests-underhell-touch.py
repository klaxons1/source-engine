#!/usr/bin/env python3
"""Check real VTFs/VPK contents and execute the production C++ touch policy."""
import importlib.util
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("underhell_touch_assets", ROOT / "scripts/build-underhell-touch-assets.py")
assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assets)


def unpack_vpk(data):
    magic, version, tree_size = struct.unpack_from('<III', data)
    assert (magic, version) == (0x55aa1234, 1)
    cursor, result = 12, {}
    payload = 12 + tree_size

    def string():
        nonlocal cursor
        end = data.index(0, cursor)
        value = data[cursor:end].decode()
        cursor = end + 1
        return value

    while True:
        extension = string()
        if not extension: break
        while True:
            directory = string()
            if not directory: break
            while True:
                name = string()
                if not name: break
                crc, preload, archive, offset, size, terminator = struct.unpack_from('<IHHIIH', data, cursor)
                cursor += 18
                assert (preload, archive, terminator) == (0, 0x7fff, 0xffff)
                entry = data[payload+offset:payload+offset+size]
                assert len(entry) == size and zlib.crc32(entry) == crc
                result[directory + '/' + name + '.' + extension] = entry
    assert cursor == payload
    return result


class TouchTests(unittest.TestCase):
    def test_generated_files_and_vtf_headers(self):
        for name, data in assets.outputs().items():
            self.assertEqual((ROOT / name).read_bytes(), data, name)
            if name.endswith('.vtf'):
                self.assertEqual(struct.unpack_from('<4sIIIHHIHH', data),
                                 (b'VTF\0', 7, 2, 80, 64, 64, 0x230c, 1, 0))
                self.assertEqual(struct.unpack_from('<fIBiBBH', data, 48), (1., 0, 1, -1, 0, 0, 1))
                self.assertEqual(len(data), 80 + 64*64*4)
                self.assertIn(0, data[83::4])
                self.assertIn(255, data[83::4])

    def test_vpk_inline_offsets_crc_and_case(self):
        prefix = 'assets/underhell/'
        files = {name[len(prefix):]: data for name, data in assets.outputs().items()
                 if name.startswith(prefix+'materials/')}
        packed = assets.pack_vpk(files)
        self.assertEqual(assets.pack_vpk(files), packed)
        self.assertEqual(unpack_vpk(packed), files)
        self.assertEqual(len(files), 30)
        self.assertTrue(all(name == name.lower() for name in files))
        self.assertNotIn('gameinfo.txt', files)  # Never replace the user's resource search paths.

    @unittest.skipUnless(shutil.which('g++'), 'g++ not installed')
    def test_native_policy_and_embedded_pixels(self):
        with tempfile.TemporaryDirectory(prefix='underhell-touch-test-') as tmp:
            binary = str(Path(tmp) / 'touch-test')
            subprocess.run(['g++', '-std=c++11', '-O2', '-I'+str(ROOT / 'game/client'),
                            str(ROOT / 'scripts/tests/underhell-touch-test.cpp'), '-o', binary], check=True)
            subprocess.run([binary, str(ROOT)], check=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)

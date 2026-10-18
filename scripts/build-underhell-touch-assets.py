#!/usr/bin/env python3
"""Reproducible, dependency-free 64px touch icons: VTF 7.2 + embedded RLE fallback.

The fallback uses the exact same pixels as the VTFs and is packed into the normal
client touch atlas. No external resource installation is needed to see the buttons.
"""
import argparse
import json
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parent.parent
SIZE = 64
PALETTE = [(0, 0, 0, 0), (12, 23, 29, 180), (125, 200, 205, 220), (245, 252, 252, 255)]
# Lowercase texture/button identifiers; actual server command spelling retained.
BUTTONS = [
    ("inventory", "cl_inventoryToggle", .15, .02),
    ("aim", "ironsight_toggle", .217, .02),
    ("nightvision", "NightVision_Toggle", .284, .02),
    ("gasmask", "GasMask_Toggle", .351, .02),
    ("laser", "laser_toggle", .15, .18),
    ("silencer", "silencer_toggle", .217, .18),
    ("firemode", "firemode_toggle", .284, .18),
    ("objective", "DispObj", .351, .18),
    ("kick", "uh_jake_kick", .52, .18),
    ("grenade", "Throw_Nade", .587, .18),
    ("bullettime", "impulse 110", .654, .18),
    ("drop", "DropWeapon", .52, .34),
    ("signal", "GiveSign", .587, .34),
    ("skip", "SkipScene", .654, .34),
    ("performance", "uh_android_fast_toggle", .52, .02),
]


def icon(name):
    pixels = [0] * (SIZE * SIZE)

    def dot(x, y, color=3, radius=1):
        for yy in range(y-radius, y+radius+1):
            for xx in range(x-radius, x+radius+1):
                if 0 <= xx < SIZE and 0 <= yy < SIZE:
                    pixels[yy*SIZE+xx] = color

    def line(x1, y1, x2, y2, color=3, radius=1):
        steps = max(abs(x2-x1), abs(y2-y1), 1)
        for i in range(steps+1):
            dot(round(x1+(x2-x1)*i/steps), round(y1+(y2-y1)*i/steps), color, radius)

    def rect(x1, y1, x2, y2, color=3):
        for a, b, c, d in ((x1,y1,x2,y1), (x2,y1,x2,y2), (x2,y2,x1,y2), (x1,y2,x1,y1)):
            line(a,b,c,d,color)

    def circle(cx, cy, radius, color=3):
        for y in range(cy-radius-1, cy+radius+2):
            for x in range(cx-radius-1, cx+radius+2):
                if (radius-1)**2 <= (x-cx)**2+(y-cy)**2 <= (radius+1)**2:
                    dot(x,y,color,0)

    # Rounded square, transparent outside and a high-contrast thin frame.
    for y in range(3,61):
        for x in range(3,61):
            dx, dy = max(10-x, 0, x-53), max(10-y, 0, y-53)
            if dx*dx+dy*dy <= 49:
                pixels[y*SIZE+x] = 2 if x in (3,60) or y in (3,60) or dx*dx+dy*dy >= 30 else 1

    if name == "inventory":
        rect(18,22,46,49); rect(25,14,39,22); rect(23,34,41,44); line(18,28,46,28)
    elif name == "aim":
        circle(32,32,13)
        for a,b,c,d in ((32,12,32,24),(32,40,32,52),(12,32,24,32),(40,32,52,32)):
            line(a,b,c,d)
        dot(32,32)
    elif name == "nightvision":
        circle(22,34,9); circle(43,34,9); line(29,30,36,30); line(16,22,48,22)
    elif name == "gasmask":
        circle(32,30,16); circle(23,27,5); circle(41,27,5); rect(26,36,38,49)
        line(18,42,23,46); line(41,46,47,42)
    elif name == "laser":
        rect(15,33,34,40); line(26,30,26,43); line(34,35,50,19); circle(50,19,3)
    elif name == "silencer":
        rect(13,25,34,34); rect(34,27,51,32); line(20,34,17,47); line(17,47,25,47); line(25,47,28,34)
    elif name == "firemode":
        for x in (19,31,43):
            rect(x,27,x+5,47); line(x,27,x+2,17); line(x+2,17,x+5,27)
    elif name == "objective":
        rect(19,17,46,49); rect(26,14,38,21)
        for y in (29,36,43): line(25,y,40,y)
    elif name == "kick":
        line(26,15,22,36); line(22,36,14,43); line(14,43,15,49); line(15,49,48,49)
        line(48,49,49,41); line(49,41,34,35); line(34,35,37,15); line(26,15,37,15)
    elif name == "grenade":
        circle(31,38,13); rect(26,19,37,25); line(32,17,46,17); line(46,17,49,31)
        line(21,37,41,37); line(31,26,31,50)
    elif name == "bullettime":
        circle(31,32,18); line(31,18,31,33); line(31,33,42,39); line(49,17,53,17)
    elif name == "drop":
        rect(15,19,48,26); line(24,27,21,37); line(37,32,37,49); line(29,42,37,50); line(37,50,45,42)
    elif name == "signal":
        rect(22,27,41,49); line(28,27,28,13); circle(45,20,6); line(26,34,36,34); line(26,41,36,41)
    elif name == "skip":
        for x in (17,31): line(x,18,x+14,32); line(x+14,32,x,46)
        line(49,18,49,46)
    elif name == "performance":
        # Lightning bolt = optional reduced graphics load, not a promised FPS number.
        for a,b,c,d in ((35,13,20,35),(20,35,32,35),(32,35,28,51),(28,51,46,28),(46,28,34,28),(34,28,35,13)):
            line(a,b,c,d)
    else:
        raise ValueError(name)
    return pixels


def rgba(pixels):
    return bytes(c for p in pixels for c in PALETTE[p])


def vtf(pixels):
    header = bytearray(80)
    struct.pack_into('<4sIIIHHIHH', header, 0, b'VTF\0', 7, 2, 80, SIZE, SIZE, 0x230c, 1, 0)
    struct.pack_into('<3f', header, 32, .5, .5, .5)
    struct.pack_into('<fIBiBBH', header, 48, 1., 0, 1, -1, 0, 0, 1)
    return bytes(header) + rgba(pixels)


def runs(pixels):
    result = []
    for value in pixels:
        if result and result[-1] & 255 == value and result[-1] >> 8 < 255:
            result[-1] += 256
        else:
            result.append(256 | value)
    return result


def outputs():
    result = {}
    header = ['// Generated by scripts/build-underhell-touch-assets.py; do not edit.',
              '#ifndef UH_TOUCH_ASSETS_H', '#define UH_TOUCH_ASSETS_H',
              'static const unsigned char g_UHTouchPalette[][4] = {']
    header += ['    {' + ', '.join(map(str, p)) + '},' for p in PALETTE]
    header += ['};']
    for name, command, x, y in BUTTONS:
        pixels = icon(name)
        path = 'assets/underhell/materials/vgui/touch/underhell/' + name
        result[path + '.vtf'] = vtf(pixels)
        result[path + '.vmt'] = ('"UnlitGeneric"\n{\n    "$basetexture" "vgui/touch/underhell/' + name +
            '"\n    "$translucent" "1"\n    "$vertexcolor" "1"\n    "$vertexalpha" "1"\n    "$ignorez" "1"\n}\n').encode()
        encoded = runs(pixels)
        header.append('static const unsigned short g_UHTouch_' + name + '[] = {')
        for i in range(0, len(encoded), 16):
            header.append('    ' + ', '.join('0x%04x' % n for n in encoded[i:i+16]) + ',')
        header.append('};')
    header += ['struct UHTouchAsset { const char *name, *command; float x, y; const unsigned short *runs; int count; };',
               'static const UHTouchAsset g_UHTouchAssets[] = {']
    for name, command, x, y in BUTTONS:
        header.append('    {"%s", "%s", %.3ff, %.3ff, g_UHTouch_%s, sizeof(g_UHTouch_%s)/sizeof(unsigned short)},' %
                      (name, command, x, y, name, name))
    header += ['};', '#endif', '']
    result['game/client/underhell/uh_touch_assets.h'] = '\n'.join(header).encode()
    cfg = ['// Underhell extra controls for an already-installed port: exec underhell_touch.cfg',
           '// Re-running resets ONLY these 14 action buttons, never movement/attack controls.',
           'touch_enable 1', 'touch_draw 1']
    for name, command, x, y in BUTTONS:
        if name == 'performance': continue  # Native reversible command requires the updated client.
        cfg += ['touch_removebutton "uh_%s"' % name,
                'touch_addbutton "uh_%s" "vgui/touch/underhell/%s" "%s" %.3f %.3f %.3f %.3f 255 255 255 220 0 1' %
                (name, name, command, x, y, x+.06, y+.1)]
    result['assets/underhell/cfg/underhell_touch.cfg'] = ('\n'.join(cfg) + '\n').encode()
    result['assets/underhell/cfg/underhell_android_fast.cfg'] = ("""// Optional LOWER graphics quality, for the existing APK; NOT a renderer fix.
// These values can be saved by the engine. Back up cfg/config.cfg first.
// The updated native client instead offers uh_android_fast 1 / 0 (session restore).
r_flashlightdepthtexture 0
r_shadowrendertotexture 0
r_waterforceexpensive 0
r_waterforcereflectentities 0
mat_motion_blur_enabled 0
""").encode()
    result['assets/underhell/touch-buttons.json'] = (json.dumps([
        dict(name=n, command=c, x=x, y=y, width=.06) for n,c,x,y in BUTTONS], indent=2) + '\n').encode()
    return result


def pack_vpk(files):
    """VPK v1 with inline data (archive index 0x7fff), no external chunks."""
    grouped = {}
    for name, data in sorted(files.items()):
        path = Path(name)
        grouped.setdefault(path.suffix[1:], {}).setdefault(path.parent.as_posix(), []).append((path.stem, data))
    tree, payload = bytearray(), bytearray()
    for extension, directories in sorted(grouped.items()):
        tree += extension.encode() + b"\0"
        for directory, entries in sorted(directories.items()):
            tree += directory.encode() + b"\0"
            for name, data in entries:
                tree += name.encode() + b"\0"
                tree += struct.pack('<IHHIIH', zlib.crc32(data), 0, 0x7fff, len(payload), len(data), 0xffff)
                payload += data
            tree += b"\0"
        tree += b"\0"
    tree += b"\0"
    return struct.pack('<III', 0x55aa1234, 1, len(tree)) + tree + payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='fail if generated files differ')
    parser.add_argument('--launcher', type=Path, help='also package icon VTF/VMTs into android/assets/extras_dir.vpk')
    args = parser.parse_args()
    files = outputs()
    for name, data in files.items():
        path = ROOT / name
        if args.check:
            if not path.is_file() or path.read_bytes() != data:
                raise SystemExit('Outdated touch asset: ' + name)
        elif args.launcher is None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    if args.launcher is not None:
        prefix = 'assets/underhell/'
        content = {name[len(prefix):]: data for name, data in files.items()
                   if name.startswith(prefix + 'materials/')}
        target = args.launcher / 'android/assets/extras_dir.vpk'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(pack_vpk(content))
        print('Packed ' + str(target))
    print('15 Underhell touch icons: VTF 7.2 RGBA8888 + matching embedded atlas fallback')


if __name__ == '__main__':
    main()

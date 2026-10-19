"""Explicit native legacy profile; never a D7VK/Wine DLL substitution."""
from pathlib import Path
import re

MODULES = {
    'shaderapidx9_sarek_dx6': b'UNDERHELL_DX6_SHADERAPI_V1',
    'materialsystem_sarek_dx6': b'UNDERHELL_DX6_MATERIALSYSTEM_V1',
    'stdshader_dx6_sarek': b'UNDERHELL_DX6_SHADERS_V1',
}


def shader_sources(directory):
    root = Path(directory)
    # Source's original DX6 manifest is the inventory, not a hand-picked subset.
    # CRC/MD5/Windows DLL verification are not shader implementations.
    sources = [name for name in re.findall(r'\$File\s+"([^"\n]+\.cpp)"',
               (root / 'stdshader_dx6.vpc').read_text()) if '/' not in name and '\\' not in name]
    if len(sources) != 32 or len(set(sources)) != len(sources):
        raise ValueError('Unexpected DX6 shader inventory; review the VPC changes')
    for name in sources:
        if not (root / name).is_file():
            raise ValueError('Missing DX6 shader: ' + name)
    return sources

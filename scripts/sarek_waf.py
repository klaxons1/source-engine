"""The native D3D9 ABI is confined to shaderapi_sarek and bitmap_sarek."""
import os


def native_env(bld):
    env = bld.env.derive()
    # GNUSTL's <cstring> undefines CRT macros before using ::strncpy. Renaming
    # that C declaration in command-line defines makes native Windows headers fail.
    # Scope this exception to the native ABI targets, never the GLES environment.
    env.DEFINES = [d for d in env.DEFINES if d.split('=', 1)[0] not in
                   ('TOGLES', 'DX_TO_GL_ABSTRACTION', 'GL_GLEXT_PROTOTYPES', 'strncpy', '_snprintf')]
    env.append_unique('DEFINES', ['UNDERHELL_SAREK=1'])
    env.CXXFLAGS = [f for f in env.CXXFLAGS if not f.startswith('-std=')] + ['-std=c++14']
    return env


def native_includes(bld):
    return [os.path.join(bld.env.SAREK_SDK, 'include', p) for p in ('windows', 'directx')] + [
        bld.srcnode.find_node('materialsystem/shaderapidx9').abspath()]

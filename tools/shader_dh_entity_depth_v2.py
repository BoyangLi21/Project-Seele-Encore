"""Shader pack V2 for R64 (perf, approved by main 2026-11-16): a far-terrain depth test in the entity programs.

Entities are depth-tested against the vanilla depth buffer only. Distant Horizons draws far terrain into its own depth
buffer, so an entity beyond the real chunks (an EVA in a distant hangar, a launch-shaft door) was drawn over far
buildings and hills. The two entity programs now drop fragments that lie more than one block behind the far terrain
at the same pixel. Only these two files change; every other entry of the author's archive, licence files included,
stays byte for byte.

tools/package_r60.py applies it to the shipped pack under the pack's own file name, so oculus.properties and the
pack's .zip.txt settings stay matched. Standalone (prints both SHA-256 and the changed paths):

  python tools/shader_dh_entity_depth_v2.py <pack.zip> <out.zip>

From perf's r64-kit/r64/pack_v2_patch.py; the inserted code is unchanged.
"""
import hashlib
import sys
import zipfile

MARK = 'SEELE: far terrain has its own depth buffer'
SNIPPET = '''
    #ifdef DISTANT_HORIZONS
        // SEELE: far terrain has its own depth buffer, which this program's depth test never sees.
        // Drop what lies behind it, so entities beyond the real chunks stop showing through far buildings and hills.
        float seeleDhZ = texelFetch(dhDepthTex, ivec2(gl_FragCoord.xy), 0).r;
        if (seeleDhZ < 1.0) {
            vec2 seeleUv = gl_FragCoord.xy / vec2(viewWidth, viewHeight);
            vec4 seeleDhView = dhProjectionInverse * (vec4(seeleUv, seeleDhZ, 1.0) * 2.0 - 1.0);
            vec4 seeleView = gbufferProjectionInverse * (vec4(seeleUv, gl_FragCoord.z, 1.0) * 2.0 - 1.0);
            if (seeleView.z / seeleView.w < seeleDhView.z / seeleDhView.w - SEELE_DH_MARGIN) discard;
        }
    #endif
'''
# Margin in blocks: far terrain is coarser than the real terrain, so an entity right against it keeps one block.
TARGETS = {'shaders/program/gbuffers_entities.glsl': '1.0', 'shaders/program/gbuffers_spidereyes.glsl': '1.0'}


def patch_text(text, margin):
    """The program with the test at the top of its first main(), the fragment program in these files; unchanged if present."""
    if MARK in text:
        return text
    newline = '\r\n' if '\r\n' in text else '\n'
    marker = 'void main() {'
    at = text.index(marker) + len(marker)
    if 'FRAGMENT_SHADER' not in text[:at]:
        raise ValueError('the first main() is not in the fragment program')
    snippet = SNIPPET.replace('SEELE_DH_MARGIN', margin).rstrip('\n').replace('\n', newline)
    return text[:at] + snippet + text[at:]


def main():
    source, target = sys.argv[1:3]
    changed = []
    with zipfile.ZipFile(source) as zin, zipfile.ZipFile(target, 'x', zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename in TARGETS:
                text = data.decode('utf8')
                patched = patch_text(text, TARGETS[info.filename])
                if patched != text:
                    data = patched.encode('utf8'); changed.append(info.filename)
            zout.writestr(info, data)
        zout.comment = zin.comment
    digest = lambda path: hashlib.sha256(open(path, 'rb').read()).hexdigest()
    print('source', digest(source))
    print('output', digest(target))
    print('changed', changed or 'nothing (already patched)')


if __name__ == '__main__':
    main()

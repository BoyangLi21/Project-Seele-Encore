"""Keep the cavern grade; let the actual distant city remain visible from Hakone."""
from pathlib import Path
import argparse
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).parent))
from patch_zip_entries import replace_entries

parser = argparse.ArgumentParser()
parser.add_argument("shader", type=Path)
args = parser.parse_args()
name = "shaders/lib/atmospherics/fog/mainFog.glsl"
with zipfile.ZipFile(args.shader) as archive:
    source = archive.read(name).decode("utf-8")
marker = "// SEELE Hakone: retain atmospheric depth beyond the real city target."
if marker not in source:
    anchor = "        if (fog > 0.0) {"
    assert anchor in source
    source = source.replace(anchor, """        #if defined SEELE_GEOFRONT && defined DISTANT_HORIZONS
            // SEELE Hakone: retain atmospheric depth beyond the real city target.
            fog *= mix(0.35, 1.0, SeeleCavernWeight());
        #endif

""" + anchor, 1)
    anchor = "float fog = pow2(1.0 - exp(-max0(lViewPos - 40.0) * (0.7 + 0.7 * rainFactor) / ATM_FOG_DISTANCE));"
    assert anchor in source
    source = source.replace(anchor, """float atmosphereRange = float(ATM_FOG_DISTANCE);
            #ifdef SEELE_GEOFRONT
                atmosphereRange = mix(max(atmosphereRange, 1100.0), atmosphereRange, SeeleCavernWeight());
            #endif
            float fog = pow2(1.0 - exp(-max0(lViewPos - 40.0) * (0.7 + 0.7 * rainFactor) / atmosphereRange));""")
    replace_entries(args.shader, {name: source.encode("utf-8")})
print("Hakone exterior atmosphere updated; cavern lighting retained")

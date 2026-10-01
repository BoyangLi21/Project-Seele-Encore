"""Create a local shader variant with the current SEELE LCL material."""
from pathlib import Path
import zipfile,json,hashlib
from lcl_shader_material_r44 import material_patch
ROOT=Path(__file__).resolve().parents[1]
def build(source,out):
    source=Path(source);out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    patch=material_patch()
    with zipfile.ZipFile(source) as original,zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as result:
        for item in original.infolist():
            data=original.read(item.filename)
            if item.filename=='shaders/block.properties':
                text=data.decode();assert 'block.32001=' not in text
                text+='\n# Project SEELE amber LCL (separate from biome-coloured water)\nblock.32001=projectseele:lcl\n';data=text.encode()
            if item.filename=='shaders/program/gbuffers_water.glsl':
                text=data.decode();assert text.count('    // Blending')==1;text=text.replace('    // Blending',patch+'    // Blending');data=text.encode()
            result.writestr(item,data)
        result.writestr('SEELE_LCL_COMPAT.txt','Local compatibility patch for Project SEELE: custom LCL material ID and alpha. Original shader authors, credits and licenses remain included. No other shader behavior is changed.\n')
    out.with_suffix('.json').write_text(json.dumps({'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'output_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'material':'r44_dense_orange_red','native_evidence':None},indent=2));return out
def main():
    print(build(ROOT/'run/shaderpacks/ComplementaryUnbound_r5.3.zip',ROOT/'artifacts/combat_rebuild_r35/facility/ComplementaryUnbound_r5.3_SEELE_LCL.zip'))
if __name__=='__main__':main()

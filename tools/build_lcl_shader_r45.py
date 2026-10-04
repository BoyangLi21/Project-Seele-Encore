"""Use pinned water shading with LCL-specific colour and absorption inputs."""
from pathlib import Path
import argparse, hashlib, json, shutil, zipfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'artifacts/rebuild_r44/atmosphere/geofront_shader_v3/ComplementaryUnbound_r5.3_SEELE_R44_GeoFrontCandidate_v3.zip'
TARGET=ROOT/'artifacts/rebuild_r45/lcl/ComplementaryUnbound_r5.3_SEELE_R45.zip'

def build(source=SOURCE,target=TARGET,density=4.0):
    source,target=Path(source),Path(target)
    assert 1.0<=density<=8.0
    assert source.resolve()!=target.resolve() and not target.exists()
    target.parent.mkdir(parents=True,exist_ok=True);changes=[]
    main='shaders/program/gbuffers_water.glsl'
    material='shaders/lib/materials/specificMaterials/translucents/water.glsl'
    with zipfile.ZipFile(source) as src,zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as dst:
        for info in src.infolist():
            data=src.read(info.filename)
            if info.filename==main:
                s=data.decode('utf8');assert s.count('if (mat == 32000) { // Water')==1
                s=s.replace('if (mat == 32000) { // Water','if (mat == 32000 || mat == 32001) { // Water and LCL')
                start=s.index('    // Project SEELE LCL R44:');end=s.index('    // Blending',start)
                old=s[start:end];assert old.count('if (mat == 32001)')==1
                s=s[:start]+s[end:];data=s.encode('utf8');changes.append(main)
            elif info.filename==material:
                s=data.decode('utf8').replace('\r\n','\n')
                # Tint must be assigned before color.rgb consumes it. An
                # earlier generated package assigned it after this point.
                needle='    #if WATER_STYLE < 3\n        vec3 colorPM'
                assert s.count(needle)==1
                colour='''    // Project SEELE R45: set material input before surface colour.\n    if (mat == 32001) {\n        glColorM = sqrt1(glColor.rgb) * vec3(1.0, 0.85, 0.8);\n        #ifdef GBUFFERS_WATER\n            translucentMultCalculated = true;\n            translucentMult.rgb = normalize(sqrt2(glColor.rgb));\n            translucentMult.g *= 0.88;\n        #endif\n    }\n\n'''
                s=s.replace(needle,colour+needle,1)
                fog='            float waterFog = max0(1.0 - exp(lViewPosDifM * 0.075));'
                assert s.count(fog)==1
                s=s.replace(fog,'            // Same water thickness law; only the facility liquid is denser.\n'
                    +f'            if (mat == 32001) lViewPosDifM *= {density:.6f};\n'+fog,1)
                assert s.index('if (mat == 32001)')<s.index('color.rgb = colorPM * glColorM;')
                data=s.encode('utf8');changes.append(material)
            dst.writestr(info,data)
        dst.writestr('SEELE_LCL_R45.txt',f'LCL uses the original water material with orange-red Forge tint and {density:g}x optical absorption. Ordinary water, reflection, waves and refraction functions remain unchanged. Original shader licenses remain intact.\n')
    with zipfile.ZipFile(source) as src,zipfile.ZipFile(target) as dst:
        assert dst.testzip() is None
        assert all(src.read(n)==dst.read(n) for n in src.namelist() if n not in changes)
    settings=source.with_name(source.name+'.txt')
    if settings.exists():shutil.copy2(settings,target.with_name(target.name+'.txt'))
    report=dict(source=str(source),target=str(target),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        target_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),changed=changes,
        shader_algorithm='Pinned water functions reused; LCL tint before surface calculation and material-specific optical absorption',
        lcl_absorption_multiplier=density,normal_water_changed=False,native_shader_and_visual='PENDING')
    target.with_suffix('.json').write_text(json.dumps(report,indent=2),'utf8');print('R45 native-water LCL shader built')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=SOURCE);p.add_argument('--target',type=Path,default=TARGET)
    p.add_argument('--lcl-density',type=float,default=4.0)
    a=p.parse_args();build(a.source,a.target,a.lcl_density)

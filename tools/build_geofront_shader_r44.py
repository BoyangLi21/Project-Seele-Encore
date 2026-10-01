"""Dimension-scoped cavern atmosphere candidate atop the reviewed R44 LCL pack.

The source pack remains intact. This addresses shader-owned border fog and
celestial effects; it does not fabricate a roof or replace real chunk geometry.
"""
from pathlib import Path
import hashlib, json, shutil, zipfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'artifacts/rebuild_r44/lcl/ComplementaryUnbound_r5.3_SEELE_R44.zip'
OUT=ROOT/'artifacts/rebuild_r44/atmosphere/geofront_shader_v1'
TARGET=OUT/'ComplementaryUnbound_r5.3_SEELE_R44_GeoFrontCandidate.zip'
HELPER='''#ifndef SEELE_CAVERN_HELPER
#define SEELE_CAVERN_HELPER
float SeeleCavernWeight() {
    #ifdef SEELE_GEOFRONT
        return 1.0 - smoothstep(-192.0, -128.0, cameraPosition.y);
    #else
        return 0.0;
    #endif
}
vec3 SeeleCavernHaze(float vertical) {
    // Forge's dimension fog event supplies the reviewed cavern tint.
    // Keep the supplied tint. Additional gamma/darkening made a black
    // background around the finite real roof mesh in the first native pass.
    vec3 base = max(fogColor, vec3(0.015));
    return base * mix(1.05, 0.95, smoothstep(0.05, 1.0, vertical));
}
float SeeleCavernFogDistance(vec3 position) {
    // Horizontal range stays bounded. A real high roof is not washed out
    // merely because its vertical separation exceeds the horizontal radius.
    return max(length(position.xz), abs(position.y) * mix(1.0, 0.28, SeeleCavernWeight()));
}
#endif
'''


def build():
    assert not TARGET.exists(),'Keep earlier candidate and evidence'
    OUT.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(SOURCE) as source:
        original={n:source.read(n) for n in source.namelist()};result=dict(original);changes=[]
        def edit(name,transform):
            before=original[name].decode().replace('\r','');after=transform(before)
            assert after!=before,name
            result[name]=after.encode();changes.append(name)
        def once(text,old,new):
            assert text.count(old)==1,(old,text.count(old))
            return text.replace(old,new)
        def sky(s):
            s=once(s,'    #define INCLUDE_SKY','    #define INCLUDE_SKY\n    #include "/lib/seele/cavern.glsl"')
            assert s.count('        return finalSky;')==2
            return s.replace('        return finalSky;','        return mix(finalSky, SeeleCavernHaze(VdotU), SeeleCavernWeight());')
        edit('shaders/lib/atmospherics/sky.glsl',sky)
        def basic(s):
            s=once(s,'color.rgb += GetStars(starCoord, VdotU, VdotS);','color.rgb += GetStars(starCoord, VdotU, VdotS) * (1.0 - SeeleCavernWeight());')
            return once(s,'float sunMoonMixer = sqrt1(sunSizeFactor2 * (absVdotS - sunSizeFactor1));','float sunMoonMixer = sqrt1(sunSizeFactor2 * (absVdotS - sunSizeFactor1)) * (1.0 - SeeleCavernWeight());')
        edit('shaders/program/gbuffers_skybasic.glsl',basic)
        def textured(s):
            s=once(s,'#ifdef FRAGMENT_SHADER','#ifdef FRAGMENT_SHADER\n#include "/lib/seele/cavern.glsl"')
            return once(s,'    /* DRAWBUFFERS:0 */','    #ifdef OVERWORLD\n        color.a *= 1.0 - SeeleCavernWeight();\n    #endif\n    /* DRAWBUFFERS:0 */')
        edit('shaders/program/gbuffers_skytextured.glsl',textured)
        def deferred(s):
            s=once(s,'#ifdef FRAGMENT_SHADER','#ifdef FRAGMENT_SHADER\n#include "/lib/seele/cavern.glsl"')
            token='                color.rgb += nightNebula;\n            #endif'
            return once(s,token,token+'\n            color.rgb = mix(color.rgb, SeeleCavernHaze(VdotU), SeeleCavernWeight());')
        edit('shaders/program/deferred1.glsl',deferred)
        edit('shaders/lib/atmospherics/clouds/mainClouds.glsl',lambda s:once(s,'    return clouds;','    clouds.a *= 1.0 - SeeleCavernWeight();\n    return clouds;'))
        def fog(s):
            s='#include "/lib/seele/cavern.glsl"\n'+s
            s=once(s,'max(length(playerPos.xz), abs(playerPos.y)), VdotU','SeeleCavernFogDistance(playerPos), VdotU')
            marker='        if (fog > 0.0) {\n            fog = clamp(fog, 0.0, 1.0);'
            assert s.index(marker)>s.index('void DoBorderFog') and s.index(marker)<s.index('void DoCaveFog')
            return s.replace(marker,'        #ifdef SEELE_GEOFRONT\n            float cavernFog = 1.0 - exp(-2.0 * pow(max(lPos / renderDistance, 0.0), 2.2));\n            fog = mix(fog, cavernFog, SeeleCavernWeight());\n        #endif\n\n'+marker,1)
        edit('shaders/lib/atmospherics/fog/mainFog.glsl',fog)
        result['shaders/lib/seele/cavern.glsl']=HELPER.encode()
        mapping=original['shaders/dimension.properties'].decode().replace('\r','')
        assert 'dimension.world0=*' in mapping and 'projectseele:geofront' not in mapping
        result['shaders/dimension.properties']=(mapping+'\n# Exact project dimension; other dimensions retain their original programs.\ndimension.seele_geofront=projectseele:geofront\n').encode();changes.append('shaders/dimension.properties')
        # Program gates are dimension-folder specific too. Without these,
        # the copied compute pass runs while its optional voxel images are
        # disabled by the original preset (undefined voxel_sampler).
        properties=original['shaders/shaders.properties'].decode().replace('\r','')
        lines=[];aliased=0
        for line in properties.splitlines():
            lines.append(line)
            if 'program.world0/' in line:
                lines.append(line.replace('program.world0/','program.seele_geofront/'));aliased+=1
        assert aliased>0
        result['shaders/shaders.properties']=('\n'.join(lines)+'\n').encode();changes.append('shaders/shaders.properties')
        wrappers=[]
        for name,data in original.items():
            if not name.startswith('shaders/world0/') or not name.endswith(('.vsh','.fsh','.gsh','.csh')):continue
            s=data.decode().replace('\r','');assert s.count('#define OVERWORLD')==1,name
            target=name.replace('shaders/world0/','shaders/seele_geofront/');result[target]=s.replace('#define OVERWORLD','#define OVERWORLD\n#define SEELE_GEOFRONT').encode();wrappers.append(target)
        assert wrappers
        result['SEELE_GEOFRONT_R44.txt']=b'Private native-review candidate. Exact GeoFront dimension mapping; underground haze and sky/reflection/cloud handling only. Source credits, licenses, dense LCL and command-room lighting switches are retained. This is not proof that real roof chunks render.\n'
        with zipfile.ZipFile(TARGET,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
            for name,data in result.items():z.writestr(name,data)
        with zipfile.ZipFile(TARGET)as z:
            assert z.testzip()is None
            for name,data in original.items():
                if name not in changes:assert z.read(name)==data,name
    settings=SOURCE.with_name(SOURCE.name+'.txt')
    if settings.exists():shutil.copy2(settings,TARGET.with_name(TARGET.name+'.txt'))
    manifest=dict(source=str(SOURCE),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),target=str(TARGET),target_sha256=hashlib.sha256(TARGET.read_bytes()).hexdigest(),changed_existing_files=changes,new_dimension_wrappers=len(wrappers),old_world0_wrappers_unchanged=True,lcl_and_lighting_materials_unchanged=True,native_compilation=False,visual_pass=False,
        reference='https://shaders.properties/current/reference/miscellaneous/dimension_properties/',dimension_program_gates_aliased=aliased,root_cause_candidate='Shader DoBorderFog uses max(horizontal,vertical) against renderDistance and shader-owned GetSky rather than the Forge fog tint. A high roof can be fogged into daytime sky even with a larger vanilla vertical fog distance.',requires=['Actual Oculus selection of exact new dimension folder','Before/after same-cavern roof required-section image, night/day, sky/reflection/opaque LCL','Surface, ordinary overworld, Nether, End remain original shader behavior'])
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf8');print(json.dumps(manifest,indent=2))


if __name__=='__main__':build()

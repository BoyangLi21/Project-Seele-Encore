"""Read-only source and compiled producer compatibility for the exact migration."""
from pathlib import Path
import hashlib,json,re,subprocess

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'src/main/java/com/projectseele/world/EvaHangarBuilder.java'
CLASS=ROOT/'build/classes/java/main/com/projectseele/world/EvaHangarBuilder.class'
JAVAP=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin/javap.exe')
OUT=ROOT/'artifacts/rebuild_r44/facility_transit_r44/tv_front_crossway_relocation_v2'


def main():
    s=SOURCE.read_text(encoding='utf8');checks={
        'front_starts_at_minus27':bool(re.search(r'FRONT_CROSS_Z_FROM_BED\s*=\s*-27\s*;',s)),
        'four_rows_last_is_guard_bearing':bool(re.search(r'FRONT_CROSS_DEPTH\s*=\s*4\s*;',s)),
        'side_guard_starts_on_inner_last_row':'z >= FRONT_CROSS_Z_FROM_BED + FRONT_CROSS_DEPTH - 1' in s,
        'three_rows_named_headroom':'z < FRONT_CROSS_Z_FROM_BED + FRONT_CROSS_DEPTH - 1' in s,
        'full_MTR_states_preserved':'.getNamespace().equals("mtr")' in s,
        'complete_BE_preserved':'level.getBlockEntity(position) != null' in s,
        'whole_existing_east_arrival_apertures_preserved':'bed.equals(new BlockPos(72, -443, -240))' in s and 'position.getZ() >= -264' in s and 'position.getX() >= 85' in s,
        'connector_normalized_toward_new_front':'Math.min(galleryStartZ, catwalkStartZ)' in s,
        'low_inner_jamb_not_in_public_first_row':'if (y > 2)' in s,
        'source_corners_have_two_sides':'guard = guard.setValue(x < 0 ? FacilityEdgeRailR41.EAST : FacilityEdgeRailR41.WEST, true)' in s}
    assert all(checks.values()),checks
    compiled={}
    if CLASS.exists():
        result=subprocess.run([str(JAVAP),'-p','-constants',str(CLASS)],capture_output=True,text=True,check=True)
        text=result.stdout
        compiled={'class_sha256':hashlib.sha256(CLASS.read_bytes()).hexdigest(),
            'class_not_older_than_source':CLASS.stat().st_mtime>=SOURCE.stat().st_mtime,
            'constant_minus27':'FRONT_CROSS_Z_FROM_BED = -27' in text,
            'constant_four':'FRONT_CROSS_DEPTH = 4' in text,
            'helper_methods_present':all(name in text for name in ['preservedCrewInfrastructureR44','setCrewBearingR44','setCrewRailR44','clearOwnedCrewRailR44'])}
    report={'source':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'source_checks':checks,'compiled_checks':compiled,'source_compatible':True,
        'compiled_compatible':bool(compiled) and all(v for k,v in compiled.items() if k!='class_sha256'),
        'exact_patch_application_is_separate':True,'current_world_writer_is_root_only':True,
        'clean_future_template_native_test':False,'limit':'Source and actual compiled constants/method presence, not a live constructor pass or a world write. Post-apply full-width paths/equipment/cold reload remain required.'}
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'producer_compatibility.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report))


if __name__=='__main__':main()

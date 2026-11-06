"""Prepare an explicit final-candidate native probe; never launch or open a save."""
from pathlib import Path
import argparse,hashlib,json,zipfile
from prepare_r52_terrain_observer_plan import CANDIDATE,OLD_C8
PINS=['com.projectseele.ProjectSeele','com.projectseele.world.DeadSeaChamberR45',
      'com.projectseele.world.DeadSeaChamberSavedDataR45','com.projectseele.world.NervAccessReaderR44',
      'com.projectseele.world.NervAccessReaderEntityR44','com.projectseele.item.NervAccessCardR44']
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--jar',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    jar=a.jar.resolve();output=a.output.resolve();digest=hashlib.sha256(jar.read_bytes()).hexdigest()
    if digest==OLD_C8:raise ValueError('Highest-chamber relocated QA requires C9 or later; C8 refused')
    if not output.is_relative_to(CANDIDATE) or output.exists():raise ValueError('Fresh candidate-only plan required')
    with zipfile.ZipFile(jar)as z:pins={name:hashlib.sha256(z.read(name.replace('.','/')+'.class')).hexdigest()for name in PINS}
    plan=dict(schema='projectseele.r52.highest-chamber-native-probe.v1',candidate_jar=str(jar),candidate_jar_sha256=digest,
              loaded_class_sha256=pins,world='SEELE_R52_REVIEW',dimension='projectseele:geofront',deadline_seconds=90,
              outside_reader=[36,-421,339],outside_stand=[36.5,-422,337.5],inside_reader=[35,-421,341],inside_stand=[35.5,-422,343.5],
              cases=['ordinary_card1_rejected','outside_card3_full10_open_and_exact200_tick_fullNBT_restore','inside_card3_full10_open_and_exact200_tick_fullNBT_restore'],
              interaction_path='Actual player; vanilla gameMode.useItemOn with real shape ray and permissions; no direct grant or door/image writes',
              temporary_player_changes='Inventory presentation card, survival mode and Root-declared stand positions; complete inventory/mode/original position restored',
              source_world_opened=False,native_executed=False,visual_acceptance=False)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(plan,indent=2)+'\n','utf8');print(output)
if __name__=='__main__':main()

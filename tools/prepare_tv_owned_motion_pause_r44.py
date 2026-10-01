"""Freeze read-only motion-clock review and unapplied source-hook proposal."""
from pathlib import Path
import json,hashlib,difflib

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r44/hangar_machinery/personnel_owned_motion_pause_v1'
if OUT.exists():raise ValueError('Immutable proposal exists')
OUT.mkdir(parents=True);rows=[]
paths=['src/main/java/com/projectseele/entity/EvaUnit01Entity.java',
       'src/main/java/com/projectseele/entity/EntryPlugCarrierEntity.java',
       'src/main/java/com/projectseele/world/EvaLogisticsDirector.java',
       'src/main/java/com/projectseele/world/EntryPlugDirector.java',
       'src/main/java/com/projectseele/world/TvPersonnelPlatformInterlockR44.java']
for name in paths:
    data=(ROOT/name).read_bytes();dest=OUT/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    rows.append({'path':name,'sha256':hashlib.sha256(data).hexdigest()})
patch=[]
def propose(name,changes):
    original=(ROOT/name).read_text('utf8');current=original
    for before,after in changes:
        if current.count(before)!=1:raise ValueError(('Hook source not unique',name,before[:65],current.count(before)))
        current=current.replace(before,after)
    target=OUT/'unapplied'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(current,'utf8')
    patch.extend(difflib.unified_diff(original.splitlines(True),current.splitlines(True),fromfile='a/'+name,tofile='b/'+name))

# Exact hook points, deliberately incomplete pending root's data-accessor and
# save/reload implementation. These source copies are not compiled or applied.
propose(paths[0],[
    ('        this.oldCarrierRiseR26=this.entityData.get(DATA_CARRIER_RISE_R26);',
     '        this.updateTvPersonnelCarrierHoldR44(); // proposed owned clock authority, not whole aiStep cancellation\n        this.oldCarrierRiseR26=this.entityData.get(DATA_CARRIER_RISE_R26);'),
    ('    public Vec3 sampleCarrierMotion(float partialTick)\n    {',
     '    public Vec3 sampleCarrierMotion(float partialTick)\n    {\n        if (this.hasTvPersonnelCarrierHoldR44()) return this.tvPersonnelFrozenCarrierPositionR44();'),
    ('    private void tickLaunchSequence()\n    {',
     '    private void tickLaunchSequence()\n    {\n        if (this.holdOwnedNervLaunchClockR44()) return; // canonical NERV / assigned shaft only'),
    ('            this.entityData.set(DATA_ACTIVATION_TICKS, this.getActivationTicks() - 1);',
     '            if (!this.holdOwnedNervLaunchClockR44())\n                this.entityData.set(DATA_ACTIVATION_TICKS, this.getActivationTicks() - 1);')])
propose(paths[1],[
    ('                this.ejectionTicks++;\n                EntryPlugDirector.tickEjection(this, this.ejectionTicks);',
     '                if (!com.projectseele.world.TvPersonnelPlatformInterlockR44.holdCanonicalWetEjectionR44(this))\n                {\n                    this.ejectionTicks++;\n                    EntryPlugDirector.tickEjection(this, this.ejectionTicks);\n                }')])
(OUT/'unapplied_hooks.diff').write_text(''.join(patch),'utf8')
(OUT/'manifest.json').write_text(json.dumps({'source_snapshots':rows,'status':'READ_ONLY_PLAN_UNAPPLIED_HOOK_SKETCH_NOT_COMPILABLE',
    'entity_primary_sources_modified':False,'world_write':False,'native_passed':False,
    'required_implementation':['owned canonical predicates and motion kinds','synced held/frozen xyz and carrier elapsed/start accounting',
                               'NBT pause version/frame/elapsed persistence and startup fail-closed validation',
                               'client partial sampling freezing; clear/reset lifecycle and actually loaded ownership',
                               'native50tick intrusion/no drift/resume/cold controls and UN/field negative controls']},indent=2),'utf8')
print(json.dumps({'proposal':str(OUT),'source_modified':False}))

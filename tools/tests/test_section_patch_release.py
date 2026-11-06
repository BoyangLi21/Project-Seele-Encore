"""Offline publication rejection and real deep MCA/recipe round trips."""
import argparse
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest

import nbtlib
import numpy as np
from apply_s20_approved_semantic_repairs import chunk_blob, parse_state
from install_hakone_array_patch import Palette, compose, prepare_region
from map_pipeline.delivery_check import read, write
from map_pipeline.install.invariants import require_nbt_equal
from plan_hakone_relocations import unpack
from prepare_station_section_recipes import DATA, REGIONS, validate_delta, actual_cells, prepare
from release_section_access_patch import (freeze_files, validate_replay, replay_scope, validate_offline,
    installed_dependencies, declaration_transition, validate_retained_failure)
from transplant_s22_authority import build_region, read_region, parse_chunk


class SectionPatchTest(unittest.TestCase):
    def fixture(self, root):
        source, candidate, world = (root/name for name in ('source','candidate','world'))
        (source/'sections').mkdir(parents=True); (candidate/'delta').mkdir(parents=True)
        write(source/'capture.json',dict(diagnostics=[]))
        positions = [(-17,-560,-1),(-18,-437,-2),(-17,80,-1)]
        ys = sorted({p[1]//16 for p in positions})
        np.savez(source/'sections/r.-1.-1.npz',coordinates=[[-2,y,-1] for y in ys],
                 blocks=np.zeros((len(ys),16,16,16),np.uint16),palette=['minecraft:air'])
        rows = [dict(pos=list(p),before='minecraft:air',after='minecraft:glass') for p in positions]
        write(candidate/'exact-edits.json',rows)
        delta = candidate/'delta/r.-1.-1.npz'
        np.savez(delta,coordinates=[[-2,-1]],ranges=[0,len(rows)],
                 indices=[(y+672)*256+(z%16)*16+x%16 for x,y,z in positions],
                 before=np.zeros(len(rows),np.int32),after=np.ones(len(rows),np.int32),
                 palette=['minecraft:air','minecraft:glass'],y_origin=-672,height=992)
        write(candidate/'manifest.json',dict(source=str(source),world=str(world),cells=len(rows),device_changes=0,
              vertical_extent=[-672,319],regions=[dict(path='delta/r.-1.-1.npz',cells=len(rows),y_origin=-672,height=992)]))
        tag = nbtlib.Compound({'id':nbtlib.String('minecraft:chest'),'x':nbtlib.Int(-31),
                              'y':nbtlib.Int(70),'z':nbtlib.Int(-15),'CustomName':nbtlib.String('preserve me'),
                              'Items':nbtlib.List[nbtlib.Compound]()})
        sections = [nbtlib.Compound({'Y':nbtlib.Byte(y),
            'block_states':nbtlib.Compound({'palette':nbtlib.List[nbtlib.Compound]([parse_state('minecraft:air')])}),
            'biomes':nbtlib.Compound({'palette':nbtlib.List[nbtlib.String]([nbtlib.String('minecraft:plains')])})}) for y in ys]
        chunk = nbtlib.File({'DataVersion':nbtlib.Int(3465),'xPos':nbtlib.Int(-2),'zPos':nbtlib.Int(-1),
                            'Status':nbtlib.String('minecraft:full'),'InhabitedTime':nbtlib.Long(12345),
                            'sections':nbtlib.List[nbtlib.Compound](sections),
                            'block_entities':nbtlib.List[nbtlib.Compound]([tag]),
                            'UnrelatedProgress':nbtlib.Compound({'Value':nbtlib.Long(99)})})
        raw = [None]*1024; raw[31*32+30] = chunk_blob(chunk)
        (world/REGIONS).mkdir(parents=True)
        (world/REGIONS/'r.-1.-1.mca').write_bytes(build_region(bytes(4096),raw))
        recipe = nbtlib.File({'Version':nbtlib.Int(1),'WorldUUID':nbtlib.IntArray([1,2,3,4]),
            'Palette':nbtlib.List[nbtlib.Compound]([parse_state('minecraft:stone')]),
            'Spans':nbtlib.List[nbtlib.IntArray]([nbtlib.IntArray([-32,-16,60,60,0])]),
            'BlockEntities':nbtlib.List[nbtlib.Compound]([tag]),'RetainedExtra':nbtlib.String('original')})
        (world/DATA).mkdir(parents=True); recipe.save(world/DATA/'-2_-1.dat',gzipped=True)
        return candidate, source, world, delta, recipe

    def test_deep_mca_prepare_and_exact_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); candidate,source,world,delta,recipe=self.fixture(root)
            checked=validate_delta(candidate); before_devices,count=actual_cells(world,checked)
            self.assertEqual(3,count)
            palette=Palette(); chunks=compose([delta],palette)
            stage=root/'stage'; destination=stage/REGIONS/'r.-1.-1.mca'
            prepare_region(world,(-1,-1),chunks,{},palette,destination)
            after_devices,count=actual_cells(stage,checked,after=True)
            require_nbt_equal(before_devices,after_devices)
            self.assertEqual(3,count)
            with self.assertRaisesRegex(ValueError,'precondition/readback'):
                actual_cells(stage,checked)
            _,raw=read_region(destination); parsed=parse_chunk(raw[31*32+30])
            self.assertEqual(12345,int(parsed['InhabitedTime']))
            self.assertEqual(99,int(parsed['UnrelatedProgress']['Value']))
            # prepare_region left the original scratch world unchanged.
            actual_cells(world,checked)

    def test_absolute_recipes_preserve_uuid_spans_and_devices(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate,source,world,delta,recipe=self.fixture(Path(tmp))
            proof=prepare(world,candidate)
            self.assertEqual(3,proof['actual_old_cells_verified'])
            self.assertEqual(1,proof['actual_touched_chunk_devices'])
            after=nbtlib.load(candidate/'after'/DATA/'-2_-1.dat')
            for key in ('WorldUUID','BlockEntities','RetainedExtra'):
                require_nbt_equal(recipe[key],after[key])
            require_nbt_equal(recipe['Spans'][0],after['Spans'][0])
            cells={}
            for x,z,lo,hi,state in after['Spans']:
                for y in range(int(lo),int(hi)+1):cells[int(x),y,int(z)]=after['Palette'][int(state)]
            for row in read(candidate/'exact-edits.json'):
                self.assertEqual(parse_state(row['after']),cells[tuple(row['pos'])])
            expected=nbtlib.load(candidate/'recipe-replay-expected/r.-1.-1.dat')
            self.assertEqual(1,int(expected['Version']))
            actual={tuple(unpack(int(c['Pos']))) for ch in expected['Chunks'] for c in ch['Cells']}
            self.assertEqual({tuple(r['pos']) for r in read(candidate/'exact-edits.json')},actual)

    def test_changed_scope_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate,*_=self.fixture(Path(tmp)); rows=read(candidate/'exact-edits.json')
            rows[0]['after']='minecraft:stone';write(candidate/'exact-edits.json',rows)
            with self.assertRaisesRegex(ValueError,'declared cells'):validate_delta(candidate)

    def test_unknown_source_is_not_air(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate,source,*_=self.fixture(Path(tmp))
            path=source/'sections/r.-1.-1.npz'
            with np.load(path) as f:data={k:f[k] for k in f.files}
            data['coordinates']=data['coordinates'][1:];data['blocks']=data['blocks'][1:];np.savez(path,**data)
            with self.assertRaisesRegex(ValueError,'Unknown source'):validate_delta(candidate)
            with self.assertRaisesRegex(ValueError,'Unknown source'):
                validate_delta(candidate,source_overlay={(-17,-560,-1):'minecraft:air'})

    def test_dependency_state_cannot_hide_delta_precondition(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate,*_=self.fixture(Path(tmp))
            with self.assertRaisesRegex(ValueError,'source precondition'):
                validate_delta(candidate,source_overlay={(-17,-560,-1):'minecraft:stone'})

    def test_unknown_scope_kind_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);candidate,*_=self.fixture(root)
            write(candidate/'functional.json',{})
            config=root/'config.json'
            write(config,dict(schema='section-access-patch-release-v1',id='test',maximum_step=.5,
                changes_file='exact-edits.json',functional_report='functional.json',scope_kind='floor_as_guard'))
            with self.assertRaisesRegex(ValueError,'scope_kind'):
                validate_offline(argparse.Namespace(candidate=candidate,config=config))

    def test_uninstalled_or_unreplayed_dependency_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);candidate,*_=self.fixture(root);checked=validate_delta(candidate)
            item=dict(candidate=str(candidate),installation=str(root/'installation.json'))
            with self.assertRaisesRegex(ValueError,'not installed'):installed_dependencies([(item,checked)])
            write(root/'installation.json',dict(status='installed',changed_section_readback=True,cells=3,
                candidates=[str(candidate)],world=checked['manifest']['world']))
            write(candidate/'delivery-check.json',dict(passed=True,production_replay_passed=False,changed_cells=3))
            write(candidate/'section-release-check.json',dict(installed_delivery_check_passed=True,production_recipe_replay_passed=True))
            with self.assertRaisesRegex(ValueError,'replay/delivery'):installed_dependencies([(item,checked)])

    def declaration_fixture(self):
        cell=dict(floor=[0,-450,0],role='public',source={'generator':'fixture'},allowed_occupants=[])
        before=dict(stations=[dict(site='a',cells=[cell],native_platforms=[dict(extent=[-32,32])])])
        after=copy.deepcopy(before);changed=after['stations'][0]['cells'][0]
        changed.update(role='guarded_nonboarding_trackside_margin',public_walkable=False,
                       ownership_change={'component':['a','line',1,1]})
        exact=[dict(site='a',floor=cell['floor'],before=cell,after=changed)]
        expected=dict(complete_floor_denominator=1,finite_margin_cells=1,new_barrier_occupied_cells=0,declaration_changed_cells=1)
        return before,after,exact,expected

    def test_complete_declaration_denominator_and_exact_delta(self):
        before,after,exact,expected=self.declaration_fixture()
        actual,margins=declaration_transition(before,after,exact,{},expected)
        self.assertEqual(expected,actual);self.assertEqual({('a',(0,-450,0))},margins)
        with self.assertRaisesRegex(ValueError,'delta differs'):
            declaration_transition(before,after,[],{},expected)
        after['stations'][0]['cells']=[]
        with self.assertRaisesRegex(ValueError,'denominator'):
            declaration_transition(before,after,exact,{},expected)

    def test_original_boarding_metadata_cannot_be_reclassified(self):
        before,after,exact,expected=self.declaration_fixture()
        after['stations'][0]['native_platforms'][0]['extent']=[-31,31]
        with self.assertRaisesRegex(ValueError,'boarding'):
            declaration_transition(before,after,exact,{},expected)

    def test_structural_underlay_cannot_bypass_margin_proof(self):
        before,after,exact,expected=self.declaration_fixture()
        after['stations'][0]['cells'][0]['role']='structural_underlay'
        with self.assertRaisesRegex(ValueError,'occupant'):
            declaration_transition(before,after,exact,{},expected)

    def test_legacy_failure_exception_is_exact_and_disjoint(self):
        hit=dict(kind='body_obstruction',pos=[0,0,0],state='fixture:board')
        result=dict(kind='strict_step_or_body_failure',unknown=[])
        row=dict(key='a/original/0',path=[[0,1,0],[2,1,0]],before=dict(forward=result,reverse=result),after=dict(forward=result,reverse=result))
        exception=dict(path=row['path'],results=row['before'],obstruction=hit,witness_feet=[1,1,0])
        class Walker:
            minimum=[0,0,0];maximum=[1,1,1]
            def __init__(self):self.reader=self
            def body(self,*p):return hit
            def state(self,*p):return 'fixture:board'
        w=Walker()
        self.assertFalse(validate_retained_failure(row,exception,w,w,{(50,0,50):{}})['resolved'])
        with self.assertRaisesRegex(ValueError,'query domain'):
            validate_retained_failure(row,exception,w,w,{(2,0,1):{}})
        changed=copy.deepcopy(row);changed['after']['forward']['unknown']=[{'pos':[1,2,3]}]
        with self.assertRaisesRegex(ValueError,'changed original route failure'):
            validate_retained_failure(changed,exception,w,w,{})

    def test_extent_outside_dimension_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate,source,world,delta,recipe=self.fixture(Path(tmp))
            with np.load(delta) as f:data={k:f[k] for k in f.files}
            data['height']=1008;np.savez(delta,**data)
            with self.assertRaisesRegex(ValueError,'extent'):validate_delta(candidate)

    def test_frozen_proof_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);candidate,*_=self.fixture(root);review=root/'review';review.mkdir()
            write(review/'review.json',{'errors':[],'routes':97});config=root/'config.json';write(config,{'review_directory':str(review)})
            args=argparse.Namespace(candidate=candidate,config=config)
            freeze_files(args,save=True);freeze_files(args)
            write(review/'review.json',{'errors':[],'routes':96})
            with self.assertRaisesRegex(ValueError,'Frozen proof'):freeze_files(args)

    def test_missing_or_wrong_scope_replay_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);candidate,source,world,*_=self.fixture(root);prepare(world,candidate)
            args=argparse.Namespace(candidate=candidate,world=world,batch=72,
                expected=candidate/'recipe-replay-expected',production_log=root/'production.log')
            checked=validate_delta(candidate);prepared={'prepared_time_ns':time.time_ns()}
            with self.assertRaisesRegex(ValueError,'replay is missing'):validate_replay(args,checked,prepared)
            scope=replay_scope(args);scope['batch']=71
            args.production_log.write_text('SECTION_PATCH_REPLAY_SCOPE '+json.dumps(scope)+'\nProduction surface replay: 1 chunks, 3 changed cells\nBUILD SUCCESSFUL','utf8')
            with self.assertRaisesRegex(ValueError,'scope is missing or stale'):validate_replay(args,checked,prepared)
            scope['batch']=72
            args.production_log.write_text('SECTION_PATCH_REPLAY_SCOPE '+json.dumps(scope)+'\nProduction surface replay: 1 chunks, 3 changed cells\nBUILD SUCCESSFUL','utf8')
            validate_replay(args,checked,prepared)
            args.production_log.write_text('SECTION_PATCH_REPLAY_SCOPE '+json.dumps(scope)+'\nProduction surface replay: 1 chunks, 4 changed cells\nBUILD SUCCESSFUL','utf8')
            with self.assertRaisesRegex(ValueError,'scope differs'):validate_replay(args,checked,prepared)

    def test_freeze_keeps_deep_recipe_names_in_flat_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); candidate,*_=self.fixture(root)
            review=root/'review'; review.mkdir()
            config=root/'config.json'; write(config,{'review_directory':str(review)})
            relative=Path('after')/DATA/'-2_-1.dat'
            original=candidate/relative; original.parent.mkdir(parents=True)
            original.write_bytes(b'original deep recipe')
            args=argparse.Namespace(candidate=candidate,config=config)
            freeze_files(args,save=True); freeze_files(args)
            frozen=candidate/'section-release-freeze'
            index=read(frozen/'inventory.json')['files']
            name=index['candidate/'+relative.as_posix()]
            self.assertEqual(Path(name).name,name)
            self.assertEqual(original.read_bytes(),(frozen/name).read_bytes())
            original.write_bytes(b'changed deep recipe')
            with self.assertRaisesRegex(ValueError,'Frozen proof'):freeze_files(args)


if __name__=='__main__':unittest.main()

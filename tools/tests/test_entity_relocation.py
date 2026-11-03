import copy,tempfile,unittest
from pathlib import Path
import nbtlib
from map_pipeline.install.entity_moves import translated,prepare,ENTITIES
from transplant_s22_authority import build_region,read_region,parse_chunk
from apply_s20_approved_semantic_repairs import chunk_blob


def actor(uid,x=1.25):
    return nbtlib.Compound({'id':nbtlib.String('projectseele:industrial_member'),
        'UUID':nbtlib.IntArray([uid,2,3,4]),'Pos':nbtlib.List[nbtlib.Double]([x,68,2.5]),
        'Inventory':nbtlib.Compound({'Items':nbtlib.List[nbtlib.Compound]([
            nbtlib.Compound({'Slot':nbtlib.Byte(7),'Count':nbtlib.Byte(23),'identity':nbtlib.Long(2**60+5)})])}),
        'Tags':nbtlib.List[nbtlib.String](['original']), 'Health':nbtlib.Float(123.25)})


class EntityRelocationTests(unittest.TestCase):
    def test_full_payload_and_passenger_identity_preserved(self):
        old=actor(1);old['Passengers']=nbtlib.List[nbtlib.Compound]([actor(2)])
        new=translated(old,[1824,-144,640])
        self.assertEqual(list(new['Pos']),[1825.25,-76,642.5])
        self.assertEqual(new['Inventory'],old['Inventory'])
        self.assertEqual(new['Passengers'][0]['UUID'],old['Passengers'][0]['UUID'])
        self.assertEqual(list(old['Pos']),[1.25,68,2.5])

    def test_active_patrol_rejected(self):
        old=actor(1);old['LoiterActive']=nbtlib.Byte(1)
        with self.assertRaisesRegex(ValueError,'Active vehicle'):translated(old,[1,2,3])

    def test_empty_native_brain_is_preserved_but_location_memory_rejected(self):
        old=actor(1);old['Brain']=nbtlib.Compound(memories=nbtlib.Compound())
        self.assertEqual(translated(old,[1,2,3])['Brain'],old['Brain'])
        old['Brain']['memories']['minecraft:home']=nbtlib.Compound(pos=nbtlib.IntArray([1,2,3]))
        with self.assertRaisesRegex(ValueError,'Spatial actor'):translated(old,[1,2,3])

    def test_cross_region_stage_retains_other_actors_and_original_files(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);world=root/'world';candidate=root/'candidate';stage=root/'stage';candidate.mkdir();(world/ENTITIES).mkdir(parents=True)
            old=actor(1);other=actor(9);target=world/ENTITIES/'r.0.0.mca'
            chunk=nbtlib.File({'DataVersion':nbtlib.Int(3465),'Position':nbtlib.IntArray([0,0]),
                'Entities':nbtlib.List[nbtlib.Compound]([old,other]),'CustomMetadata':nbtlib.String('retained')})
            raw=[None]*1024;raw[0]=chunk_blob(chunk);data=build_region(bytes(4096),raw);target.write_bytes(data)
            new=translated(old,[1824,-144,640]);packet=nbtlib.Compound(Before=old,After=new,Delta=nbtlib.IntArray([1824,-144,640]))
            nbtlib.File({'Moves':nbtlib.List[nbtlib.Compound]([packet])}).save(candidate/'moves.dat',gzipped=True)
            pairs,report=prepare(candidate,world,stage,dict(entity_moves='moves.dat'))
            self.assertEqual(report['roots'],1);self.assertEqual(len(pairs),2);self.assertEqual(target.read_bytes(),data)
            source=parse_chunk(read_region(stage/ENTITIES/'r.0.0.mca')[1][0]);self.assertEqual(source['Entities'],[other]);self.assertEqual(source['CustomMetadata'],'retained')
            roots=[parse_chunk(blob)for _,p in pairs for blob in read_region(p)[1]if blob]
            received=[e for r in roots for e in r['Entities'] if tuple(e['UUID'])==tuple(old['UUID'])]
            self.assertEqual(received,[new])

    def test_inventory_change_is_not_a_translation(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);old=actor(1);new=translated(old,[1,0,0]);new['Health']=nbtlib.Float(300)
            nbtlib.File({'Moves':nbtlib.List[nbtlib.Compound]([nbtlib.Compound(Before=old,After=new,Delta=nbtlib.IntArray([1,0,0]))])}).save(root/'moves.dat',gzipped=True)
            with self.assertRaisesRegex(ValueError,'changes content'):
                prepare(root,root,root/'stage',dict(entity_moves='moves.dat'))


if __name__=='__main__':unittest.main()

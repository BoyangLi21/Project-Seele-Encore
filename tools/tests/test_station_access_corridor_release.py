import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from release_station_access_corridor import validate_plan


class CorridorContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.old=self.root/'old';self.c=self.root/'candidate'
        self.old.mkdir();(self.c/'plan').mkdir(parents=True);(self.c/'earthworks').mkdir()
        self.data=dict(bounds=np.array([0,0,4,4]),walk=np.zeros((5,5),bool),road=np.zeros((5,5),bool),
                       grade2=np.full((5,5),-150),ground=np.full((5,5),-76),tunnel=np.zeros((5,5),bool),
                       marking=np.zeros((5,5),bool),reserved=np.zeros((5,5),bool))
        self.data['walk'][2,0]=True;self.data['road'][2,0]=True
        np.savez_compressed(self.old/'network.npz',**self.data)
        self.new={k:v.copy()for k,v in self.data.items()};self.new['walk'][2,:4]=True;self.new['road'][2,:4]=True
        active=np.zeros((5,5),bool);active[2,:4]=True
        np.savez_compressed(self.c/'earthworks/road.npz',bounds=[0,0,4,4],active=active,walk=active)
        for name in ('catalog.json','station-volumes.json'):
            (self.old/name).write_text('[]','utf8');(self.c/'plan'/name).write_text('[]','utf8')

    def run_check(self):
        np.savez_compressed(self.c/'plan/network.npz',**self.new)
        return validate_plan(self.c,self.old)

    def test_finite_addition_preserves_existing_road(self):
        self.assertEqual(self.run_check()['public_columns'],4)

    def test_no_silent_existing_grade_or_road_change(self):
        for key,value in [('grade2',-149),('road',False),('walk',False),('tunnel',True)]:
            with self.subTest(key=key):
                old=self.new[key][2,0].copy();self.new[key][2,0]=value
                with self.assertRaises(ValueError):self.run_check()
                self.new[key][2,0]=old

    def test_declared_promotion_only(self):
        self.data['walk'][1,1]=True
        np.savez_compressed(self.old/'network.npz',**self.data)
        for key in ('walk','road'):self.new[key][1,1]=True
        with np.load(self.c/'earthworks/road.npz')as f:payload={k:f[k]for k in f.files}
        payload['walk'][1,1]=True;payload['active'][1,1]=True
        np.savez_compressed(self.c/'earthworks/road.npz',**payload)
        np.savez_compressed(self.c/'plan/network.npz',**self.new)
        with self.assertRaises(ValueError):validate_plan(self.c,self.old)
        self.assertEqual(validate_plan(self.c,self.old,[[1,1]])['public_columns'],5)
        with self.assertRaises(ValueError):validate_plan(self.c,self.old,[[1,1],[3,2]])

    def test_no_outside_or_unknown_metadata_mutation(self):
        for key,pos,value in [('ground',(4,4),-75),('reserved',(2,2),True),('road',(4,4),True)]:
            with self.subTest(key=key):
                old=self.new[key][pos].copy();self.new[key][pos]=value
                with self.assertRaises(ValueError):self.run_check()
                self.new[key][pos]=old

    def test_no_detached_or_missing_public_declaration(self):
        self.new['walk'][2,2]=False
        with self.assertRaises(ValueError):self.run_check()
        self.new['walk'][2,2]=True
        with np.load(self.c/'earthworks/road.npz')as f:payload={k:f[k]for k in f.files}
        payload['walk'][2,0]=False
        np.savez_compressed(self.c/'earthworks/road.npz',**payload)
        with self.assertRaises(ValueError):self.run_check()

    def test_catalogue_mutation_is_rejected(self):
        (self.c/'plan/catalog.json').write_text('[1]','utf8')
        with self.assertRaises(ValueError):self.run_check()


if __name__=='__main__':unittest.main()

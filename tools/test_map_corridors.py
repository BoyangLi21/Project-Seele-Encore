"""Prevent road retirement, equipment loss and impossible approach regressions."""
import unittest
from unittest.mock import patch
import numpy as np
from map_pipeline.corridors import compile_street,alignment,fit_ports,retain_bearings


class FlatStreet:
    def __init__(self,obstacle=False):self.obstacle=obstacle
    def state(self,x,y,z):
        if self.obstacle and (x,y,z)==(0,81,0):return 'minecraft:chest[facing=north,type=single,waterlogged=false]'
        if y==80 and abs(z)<=3:return 'minecraft:black_concrete'
        return 'minecraft:stone'if y<80 else'minecraft:air'


class CorridorRegression(unittest.TestCase):
    def row(self):
        return dict(id='measured-road',bounds=[-15,-12,15,12],points=[[-8,81,0],[8,81,0]],
                    carriage_width=7,sidewalk_width=1,retire_volumes=[[-15,80,-8,15,85,8]])

    @patch('map_pipeline.corridors.ground',return_value=np.full((25,31),79,np.int16))
    def test_republishing_the_same_floor_after_retirement_keeps_it(self,_):
        result,compiled=compile_street(FlatStreet(),self.row(),[],np.empty((0,3)))
        self.assertEqual(result['status'],'prepared')
        self.assertEqual(compiled[0][0,80,2],'minecraft:black_concrete')

    @patch('map_pipeline.corridors.ground',return_value=np.full((25,31),79,np.int16))
    def test_unknown_inventory_host_rejects_the_whole_street(self,_):
        result,compiled=compile_street(FlatStreet(True),self.row(),[],np.empty((0,3)))
        self.assertEqual(result['status'],'blocked');self.assertIsNone(compiled)
        self.assertTrue(any(r[:3]==[0,81,0]for r in result['blockers']))

    def test_large_height_difference_requires_a_longer_alignment(self):
        row=self.row();row['points']=[[-8,81,0],[8,100,0]]
        with self.assertRaisesRegex(ValueError,'grade exceeds'):alignment(row)

    def test_cross_sections_reject_incompatible_side_branch_levels(self):
        walk=np.zeros((7,9),bool);walk[2:5,2:7]=True
        old=np.full(walk.shape,160,np.int16);old[1]=170
        retained=np.zeros_like(walk);retained[1,2:7]=True;retained[5,2:7]=True
        sections=[{(z,x)for z in range(2,5)}for x in range(2,7)]
        with self.assertRaisesRegex(ValueError,'wider or longer'):
            fit_ports(walk,np.full_like(old,165),retained,old,sections)

    @patch('map_pipeline.corridors.ground',return_value=np.full((41,49),79,np.int16))
    def test_bridge_keeps_the_void_below_its_structural_deck(self,_):
        row=self.row();row['points']=[[-8,84,0],[8,84,0]]
        row['bounds']=[-24,-20,24,20]
        row['bridge']=dict(along=[4,12],deck_depth=2)
        report,compiled=compile_street(FlatStreet(),row,[],np.empty((0,3)))
        self.assertEqual(report['status'],'prepared')
        writes,field=compiled
        self.assertEqual(writes[0,80,0],'minecraft:air')
        self.assertEqual(writes[0,81,0],'minecraft:stone_bricks')
        self.assertEqual(field['target'][20,24],79)

    def test_full_width_interfaces_constrain_both_ends_and_raster_steps(self):
        walk=np.zeros((7,15),bool);walk[2:5,2:13]=True
        retained=np.zeros_like(walk);retained[2:5,1]=True;retained[2:5,13]=True
        old=np.full(walk.shape,160,np.int16);old[:,13]=170
        fitted=fit_ports(walk,np.full(walk.shape,166,np.int16),retained,old)
        self.assertTrue(np.all(abs(fitted[2:5,2]-160)<=1))
        self.assertTrue(np.all(abs(fitted[2:5,12]-170)<=1))
        self.assertLessEqual(abs(np.diff(fitted[2:5,2:13],axis=1)).max(),1)

    def test_bored_road_keeps_the_ridge_above_its_lined_crown(self):
        class Mountain(FlatStreet):
            def state(self,x,y,z):
                if abs(x)<=4:return 'minecraft:stone'if y<=100 else'minecraft:air'
                return super().state(x,y,z)
        terrain=np.full((25,31),79,np.int16);terrain[:,11:20]=100
        row=self.row();row['tunnel']=dict(along=[4,12])
        with patch('map_pipeline.corridors.ground',return_value=terrain):
            report,compiled=compile_street(Mountain(),row,[],np.empty((0,3)))
        self.assertEqual(report['status'],'prepared')
        writes,field=compiled
        self.assertEqual(field['target'][12,15],100)
        self.assertEqual(writes[0,85,0],'minecraft:air')
        self.assertEqual(writes[0,87,0],'minecraft:stone_bricks')
        self.assertNotIn((0,90,0),writes)
        self.assertTrue(field['tunnel'][12,15])
        self.assertFalse(field['bridge_span'].any())

    @patch('map_pipeline.corridors.ground',return_value=np.full((25,31),79,np.int16))
    def test_earthworks_do_not_retire_paving_outside_walk(self,_):
        row=self.row();row['points']=[[-8,84,0],[8,84,0]];row['carriage_width']=1;row['sidewalk_width']=0
        result,compiled=compile_street(FlatStreet(),row,[],np.empty((0,3)))
        self.assertEqual(result['status'],'prepared')
        self.assertNotIn((0,80,2),compiled[0])

    def test_foundation_and_road_are_joined_without_undermining(self):
        old=np.full((21,21),80,np.int16);old[12:15,8:13]=84
        target=np.full_like(old,80);walk=np.zeros_like(old,bool);walk[2]=True
        fitted=retain_bearings(target,old,walk,[[8,85,12,12,110,14]],[0,0,20,20],.5)
        self.assertTrue(np.all(fitted[12:15,8:13]==84))
        self.assertTrue(np.all(fitted[2]==80))
        self.assertLessEqual(abs(np.diff(fitted,axis=0)).max(),1)

    def test_embankment_cannot_fill_the_retained_ground_floor(self):
        old=np.full((21,21),80,np.int16);target=np.full_like(old,84)
        walk=np.zeros_like(old,bool);walk[2]=True
        fitted=retain_bearings(target,old,walk,[[8,81,12,12,110,14]],[0,0,20,20],.5)
        self.assertTrue(np.all(fitted[12:15,8:13]==80))
        self.assertTrue(np.all(fitted[2]==84))

    def test_local_bearing_adjustment_preserves_the_existing_steep_hillside(self):
        old=np.tile(np.arange(21,dtype=np.int16)*2+60,(21,1))
        target=old.copy();target[9:12,9:12]+=2
        walk=np.zeros_like(old,bool)
        fitted=retain_bearings(target,old,walk,[[10,81,10,10,100,10]],[0,0,20,20],.6,relative=True)
        self.assertEqual(fitted[10,10],old[10,10])
        self.assertTrue(np.array_equal(fitted[:,0],old[:,0]))
        self.assertTrue(np.array_equal(fitted[:,-1],old[:,-1]))

    @patch('map_pipeline.corridors.ground',return_value=np.full((25,31),79,np.int16))
    def test_retiring_one_buried_light_does_not_authorize_another(self,_):
        class Lamps(FlatStreet):
            def state(self,x,y,z):
                if (x,y,z) in ((0,80,0),(0,81,1)):
                    return 'minecraft:lantern[hanging=true,waterlogged=false]'
                return super().state(x,y,z)
        row=self.row();row['retire_auxiliary_points']=[dict(pos=[0,80,0],state=Lamps().state(0,80,0))]
        result,compiled=compile_street(Lamps(),row,[],np.empty((0,3)))
        self.assertEqual(result['status'],'blocked');self.assertIsNone(compiled)
        self.assertTrue(any(p[:3]==[0,81,1]for p in result['blockers']))


if __name__=='__main__':unittest.main()

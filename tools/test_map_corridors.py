"""Prevent road retirement, equipment loss and impossible approach regressions."""
import unittest
from unittest.mock import patch
import numpy as np
from map_pipeline.corridors import compile_street,alignment,fit_ports


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

    def test_full_width_interfaces_constrain_both_ends_and_raster_steps(self):
        walk=np.zeros((7,15),bool);walk[2:5,2:13]=True
        retained=np.zeros_like(walk);retained[2:5,1]=True;retained[2:5,13]=True
        old=np.full(walk.shape,160,np.int16);old[:,13]=170
        fitted=fit_ports(walk,np.full(walk.shape,166,np.int16),retained,old)
        self.assertTrue(np.all(abs(fitted[2:5,2]-160)<=1))
        self.assertTrue(np.all(abs(fitted[2:5,12]-170)<=1))
        self.assertLessEqual(abs(np.diff(fitted[2:5,2:13],axis=1)).max(),1)

    @patch('map_pipeline.corridors.ground',return_value=np.full((25,31),79,np.int16))
    def test_earthworks_do_not_retire_paving_outside_walk(self,_):
        row=self.row();row['points']=[[-8,84,0],[8,84,0]];row['carriage_width']=1;row['sidewalk_width']=0
        result,compiled=compile_street(FlatStreet(),row,[],np.empty((0,3)))
        self.assertEqual(result['status'],'prepared')
        self.assertNotIn((0,80,2),compiled[0])


if __name__=='__main__':unittest.main()

import unittest
import numpy as np
from map_pipeline.corridors import alignment, relax_exterior_earthworks


class ExteriorSlopeTests(unittest.TestCase):
    def test_fill_meets_retained_low_street_without_spreading(self):
        old=np.full((7,12),80,np.int16)
        old[:,1]=72
        target=old.copy();target[2:5,2:9]+=6
        walk=np.zeros(old.shape,bool);walk[3,7:9]=True
        result=relax_exterior_earthworks(target,old,walk)
        np.testing.assert_array_equal(result[walk],target[walk])
        self.assertTrue(np.all(result[target==old]==old[target==old]))
        self.assertTrue(np.all(abs(result-old)<=abs(target-old)))
        for axis in (0,1):
            exterior=~np.take(walk,range(walk.shape[axis]-1),axis=axis)&~np.take(walk,range(1,walk.shape[axis]),axis=axis)
            self.assertTrue(np.all(abs(np.diff(result,axis=axis))[exterior]<=np.maximum(3,abs(np.diff(old,axis=axis))+1)[exterior]))

    def test_existing_cliff_and_buried_terrain_stay_exact(self):
        old=np.array([[80,80,94,94],[80,80,94,94]],np.int16)
        result=relax_exterior_earthworks(old,old,np.zeros(old.shape,bool))
        np.testing.assert_array_equal(result,old)

    def test_bend_grade_uses_physical_distance_and_keeps_port_heights(self):
        row=dict(id='bent-mountain-road',points=[[0,100,0],[20,98,0],[20,96,20],[40,94,20]],
                 maximum_grade=.11,arc_length_grade=True)
        curve,distance=alignment(row)
        ds=np.linalg.norm(np.diff(curve[:,[0,2]],axis=0),axis=1)
        np.testing.assert_allclose(np.diff(distance),ds)
        self.assertLessEqual(float((abs(np.diff(curve[:,1]))/ds).max()),.11)
        np.testing.assert_allclose(curve[[0,-1]],[[0,100,0],[40,94,20]])


if __name__=='__main__':unittest.main()

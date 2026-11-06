import unittest
import numpy as np
from map_pipeline.rail_civil_geometry import bearing,columns,dense_points,vertical_bounds


class CivilGeometryTests(unittest.TestCase):
    def test_negative_native_datums_never_put_bearing_above_track(self):
        for y in np.linspace(-56,-25,801):
            _,_,top=bearing(y)
            self.assertLessEqual(top,y+1e-7)
            self.assertLess(y-top,.500001)

    def test_diagonal_curve_has_contiguous_columns_at_fractional_levels(self):
        rows=[dict(kind='rail',points=[[0.5,-10.2,0.5],[20.5,-12.7,15.5]])]
        cells=columns(rows,[0]);todo=[next(iter(cells))];seen=set(todo)
        while todo:
            x,z=todo.pop()
            for q in [(x-1,z),(x+1,z),(x,z-1),(x,z+1)]:
                if q in cells and q not in seen:seen.add(q);todo.append(q)
        self.assertEqual(len(seen),len(cells))
        for row in cells.values():
            self.assertGreaterEqual(vertical_bounds(row)[3]-row['high'],4.5-1e-7)

    def test_crossing_at_different_elevations_is_not_flattened(self):
        rows=[dict(points=[[0,0,0],[10,0,0]]),dict(points=[[5,8,-5],[5,8,5]])]
        with self.assertRaisesRegex(ValueError,'Different rail levels'):
            columns(rows,[0,1])

    def test_densification_bounds_horizontal_sampling(self):
        p=dense_points([[0,0,0],[3,2,4]])
        self.assertLessEqual(np.linalg.norm(np.diff(p[:,[0,2]],axis=0),axis=1).max(),.250001)
        np.testing.assert_array_equal(p[-1],[3,2,4])


if __name__=='__main__':unittest.main()

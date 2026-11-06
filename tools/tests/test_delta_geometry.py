import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
import numpy as np

from install_hakone_array_patch import Palette, compose, selected
from map_pipeline.delta_geometry import checked_indices
from map_pipeline.launch_protection import LaunchProtection
from map_pipeline.delivery_check import write
from rebase_route_audit import rebase


class DeltaGeometryTest(unittest.TestCase):
    def write(self, root, name, y, origin=None, height=None):
        bottom = -128 if origin is None else origin
        data = dict(coordinates=[[-2, -1]], ranges=[0, 1],
                    indices=[(y-bottom)*256+255], before=[0], after=[1],
                    palette=['minecraft:air', 'minecraft:glass'])
        if origin is not None: data.update(y_origin=origin, height=height)
        path = root/name
        np.savez(path, **data)
        return path

    def test_deep_and_surface_same_chunk_keep_absolute_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            deep = self.write(root, 'deep.npz', -560, -672, 992)
            surface = self.write(root, 'surface.npz', 80)
            cells = compose([deep, surface], Palette())
            offsets = cells[-2, -1][0]
            self.assertEqual([-560, 80], (offsets//256-128).tolist())
            self.assertEqual({-35, 5}, selected(cells)[-2, -1])
            self.assertEqual([255, 255], (offsets % 4096).tolist())

    def test_declared_deep_delta_cannot_bypass_launch_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), 'deep.npz', -560, -672, 992)
            guard = LaunchProtection([('deep mechanism', [-17, -560, -1, -17, -560, -1])])
            with self.assertRaisesRegex(ValueError, 'deep mechanism'):
                guard.assert_delta(path)
            self.assertEqual(1, LaunchProtection([('surface', [-17, 80, -1, -17, 80, -1])]).assert_delta(path))

    def test_same_absolute_cell_in_different_coordinate_frames_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = self.write(root, 'a.npz', 80)
            b = self.write(root, 'b.npz', 80, -672, 992)
            with np.load(b) as data: payload = {k:data[k] for k in data.files}
            payload['palette'] = ['minecraft:air', 'minecraft:stone']
            np.savez(b, **payload)
            with self.assertRaisesRegex(ValueError, 'Conflicting final states'):
                compose([a, b], Palette())

    def test_invalid_extents_are_rejected_before_composition(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), 'deep.npz', -560, -672, 992)
            with np.load(path) as data: payload = {k:data[k] for k in data.files}
            cases = [dict(y_origin=-673), dict(height=0), dict(height=1008),
                     dict(y_origin=-1360, height=1680), dict(height=992.0),
                     dict(indices=np.array([-1])), dict(indices=np.array([992*256]))]
            for changes in cases:
                np.savez(path, **dict(payload, **changes))
                with self.subTest(changes=changes), np.load(path) as data:
                    with self.assertRaises(ValueError): checked_indices(data)

    def test_deep_delta_invalidates_overlapping_route_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); prior=root/'prior'; authority=root/'authority'; candidate=root/'candidate'
            for p in (prior,authority,candidate/'delta'):p.mkdir(parents=True)
            (authority/'network.npz').write_bytes(b'unchanged network')
            write(authority/'catalog.json',[])
            write(prior/'audit.json',dict(authority=str(authority)))
            np.savez(prior/'actual-routes.npz',x=[-17],z=[-1],grade2=[-1120],road=[False])
            self.write(candidate/'delta','r.-1.-1.npz',-559,-672,992)
            write(candidate/'manifest.json',dict(cells=1))
            receipt=root/'installation.json'
            write(receipt,dict(status='installed',changed_section_readback=True,cells=1,candidates=[str(candidate)]))
            with self.assertRaisesRegex(ValueError,'changed audit samples'):
                rebase(Namespace(prior=prior,authority=authority,candidate=candidate,installation=receipt,out=root/'rebased'))


if __name__ == '__main__':
    unittest.main()

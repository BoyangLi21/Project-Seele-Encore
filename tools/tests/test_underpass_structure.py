import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from finish_hakone_road_underpass import check_structure


class StructureTests(unittest.TestCase):
    def check(self,roof,extra=()):
        wall=[[0,y,0]for y in range(5)]
        solid={tuple(p)for p in wall+roof+[[0,-1,0]]+list(extra)}
        class Saved:
            def __init__(self,path):pass
            def state(self,x,y,z):return 'minecraft:light_gray_concrete'if(x,y,z)in solid else'minecraft:air'
        with tempfile.TemporaryDirectory()as folder:
            p=Path(folder)
            (p/'underpass-structure.json').write_text(json.dumps(dict(roof_cells=roof,wall_cells=wall,
                footings=[[0,0,0]],open_portals=[[[10,0,0]],[[20,0,0]]])),'utf8')
            with patch('finish_hakone_road_underpass.Editor',Saved):return check_structure(p)

    def test_roof_with_face_connected_bearing_passes(self):
        self.assertEqual(self.check([[1,4,0],[2,4,0]]),[])

    def test_diagonal_step_is_not_a_structural_connection(self):
        errors=self.check([[1,4,0],[2,5,0]])
        self.assertTrue(any(r[0]=='underpass cells disconnected from founded walls'for r in errors))

    def test_portal_clearance_is_checked_from_saved_blocks(self):
        errors=self.check([[1,4,0]],[[10,4,0]])
        self.assertIn(['underpass portal blocked',10,4,0],errors)


if __name__=='__main__':unittest.main()

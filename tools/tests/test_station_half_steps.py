import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import verify_hakone_station_connection as connection


class StationHalfStepsTest(unittest.TestCase):
    def check_path(self,blocked):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'plan').mkdir()
            (root/'plan/buildings.json').write_text(json.dumps([dict(id='test',station_id='test',kind='station',approach=[0,1,0],platform=[2,-1,0])]),'utf8')
            (root/'plan/native-curves.json').write_text(json.dumps(dict(trains=[dict(points=[[100,10,100],[101,10,100]])])),'utf8')
            np.savez_compressed(root/'plan/network.npz',bounds=[0,0,2,0],walk=np.ones((1,3),bool),grade2=np.array([[0,-1,-2]]))
            blocks=np.zeros((1,448,16,16),np.uint16)
            blocks[0,128,0,0]=1;blocks[0,128,0,1]=2;blocks[0,127,0,2]=1
            if blocked:blocks[0,129,0,1]=1
            class Fixture:
                def region(self,x,z):
                    return dict(after=blocks,index={(0,0):0},names=['minecraft:air','minecraft:smooth_stone','minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'])
            with patch.object(connection,'Editor',return_value=Fixture()):
                return connection.verify(root)

    def test_full_slab_full_sequence_remains_walkable(self):
        report=self.check_path(False)
        self.assertFalse(report['errors'])
        self.assertEqual(report['stations'][0]['path'],[[0,1.,0],[1,.5,0],[2,0.,0]])

    def test_obstruction_above_slab_still_blocks_passenger(self):
        report=self.check_path(True)
        self.assertTrue(report['errors'])


if __name__=='__main__':unittest.main()

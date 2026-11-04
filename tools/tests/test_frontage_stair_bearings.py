import unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np
from scipy.ndimage import label
from author_hakone_district_blocks import author


class FrontageStairBearingsTest(unittest.TestCase):
    def test_rotated_multistorey_flights_are_supported_and_walkable(self):
        for rotation in range(4):
            with self.subTest(rotation=rotation),patch('author_hakone_district_blocks.load_original',return_value=[]):
                site=dict(half=[8,10],floors=4,rotation=rotation,centre=[40,60],floor=90,style='residential')
                frontage,_=author(site,dict(id='test/01-01'),Path('.'))
                cells={}
                for x,y,z,X,Y,Z,state in frontage.operations:
                    for px in range(x,X+1):
                        for py in range(y,Y+1):
                            for pz in range(z,Z+1):cells[px,py,pz]=state
                solid={p for p,s in cells.items() if s!='minecraft:air'}
                lo=np.min(list(solid),axis=0);hi=np.max(list(solid),axis=0);v=np.zeros(hi-lo+1,bool)
                for p in solid:v[tuple(np.asarray(p)-lo)]=True
                _,count=label(v)
                self.assertEqual(count,1,'Every flight must join the floor and building structure by faces')
                for p,s in cells.items():
                    if not s.startswith('minecraft:stone_brick_stairs['):continue
                    for dy in (1,2):self.assertEqual(cells.get((p[0],p[1]+dy,p[2]),'minecraft:air'),'minecraft:air')


if __name__=='__main__':unittest.main()

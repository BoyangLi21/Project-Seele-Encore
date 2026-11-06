"""Regressions for hidden roads, stacked floors and collaborator preservation."""
import tempfile,unittest,zipfile
from pathlib import Path
import numpy as np
from map_pipeline.roads import road_layers,layer_graph
from install_hakone_array_patch import prepare_jar
from map_pipeline.world_roads import chunk_layers


class RoadDiscovery(unittest.TestCase):
    def test_deep_and_top_world_layers_keep_separate_coordinates(self):
        chunk={'sections':[{'Y':-84,'block_states':{'palette':[{'Name':'minecraft:black_concrete'}]}},
                           {'Y':19,'block_states':{'palette':[{'Name':'minecraft:black_concrete'}]}}]}
        rows=chunk_layers(chunk)
        self.assertEqual(sorted(set(rows[:,1])),[-1329,319])
        labels=layer_graph(rows)
        self.assertEqual(len(set(labels)),2)

    def test_truncated_indices_are_not_read_as_air(self):
        chunk={'sections':[{'Y':-30,'block_states':{'palette':[
            {'Name':'minecraft:air'},{'Name':'minecraft:black_concrete'}],'data':[]}}]}
        with self.assertRaisesRegex(ValueError,'truncated'):
            chunk_layers(chunk)

    def test_buried_and_stacked_roads_are_discovered(self):
        names=['minecraft:air','minecraft:black_concrete','minecraft:stone']
        v=np.zeros((448,16,16),np.uint16)
        v[208,4,4]=1;v[209:212,4,4]=2;v[228,4,4]=1
        rows=road_layers(v,names)
        self.assertEqual(rows[:,1].tolist(),[80,100])
        self.assertEqual(rows[:,5].tolist(),[3,0])
        self.assertNotEqual(*layer_graph(rows))

    def test_diagonal_contact_does_not_join_roads(self):
        p=np.array([[0,80,0,162,1,0,0,0],[1,80,1,162,1,0,0,0],[2,80,1,162,1,0,0,0]])
        labels=layer_graph(p)
        self.assertNotEqual(labels[0],labels[1]);self.assertEqual(labels[1],labels[2])

    def test_map_resource_install_retains_collaborator_classes(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t);resource='data/projectseele/worldgen/hakone_surface.bin.gz'
            with zipfile.ZipFile(root/'installed.jar','w',compression=zipfile.ZIP_DEFLATED)as f:
                f.writestr('com/projectseele/client/EvaRenderer.class',b'collaborator-code')
                f.writestr('assets/projectseele/model.glb',b'authored-model');f.writestr(resource,b'old')
            with zipfile.ZipFile(root/'compiled.jar','w')as f:
                f.writestr('com/projectseele/client/EvaRenderer.class',b'unrelated-build');f.writestr(resource,b'new')
            self.assertEqual(prepare_jar(root/'installed.jar',root/'compiled.jar',root/'merged.jar',True),0)
            with zipfile.ZipFile(root/'merged.jar')as f:
                self.assertEqual(f.read('com/projectseele/client/EvaRenderer.class'),b'collaborator-code')
                self.assertEqual(f.read('assets/projectseele/model.glb'),b'authored-model')
                self.assertEqual(f.read(resource),b'new')
                self.assertEqual(len(f.namelist()),len(set(f.namelist())))
                self.assertEqual(f.getinfo('assets/projectseele/model.glb').compress_type,zipfile.ZIP_DEFLATED)

    def test_terrain_consumer_merge_has_finite_class_scope(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t);base='data/projectseele/worldgen/'
            names=[base+'hakone_surface.bin.gz',base+'hakone_surface_blend.bin.gz']
            names+=['com/projectseele/world/HakoneSurfaceField'+s+'.class'for s in ('','$Field','$Surface')]
            retained=['com/projectseele/entity/EvaUnit01Entity.class','assets/projectseele/geo/entry_plug_carrier.geo.json',
                      'com/projectseele/world/GeoFrontBoundedChunkGenerator.class','com/projectseele/world/TvWorldPreviewTerrain.class']
            with zipfile.ZipFile(root/'old.jar','w',compression=zipfile.ZIP_DEFLATED)as f:
                for n in names+retained:f.writestr(n,b'installed '+n.encode())
            with zipfile.ZipFile(root/'new.jar','w')as f:
                for n in names+retained:f.writestr(n,b'compiled '+n.encode())
            self.assertEqual(prepare_jar(root/'old.jar',root/'new.jar',root/'out.jar',terrain_consumer_only=True),3)
            with zipfile.ZipFile(root/'out.jar')as f:
                for n in names:self.assertEqual(f.read(n),b'compiled '+n.encode())
                for n in retained:self.assertEqual(f.read(n),b'installed '+n.encode())
                self.assertEqual(len(f.namelist()),len(set(f.namelist())))


if __name__=='__main__':unittest.main()

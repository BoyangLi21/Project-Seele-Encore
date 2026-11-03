"""Native cache corruption and channel/height regression tests."""
import struct,unittest
import numpy as np
from PIL import Image
from xaero_cache_codec import Cache,pack_heights,unpack_heights

def fixture(leaf=True):
    prefix=bytes(range(20))if leaf else b''
    data=struct.pack('>i',65561)+prefix+bytes([0])+struct.pack('>i',17)+bytes([17])+struct.pack('>i',23)+b'\xff'+struct.pack('>i',0)
    for key in (0,17):
        rgb=np.zeros((64,64,4),np.uint8);rgb[:]=[13,72,91,45] # native light,R,G,B
        h=np.full((64,64),-128 if key==0 else 174,np.int16);h[0,0]=-32768
        data+=bytes([key,0])+struct.pack('>ii',32856,16384)+rgb.tobytes()+b'\x01'+pack_heights(h)*2+struct.pack('>i',0)
        if not leaf:data+=struct.pack('>4i',1,2,3,4)
    return data+b'\xff'

class NativeCacheTests(unittest.TestCase):
    def test_leaf_exact_colour_light_height_roundtrip(self):
        raw=fixture();c=Cache(raw)
        self.assertEqual(c.encode(),raw)
        for t in c.tiles.values():
            self.assertEqual(tuple(np.asarray(t.image())[1,1]),(72,91,45,13))
            self.assertEqual(t.replaced(t.image(),unpack_heights(t.heights),unpack_heights(t.top_heights)),t.raw)
    def test_partial_update_preserves_other_tile(self):
        c=Cache(fixture());t=c.tiles[0];image=np.array(t.image());image[3,4]=[40,41,42,0];h=unpack_heights(t.heights);h[3,4]=199
        n=Cache(c.encode({0:t.replaced(Image.fromarray(image,'RGBA'),h,h)}))
        self.assertEqual(n.tiles[17].raw,c.tiles[17].raw)
        self.assertEqual(n.prefix,c.prefix)
        self.assertEqual(unpack_heights(n.tiles[0].heights)[3,4],199)
        self.assertEqual(tuple(np.asarray(n.tiles[0].image())[3,4]),(40,41,42,0))
    def test_branch_child_versions_preserved(self):
        raw=fixture(False);c=Cache(raw,False);self.assertEqual(c.encode(),raw)
        self.assertEqual(c.tiles[0].biomes[-16:],struct.pack('>4i',1,2,3,4))
    def test_signed_heights_and_unknown(self):
        a=np.resize(np.array([-32768,-128,-1,0,174,319,2047,-2048],np.int16),(64,64))
        np.testing.assert_array_equal(unpack_heights(pack_heights(a)),a)
    def test_truncation_rejected(self):
        with self.assertRaises(ValueError):Cache(fixture()[:-50])
    def test_new_format_is_not_silently_guessed(self):
        with self.assertRaises(ValueError):Cache(struct.pack('>i',65562)+fixture()[4:])

if __name__=='__main__':unittest.main()

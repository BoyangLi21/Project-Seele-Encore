import unittest
from shader_ground_hatch_material import COVER, patch_text

PROPERTIES = '\r\n'.join([
    '# Grass',
    'block.10124=grass_block:snowy=true podzol:snowy=true mycelium:snowy=true',
    '',
    'block.10132=grass_block:snowy=false',
    'block.10136=dirt coarse_dirt',
    ''])


class ShaderGroundHatchMaterialTest(unittest.TestCase):
    def test_the_cover_joins_the_plain_grass_entry_and_nothing_else_changes(self):
        patched = patch_text(PROPERTIES)
        self.assertEqual(patched, PROPERTIES.replace('block.10132=grass_block:snowy=false', 'block.10132=grass_block:snowy=false ' + COVER))
        self.assertEqual(patched.count(COVER), 1)
        # The file keeps its own line endings.
        self.assertNotIn('\n', patched.replace('\r\n', ''))

    def test_a_patched_pack_is_left_alone(self):
        patched = patch_text(PROPERTIES)
        self.assertEqual(patch_text(patched), patched)

    def test_a_pack_without_that_entry_is_refused(self):
        with self.assertRaises(ValueError):
            patch_text('block.10124=grass_block:snowy=true\nblock.10136=dirt\n')
        with self.assertRaises(ValueError):
            patch_text('block.1=grass_block:snowy=false\nblock.2=grass_block:snowy=false stone\n')


if __name__ == '__main__':
    unittest.main()

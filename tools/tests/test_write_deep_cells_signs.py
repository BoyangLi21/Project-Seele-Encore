import json
import unittest
from write_deep_cells import sign_entity, sign_text


class SignTextTest(unittest.TestCase):
    def test_four_lines_as_text_components(self):
        lines = sign_text(['→ 湾岸防卫区站', '贯通线'])
        self.assertEqual([json.loads(str(m))['text'] for m in lines], ['→ 湾岸防卫区站', '贯通线', '', ''])

    def test_entity_matches_the_block_kind(self):
        e = sign_entity({'pos': [1, 2, 3], 'front': ['a']}, 'minecraft:spruce_hanging_sign[rotation=0]')
        self.assertEqual(str(e['id']), 'minecraft:hanging_sign')
        self.assertEqual((int(e['x']), int(e['y']), int(e['z'])), (1, 2, 3))
        self.assertEqual(str(sign_entity({'pos': [0, 0, 0]}, 'minecraft:oak_sign[rotation=4]')['id']), 'minecraft:sign')

    def test_more_than_four_lines_is_refused(self):
        with self.assertRaises(ValueError):
            sign_text(['1', '2', '3', '4', '5'])


if __name__ == '__main__':
    unittest.main()

import unittest
from write_deep_cells import ITEM42_CELLS, item42_refusal

CONCRETE = 'minecraft:light_gray_concrete'
AIR = 'minecraft:air'


class Item42CityLiftSwitchTest(unittest.TestCase):
    def test_the_table_is_the_528_cells(self):
        self.assertEqual(len(ITEM42_CELLS), 528)
        self.assertIn((-175, 85, 91), ITEM42_CELLS)        # old shaft wall in original96/66's raised space
        self.assertIn((-179, -8, 97), ITEM42_CELLS)        # old shaft wall in its lowered space

    def test_a_listed_cell_cleared_from_an_old_block_passes(self):
        rows = [(-175, 85, 91, CONCRETE, AIR), (-179, -8, 97, 'minecraft:gray_stained_glass', AIR)]
        self.assertIsNone(item42_refusal(rows, {(-175, 85, 91), (-179, -8, 97)}))

    def test_an_unlisted_cell_in_a_lift_space_is_refused(self):
        rows = [(-170, 85, 100, CONCRETE, AIR)]
        self.assertIn('not one of the 528', item42_refusal(rows, {(-170, 85, 100)}))

    def test_a_listed_cell_with_another_block_or_not_cleared_is_refused(self):
        self.assertIn('may only be cleared', item42_refusal([(-175, 85, 91, 'minecraft:stone', AIR)], {(-175, 85, 91)}))
        self.assertIn('may only be cleared', item42_refusal([(-175, 85, 91, CONCRETE, 'minecraft:stone')], {(-175, 85, 91)}))

    def test_rows_outside_lift_spaces_are_not_its_business(self):
        self.assertIsNone(item42_refusal([(0, 70, 0, 'minecraft:stone', AIR)], set()))


if __name__ == '__main__':
    unittest.main()

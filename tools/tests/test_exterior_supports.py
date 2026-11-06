import unittest
from repair_hakone_exterior_supports import require_outside_occupied

class MovedParcelProtection(unittest.TestCase):
    def setUp(self):
        self.row=dict(id='retained-shop',occupied_bounds=[10,20,30,16,28,36],translation=[96,22,35])

    def test_current_room_rejected_after_three_axis_move(self):
        with self.assertRaises(ValueError):
            require_outside_occupied((109,45,68),[self.row])

    def test_new_exterior_collar_does_not_count_as_room(self):
        require_outside_occupied((105,45,68),[self.row])

    def test_vacated_source_is_not_the_current_occupied_volume(self):
        require_outside_occupied((13,23,33),[self.row])

    def test_unmoved_room_still_rejected(self):
        row=dict(self.row,translation=[0,0,0])
        with self.assertRaises(ValueError):
            require_outside_occupied((13,23,33),[row])

if __name__=='__main__':unittest.main()

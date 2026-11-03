import unittest
from map_pipeline.payload_exceptions import record_exception

class PayloadExceptions(unittest.TestCase):
    def test_soil_excavation_then_furniture_keeps_captured_before(self):
        rows=[]
        record_exception(rows,dict(pos=[1,2,3],before='dirt',after='air',kind='excavate'))
        record_exception(rows,dict(pos=[1,2,3],before='air',after='awning',kind='canopy'))
        self.assertEqual(len(rows),1)
        self.assertEqual((rows[0]['before'],rows[0]['after']),('dirt','awning'))

    def test_unrelated_intermediate_state_is_rejected(self):
        rows=[dict(pos=[1,2,3],before='dirt',after='air')]
        with self.assertRaises(ValueError):record_exception(rows,dict(pos=[1,2,3],before='stone',after='awning'))

if __name__=='__main__':unittest.main()

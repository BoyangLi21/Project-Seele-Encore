import copy
import unittest

from map_pipeline.station_consist import verified_platform_consists


class PlatformConsistTests(unittest.TestCase):
    def setUp(self):
        platforms = [dict(rail_id='long', name='1', required_train_length=120, minimum_end_margin=9),
                     dict(rail_id='short', name='2', required_train_length=18, minimum_end_margin=7)]
        self.proof = dict(input_plan=dict(stations=[dict(id='s', name='Station', platforms=platforms)]),
                          platforms=[dict(input_station_id='s', input_rail_id=r, station='Station',
                                          platform_name=n, platform_length=l)
                                     for r,n,l in [('long','1',142),('short','2',43)]])
        requirements = [dict(rail_id=p['rail_id'], platform_name=p['name'],
                             required_train_length=p['required_train_length'],
                             minimum_end_margin=p['minimum_end_margin']) for p in platforms]
        self.layout = dict(stations=[dict(id='s', name='Station', platform_lengths=[142,43],
                                          planned_consist_length=18, platform_consists=requirements)])

    def test_native_output_order_does_not_change_ownership(self):
        self.proof['platforms'].reverse()
        result=verified_platform_consists(self.proof,self.layout)
        self.assertEqual([r['actual_centred_end_margin'] for r in result],[11,12.5])

    def test_mixed_station_cannot_hide_behind_short_scalar(self):
        del self.layout['stations'][0]['platform_consists']
        with self.assertRaises(ValueError):verified_platform_consists(self.proof,self.layout)

    def test_rejects_wrong_platform_and_station_bindings(self):
        mutations=[('input_rail_id','long'),('input_station_id','other'),('platform_name','1'),('station','Other')]
        for key,value in mutations:
            with self.subTest(key=key):
                proof=copy.deepcopy(self.proof);proof['platforms'][1][key]=value
                with self.assertRaises(ValueError):verified_platform_consists(proof,self.layout)

    def test_rejects_short_platform_even_when_train_alone_fits(self):
        self.proof['platforms'][0]['platform_length']=130
        self.layout['stations'][0]['platform_lengths'][0]=130
        with self.assertRaises(ValueError):verified_platform_consists(self.proof,self.layout)

    def test_rejects_swapped_or_nonfinite_requirements(self):
        for value in [18,float('nan'),-1]:
            with self.subTest(value=value):
                layout=copy.deepcopy(self.layout)
                layout['stations'][0]['platform_consists'][0]['required_train_length']=value
                with self.assertRaises(ValueError):verified_platform_consists(self.proof,layout)

    def test_rejects_omitted_or_duplicate_platform(self):
        for operation in ('omit','duplicate'):
            proof=copy.deepcopy(self.proof)
            if operation=='omit':proof['platforms'].pop()
            else:proof['platforms'].append(copy.deepcopy(proof['platforms'][0]))
            with self.assertRaises(ValueError):verified_platform_consists(proof,self.layout)


if __name__=='__main__':unittest.main()

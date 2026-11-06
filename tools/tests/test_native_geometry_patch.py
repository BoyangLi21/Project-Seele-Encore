import copy,json,tempfile,unittest
from pathlib import Path
from prepare_mtr_member_patch_r52 import primitive
from map_pipeline.native_geometry_patch import expected


def encode(value):
    if isinstance(value,dict):
        assert len(value)<16
        return bytes([0x80+len(value)])+b''.join(primitive(k)+encode(v) for k,v in value.items())
    if isinstance(value,list):
        assert len(value)<16
        return bytes([0x90+len(value)])+b''.join(map(encode,value))
    return primitive(value)


class NativeGeometryPatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.c=Path(self.tmp.name)
        self.oldname='projectseele/geofront/rails/00/old';self.newname='projectseele/geofront/rails/00/new'
        self.depot='projectseele/geofront/depots/00/owner'
        self.rail=dict(position1=dict(x=0,y=0,z=0),position2=dict(x=10,y=0,z=0),shape='QUADRATIC',verticalRadius=40.,isPlatform=False,isSiding=False,styles=['default_3d'])
        self.after=copy.deepcopy(self.rail);self.after['position2']['y']=1;self.after.update(shape='TWO_RADII',verticalRadius=5.)
        edge=dict(startPosition=self.rail['position1'],endPosition=self.rail['position2'],shape='QUADRATIC',verticalRadius=40.,startDistance=20.,endDistance=30.,stopIndex=2)
        updated=copy.deepcopy(edge);updated['endPosition']=self.after['position2'];updated.update(shape='TWO_RADII',verticalRadius=5.)
        self.owner=dict(id=123,path=[edge],vehicles=[dict(id=456,railProgress=25.,speed=.003)])
        self.newowner=copy.deepcopy(self.owner);self.newowner['path']=[updated]
        for name,old,new in [(self.oldname,self.rail,None),(self.newname,None,self.after),(self.depot,self.owner,self.newowner)]:
            if old is not None:
                for base in ('preserved-native','native-geometry/before'):self.write(base,name,old)
            if new is not None:self.write('native-geometry/after',name,new)
        report=dict(operations=[dict(member=self.oldname,before=True,after=False),dict(member=self.newname,before=False,after=True),dict(member=self.depot,before=True,after=True)],
                    node_moves=[dict(before=[10,0,0],after=[10,1,0])],cached_path_entries=1,
                    rail_geometry=[dict(before_member=self.oldname,after_member=self.newname,length_before=10.,length_after=10.)])
        (self.c/'native-geometry/operations.json').write_text(json.dumps(report))
        (self.c/'manifest.json').write_text(json.dumps(dict(native_geometry_patch='native-geometry/operations.json')))

    def tearDown(self):self.tmp.cleanup()

    def write(self,base,name,value):
        p=self.c/base/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(encode(value)+b'opaque-tail')

    def test_preserves_vehicle_tokens_and_retains_only_new_endpoint(self):
        data,proof=expected(self.c)
        self.assertNotIn(self.oldname,data);self.assertIn(self.newname,data)
        self.assertEqual(proof['cached_path_entries'],1)
        self.assertEqual(proof['vehicles_in_changed_owners_exact'],1)

    def test_rejects_vehicle_progress_change(self):
        self.newowner['vehicles'][0]['railProgress']=0.
        self.write('native-geometry/after',self.depot,self.newowner)
        with self.assertRaisesRegex(ValueError,'vehicle'):expected(self.c)

    def test_rejects_changed_path_distance(self):
        self.newowner['path'][0]['endDistance']=31.
        self.write('native-geometry/after',self.depot,self.newowner)
        with self.assertRaisesRegex(ValueError,'distance'):expected(self.c)

    def test_rejects_omitted_incident_rail(self):
        extra=copy.deepcopy(self.rail);extra['position1']=dict(x=10,y=0,z=0);extra['position2']=dict(x=20,y=0,z=0)
        self.write('preserved-native','projectseele/geofront/rails/00/incident',extra)
        with self.assertRaisesRegex(ValueError,'incident'):expected(self.c)

    def test_rejects_opaque_tail_loss(self):
        (self.c/'native-geometry/after'/self.newname).write_bytes(encode(self.after))
        with self.assertRaisesRegex(ValueError,'opaque'):expected(self.c)

    def station_case(self):
        p=self.c/'native-geometry/operations.json';r=json.loads(p.read_text())
        r.update(migration_kind='cable_station_vertical',station_identity_members=['projectseele/geofront/platforms/00/platform'])
        r['node_moves']=[dict(before=[10,0,0],after=[10,7,0])]
        self.rail.update(transportMode='CABLE_CAR',isPlatform=True)
        self.after.update(transportMode='CABLE_CAR',isPlatform=True);self.after['position2']['y']=7
        self.newowner['path'][0]['endPosition']['y']=7
        for base in ('preserved-native','native-geometry/before'):
            self.write(base,self.oldname,self.rail)
        self.write('native-geometry/after',self.newname,self.after);self.write('native-geometry/after',self.depot,self.newowner)
        self.platform='projectseele/geofront/platforms/00/platform'
        self.oldplatform=dict(id=789,transportMode='CABLE_CAR',name='Original platform',position1=dict(x=0,y=0,z=0),position2=dict(x=10,y=0,z=0),dwellTime=14000)
        self.newplatform=copy.deepcopy(self.oldplatform);self.newplatform['position2']['y']=7
        for base in ('preserved-native','native-geometry/before'):self.write(base,self.platform,self.oldplatform)
        self.write('native-geometry/after',self.platform,self.newplatform)
        r['operations'].append(dict(member=self.platform,before=True,after=True));p.write_text(json.dumps(r))

    def test_explicit_cable_station_lift_retains_identity(self):
        self.station_case();_,proof=expected(self.c)
        self.assertEqual(proof['station_identities_retained'],1)
        self.assertEqual(proof['vehicles_in_changed_owners_exact'],1)

    def test_station_lift_rejects_platform_identity_change(self):
        self.station_case();self.newplatform['id']=790;self.write('native-geometry/after',self.platform,self.newplatform)
        with self.assertRaisesRegex(ValueError,'identity'):expected(self.c)

    def test_station_lift_rejects_omitted_platform(self):
        self.station_case();p=self.c/'native-geometry/operations.json';r=json.loads(p.read_text())
        r['operations']=[x for x in r['operations']if x['member']!=self.platform];r['station_identity_members']=[];p.write_text(json.dumps(r))
        with self.assertRaisesRegex(ValueError,'omitted'):expected(self.c)

    def test_station_lift_rejects_train(self):
        self.station_case();self.rail['transportMode']='TRAIN';self.after['transportMode']='TRAIN'
        for base in ('preserved-native','native-geometry/before'):self.write(base,self.oldname,self.rail)
        self.write('native-geometry/after',self.newname,self.after)
        with self.assertRaisesRegex(ValueError,'another transport mode'):expected(self.c)


if __name__=='__main__':unittest.main()

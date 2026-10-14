"""Contract-only negative tests; synthetic data never qualify native acceptance."""
from pathlib import Path
import copy,gzip,hashlib,json,tempfile,unittest,zipfile
from unittest.mock import patch
from release_scope124_r53 import navigation_pins,validate_current_bindings,SOURCE_REPORTS
from verify_scope124_delivery_r53 import verify_world_members


class DeliveryBindingTests(unittest.TestCase):
    def test_current_binding_rejects_stale_source_or_untested_navigation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);world=root/'world';world.mkdir();pipeline=root/'pipeline';pipeline.mkdir()
            native=root/'native';native.mkdir();fingerprint='f'*64;jar=root/'current.jar';jar.write_bytes(b'synthetic')
            def write(path,data):path.write_text(json.dumps(data),'utf8');return path
            def ref(path):return dict(path=str(path.resolve()),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            graph=gzip.compress(json.dumps(dict(r53_navigation=True,r52_navigation=True,nodes=[[1,2,3]])).encode())
            (world/'nerv_routes_r24.json.gz').write_bytes(graph)
            (world/'nearest_lift_paths_r44.json.gz').write_bytes(gzip.compress(json.dumps(dict(nodes=[[1,2,3]],graph_sha256=hashlib.sha256(graph).hexdigest())).encode()))
            pins=navigation_pins(world);jar_sha=ref(jar)['sha256']
            build=write(root/'BUILD_RECEIPT.json',dict(jar=str(jar),sha256=jar_sha))
            bundle={key:dict(file=key+'.json',sha256='a'*64) for key in ('directory','mechanical_owner','air_transport','personnel_lifts','upright_guideway')}
            write(world/'ROOT_ASSEMBLY_BUNDLE.json',bundle);candidate=write(pipeline/'bundle.json',bundle)
            reports={name:ref(write(pipeline/name,dict(directory_fingerprint=fingerprint,production_parser_valid=True))) for name in SOURCE_REPORTS}
            pipeline_receipt=write(pipeline/'CURRENT_BUNDLE_PIPELINE_RECEIPT.json',dict(world=str(world),bundle=ref(candidate),
                source_inputs=dict(selected_jar=ref(jar),selected_build_receipt=ref(build)),reports={name:r['sha256'] for name,r in reports.items()}))
            nav_receipt=write(root/'navigation.json',dict(world=str(world),current_round=True,installed=True,files=pins,jar_sha256=jar_sha,directory_fingerprint=fingerprint))
            native_inputs=write(native/'INPUTS.json',dict(world_metadata_sha256=pins));native_result=write(native/'RESULT.json',dict(synthetic_not_native=True))
            report=dict(jar_sha256=jar_sha,directory_fingerprint=fingerprint,bindings=dict(schema='projectseele.r53.current-release-bindings.v1',
                source_pipeline=ref(pipeline_receipt),source_reports=reports,navigation=dict(files=pins,receipt=ref(nav_receipt)),
                native_installation=dict(inputs=ref(native_inputs),result=ref(native_result))),
                checks=dict(source_build=dict(status='PASS',directory_fingerprint=fingerprint,navigation_sha256=pins,evidence=[ref(build)])))
            context=dict(root_world_authority=dict(world=str(world)));metadata=dict(directory_fingerprint=fingerprint)
            with patch('release_scope124_r53.validate_context',return_value=context):
                self.assertEqual(validate_current_bindings(report,context,build,native,metadata),report['bindings'])
                changed=copy.deepcopy(report);changed['bindings']['source_reports']['CURRENT_GUIDEWAY_REPORT.json']['sha256']='0'*64
                with self.assertRaises(ValueError):validate_current_bindings(changed,context,build,native,metadata)
                changed=copy.deepcopy(report);changed['checks']['source_build']['navigation_sha256']={}
                with self.assertRaises(ValueError):validate_current_bindings(changed,context,build,native,metadata)
                write(native_inputs,dict(world_metadata_sha256={}));changed=copy.deepcopy(report)
                changed['bindings']['native_installation']['inputs']=ref(native_inputs)
                with self.assertRaises(ValueError):validate_current_bindings(changed,context,build,native,metadata)

    def test_current_navigation_and_stale_nearest_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            world=Path(folder);graph=gzip.compress(json.dumps(dict(r53_navigation=True,r52_navigation=True,nodes=[[1,2,3]])).encode())
            (world/'nerv_routes_r24.json.gz').write_bytes(graph)
            nearest=dict(nodes=[[1,2,3]],graph_sha256=hashlib.sha256(graph).hexdigest())
            cache=world/'nearest_lift_paths_r44.json.gz';cache.write_bytes(gzip.compress(json.dumps(nearest).encode()))
            self.assertEqual(set(navigation_pins(world)),{'nerv_routes_r24.json.gz','nearest_lift_paths_r44.json.gz'})
            nearest['graph_sha256']='0'*64;cache.write_bytes(gzip.compress(json.dumps(nearest).encode()))
            with self.assertRaises(ValueError):navigation_pins(world)
            nearest['graph_sha256']=hashlib.sha256(graph).hexdigest();nearest['nodes']=[]
            cache.write_bytes(gzip.compress(json.dumps(nearest).encode()))
            with self.assertRaises(ValueError):navigation_pins(world)

    def test_actual_world_wrong_byte_or_extra_member_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'actual.zip';expected={'level.dat':hashlib.sha256(b'current').hexdigest()}
            with zipfile.ZipFile(file,'w') as archive:archive.writestr('SEELE_R52_WORLD/level.dat',b'current')
            with zipfile.ZipFile(file) as archive:self.assertEqual(verify_world_members(archive,'SEELE_R52_WORLD/',expected),expected)
            with zipfile.ZipFile(file,'w') as archive:archive.writestr('SEELE_R52_WORLD/level.dat',b'old')
            with zipfile.ZipFile(file) as archive:
                with self.assertRaises(ValueError):verify_world_members(archive,'SEELE_R52_WORLD/',expected)
            with zipfile.ZipFile(file,'w') as archive:
                archive.writestr('SEELE_R52_WORLD/level.dat',b'current');archive.writestr('SEELE_R52_WORLD/old_marker',b'old')
            with zipfile.ZipFile(file) as archive:
                with self.assertRaises(ValueError):verify_world_members(archive,'SEELE_R52_WORLD/',expected)


if __name__=='__main__':unittest.main()

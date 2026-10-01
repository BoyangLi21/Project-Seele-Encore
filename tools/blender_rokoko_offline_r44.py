"""Load the pinned, free local retarget operator without receiver/login/update modules.

This is an isolated authoring adapter, not an installed cloud connection or a
claim of improved animation quality. Upstream code retains its LGPL licence.
"""
import ast, hashlib, importlib, json, sys, types
from pathlib import Path
import bpy

ROOT=Path('D:/eva')
UPSTREAM=ROOT/'.Codex/external/rokoko_v1_4_3_b031e5a0/Rokoko-rokoko-studio-live-blender-b031e5a'
OUT=ROOT/'artifacts/rebuild_r44/tools/rokoko_offline'
PACKAGE='seele_rokoko_offline'


def package(name,path):
    module=types.ModuleType(name);module.__path__=[str(path)];module.__package__=name
    sys.modules[name]=module
    return module


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    receipt={'blender':bpy.app.version_string,'upstream':str(UPSTREAM),'upstream_version':'1.4.3',
             'full_plugin_executed':False,'account_connected':False,'asset_uploaded':False,
             'animation_quality_passed':False,'registered':False}
    try:
        for suffix in ('','core','operators','panels'):
            package(PACKAGE+('.'+suffix if suffix else ''),UPSTREAM/suffix)
        # The upstream retarget operator imports this name, then immediately
        # replaces it with core.detection_manager; its receiver/UI is not used.
        sys.modules[PACKAGE+'.operators.detector']=types.ModuleType(PACKAGE+'.operators.detector')
        panel=types.ModuleType(PACKAGE+'.panels.retargeting');panel.__package__=PACKAGE+'.panels'
        panel.__dict__.update(bpy=bpy,PropertyGroup=bpy.types.PropertyGroup,
                              StringProperty=bpy.props.StringProperty,BoolProperty=bpy.props.BoolProperty)
        source=UPSTREAM/'panels/retargeting.py'
        definition=next(n for n in ast.parse(source.read_text('utf8')).body if isinstance(n,ast.ClassDef) and n.name=='BoneListItem')
        exec(compile(ast.Module(body=[definition],type_ignores=[]),str(source),'exec'),panel.__dict__)
        sys.modules[panel.__name__]=panel
        bpy.utils.register_class(panel.BoneListItem)
        scene=bpy.types.Scene
        scene.rsl_retargeting_armature_source=bpy.props.PointerProperty(type=bpy.types.Object)
        scene.rsl_retargeting_armature_target=bpy.props.PointerProperty(type=bpy.types.Object)
        scene.rsl_retargeting_auto_scaling=bpy.props.BoolProperty(default=True)
        scene.rsl_retargeting_use_pose=bpy.props.EnumProperty(items=[('REST','Rest',''),('CURRENT','Current','')],default='REST')
        scene.rsl_retargeting_bone_list=bpy.props.CollectionProperty(type=panel.BoneListItem)
        scene.rsl_retargeting_bone_list_index=bpy.props.IntProperty(default=0)
        detector=importlib.import_module(PACKAGE+'.core.detection_manager');detector.load_detection_lists()
        operator=importlib.import_module(PACKAGE+'.operators.retargeting')
        for cls in (operator.BuildBoneList,operator.RetargetAnimation):bpy.utils.register_class(cls)
        assert not any(n.startswith(PACKAGE) and any(x in n for x in ('login','receiver','updater','library_manager')) for n in sys.modules)
        receipt.update(registered=True,operator_ids=[operator.BuildBoneList.bl_idname,operator.RetargetAnimation.bl_idname],
                       operator_sha256=hashlib.sha256((UPSTREAM/'operators/retargeting.py').read_bytes()).hexdigest(),
                       next_gate='Calibrated source/target rest-pose comparison, real retarget/export/reload and visual review; environment registration is not asset acceptance')
        print('R44 offline Rokoko retarget operator registered; no login/receiver/update code imported',flush=True)
    except Exception as error:
        receipt['error']=repr(error)
        raise
    finally:
        (OUT/'registration.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')


if __name__=='__main__':main()

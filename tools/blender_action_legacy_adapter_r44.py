"""Process-local Action.fcurves compatibility for pinned local retarget only.

Blender 5.1 channel bags replace the legacy action collection. This preserves
upstream retarget math and source files; multiple slots fail explicitly.
"""
import bpy


class CurveCollection:
    def __init__(self, curves): self.curves = curves
    def __iter__(self): return iter(self.curves)
    def __len__(self): return len(self.curves)
    def __getitem__(self, key): return self.curves[key]
    def __getattr__(self, name): return getattr(self.curves, name)
    def new(self, data_path, index=0, action_group=''):
        return self.curves.new(data_path, index=index, group_name=action_group)


def curves(action):
    if len(action.slots) > 1:
        raise RuntimeError('Offline legacy adapter requires an explicit single action slot')
    slot = action.slots[0] if action.slots else action.slots.new(id_type='OBJECT', name='R44 offline retarget')
    if not action.layers: action.layers.new('R44 offline retarget')
    layer = action.layers[0]
    if not layer.strips: layer.strips.new(type='KEYFRAME')
    bag = layer.strips[0].channelbag(slot, ensure=True)
    return CurveCollection(bag.fcurves)


def install():
    if hasattr(bpy.types.Action, 'fcurves'): return 'Native legacy collection already available'
    bpy.types.Action.fcurves = property(curves)
    if not hasattr(bpy.types.Bone, 'select'):
        def selected(bone):
            return any(obj.type=='ARMATURE' and obj.data==bone.id_data and obj.pose.bones[bone.name].select for obj in bpy.data.objects)
        def select(bone,value):
            owners=[obj for obj in bpy.data.objects if obj.type=='ARMATURE' and obj.data==bone.id_data]
            if not owners:raise RuntimeError('No actual pose owner for legacy bone selection')
            for obj in owners:obj.pose.bones[bone.name].select=value
        bpy.types.Bone.select=property(selected,select)
    return 'Process-local single-slot channelbag; action_group→group_name; Bone.select→owning PoseBone.select. Upstream files and retarget math unchanged'

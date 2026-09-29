"""Surface vocabulary; callers still supply an explicitly identified facility."""

GALLERY_FLOORS={'minecraft:gray_concrete','minecraft:polished_deepslate',
    'projectseele:nerv_floor_panel','projectseele:nerv_structural_panel'}

def gallery_bearing(state):
    if not state:return False
    name=state.partition('[')[0]
    return name in GALLERY_FLOORS or name=='mtr:escalator_step' and 'orientation=flat' in state

"""The commissioned native girder state at each original3m bearing layer."""


def running_state(y,z):
    segment={-376:'base',-375:'web',-374:'top'}[y]
    joint=str((z+266)%6==0).lower()
    return f'projectseele:nerv_crane_girder_r44[joint={joint},segment={segment}]'

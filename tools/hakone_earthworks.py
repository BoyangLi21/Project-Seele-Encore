"""Offline, coupled grading of roads, building plots and their surroundings.

The slope envelopes are separable L1 distance transforms. Their cost depends
on map area, not on the height difference or a fixed feather radius. A 30-block
cut therefore gets a real hillside transition instead of a four-block shoulder
followed by a cliff. No world, entity or runtime simulation is accessed here.
"""
import numpy as np


def min_slope_envelope(values, slope):
    result = np.asarray(values, np.float32).copy()
    for axis in range(result.ndim):
        view = np.moveaxis(result, axis, -1)
        ramp = np.arange(view.shape[-1], dtype=np.float32) * slope
        forward = np.minimum.accumulate(view - ramp, axis=-1) + ramp
        backward = np.minimum.accumulate((view + ramp)[..., ::-1], axis=-1)[..., ::-1] - ramp
        view[...] = np.minimum(forward, backward)
    return result


def grade_ground(surveyed, anchors, anchor_y, slope=1.0):
    """Fit soil to coherent fixed surfaces, leaving distant relief unchanged.

    Contradictory anchors are returned for design correction, never silently
    averaged or called a passed grade. Bridges/tunnels must not be soil anchors.
    """
    surveyed = np.asarray(surveyed, np.float32)
    anchors = np.asarray(anchors, bool)
    heights = np.asarray(anchor_y, np.float32)
    if surveyed.shape != anchors.shape or heights.shape != surveyed.shape:
        raise ValueError('Grading arrays must share one coordinate frame')
    if not np.isfinite(surveyed).all() or slope <= 0:
        raise ValueError('Finite terrain and positive slope required')
    upper = min_slope_envelope(np.where(anchors, heights, np.inf), slope)
    lower = -min_slope_envelope(np.where(anchors, -heights, np.inf), slope)
    conflict = lower > upper + .001
    ground = np.clip(surveyed, lower, upper)
    ground[anchors] = heights[anchors]
    return np.rint(ground).astype(np.int16), conflict


def grade_development(heights, developed, plots, fixed=None, slope=1.0, plot_quantum=1):
    """Solve street junctions and COMPLETE flat plots as one elevation problem.

    Each plot is a pair of slices. Grading roads first then stamping independent
    flat plots can reintroduce a cliff on the far side of an otherwise reachable
    entrance. A fixed surface (for example a lake) constrains the nearby grade.
    """
    target=np.asarray(heights,np.float32).copy()
    fixed=np.zeros(target.shape,bool) if fixed is None else np.asarray(fixed,bool)
    fixed_values=target[fixed].copy()
    upper=min_slope_envelope(np.where(fixed,target,np.inf),slope)
    lower=-min_slope_envelope(np.where(fixed,-target,np.inf),slope)
    # A level parcel must respect the highest lower bound anywhere under it,
    # and that bound also applies to neighbouring streets. Propagate it before
    # lowering the flexible grades, rather than snapping a plot back up later.
    for iteration in range(128):
        changed=False
        for area in plots:
            height=float(np.ceil(lower[area].max()/plot_quantum)*plot_quantum)
            if np.any(lower[area]!=height):lower[area]=height;changed=True
        if not changed:break
        lower=-min_slope_envelope(-lower,slope)
    else:raise ValueError('Fixed terrain/parcel constraints did not converge')
    if np.any(lower>upper+.001):
        raise ValueError('Fixed surfaces cannot share the requested terrain slope')
    mask=developed|fixed
    for iteration in range(128):
        old=target[developed].copy()
        fitted=min_slope_envelope(np.where(mask,np.maximum(target,lower),np.inf),slope)
        target[developed&~fixed]=fitted[developed&~fixed]
        for area in plots:
            target[area]=max(float(np.floor(target[area].min()/plot_quantum)*plot_quantum),float(lower[area].max()))
        if not np.array_equal(target[fixed],fixed_values):
            raise ValueError('A level plot overlaps incompatible fixed surfaces')
        if np.array_equal(old,target[developed]):break
    else:raise ValueError('Coupled street/plot grading did not converge')
    return np.rint(target).astype(np.int16)


def road_blocks(grade2):
    """Block position and slab flag for a monotonically rising half-step road.

    Even 2Y is a full block at Y; odd 2Y+1 is a bottom slab at Y+1.
    Placing that slab at Y instead made each alternate step drop half a block
    and the following step jump one and a half blocks.
    """
    grade2=np.asarray(grade2)
    return (grade2+1)//2,grade2%2==1


def plot_anchors(bounds, buildings, margin=3):
    x0, z0, x1, z1 = map(int, bounds)
    mask = np.zeros((z1-z0+1, x1-x0+1), bool)
    heights = np.zeros(mask.shape, np.int16)
    for row in buildings:
        site = row.get('site', row)
        x, z = site['centre']; hx, hz = site['half']
        if site['rotation'] % 2:
            hx, hz = hz, hx
        area = np.s_[max(0,z-hz-z0-margin):min(mask.shape[0],z+hz-z0+margin+1),
                     max(0,x-hx-x0-margin):min(mask.shape[1],x+hx-x0+margin+1)]
        if np.any(mask[area] & (heights[area] != site['floor'])):
            raise ValueError('Overlapping plots require a shared terrace design')
        mask[area] = True; heights[area] = site['floor']
    return mask, heights


def edge_defects(ground, developed, threshold=3):
    """Measure the entire outer interface, not just a walkable centreline."""
    defects = []
    for axis in (0, 1):
        a = [slice(None), slice(None)]; b = a.copy()
        a[axis] = slice(1,None); b[axis] = slice(None,-1)
        a, b = tuple(a), tuple(b)
        diff = np.abs(ground[a].astype(np.int32)-ground[b])
        bad = (developed[a] ^ developed[b]) & (diff > threshold)
        for z, x in np.argwhere(bad):
            defects.append([int(x), int(z), axis, int(diff[z,x])])
    return defects

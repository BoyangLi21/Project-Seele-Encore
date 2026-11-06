"""Explicit planar rigid-car geometry shared by station planners.

This is a plan-view reservation, not a vertical collision or live boarding
check. Margins and end handling are explicit so station-specific budgets do
not silently change while common code is extracted.
"""
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union


def point(line, distance, extend=True):
    if not np.isfinite(distance) or line.is_empty or line.length <= 0:
        raise ValueError('Finite distance and non-empty centreline required')
    if extend and (distance < 0 or distance > line.length):
        coordinates = np.asarray(line.coords, dtype=float)
        if distance < 0:
            origin = coordinates[0]
            directions = coordinates[1:] - origin
            offset = distance
        else:
            origin = coordinates[-1]
            directions = origin - coordinates[-2::-1]
            offset = distance - line.length
        lengths = np.linalg.norm(directions, axis=1)
        valid = np.flatnonzero(lengths > 1e-12)
        if not len(valid):
            raise ValueError('Centreline has no nonzero tangent')
        i = valid[0]
        return origin + directions[i] * offset / lengths[i]
    return np.asarray(line.interpolate(max(0, min(line.length, distance))).coords[0])


def pose(line, distance, wheelbase=9, extend=True):
    if wheelbase <= 0:
        raise ValueError('Positive wheelbase required')
    centre = point(line, max(0, min(line.length, distance)), extend)
    direction = point(line, distance + wheelbase/2, extend) - point(line, distance - wheelbase/2, extend)
    norm = np.linalg.norm(direction)
    if norm <= 1e-12:
        raise ValueError('Vehicle tangent is undefined')
    direction /= norm
    return centre, direction, np.array([-direction[1], direction[0]])


def rectangle(centre, tangent, normal, start, end, left, right):
    return Polygon([centre+tangent*start+normal*left, centre+tangent*end+normal*left,
                    centre+tangent*end+normal*right, centre+tangent*start+normal*right])


def envelope(line, *, length, width, wheelbase=9, lateral_margin=0,
             longitudinal_margin=0, spacing=.25, extend=True):
    if min(length, width, wheelbase, spacing) <= 0 or min(lateral_margin, longitudinal_margin) < 0:
        raise ValueError('Invalid vehicle size or clearance budget')
    if spacing > 1:
        raise ValueError('Station reservation sampling is too coarse')
    a, b = length/2+longitudinal_margin, width/2+lateral_margin
    return unary_union([rectangle(*pose(line, s, wheelbase, extend), -a, a, -b, b)
                        for s in np.arange(0, line.length+spacing/2, spacing)])

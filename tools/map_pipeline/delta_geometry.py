"""Explicit vertical coordinates for existing surface and deep section deltas."""
import numpy as np


def vertical_extent(data):
    present = {'y_origin', 'height'}.intersection(data.files)
    if not present:
        return -128, 448
    if present != {'y_origin', 'height'}:
        raise ValueError('Delta requires both y_origin and height')
    values = []
    for key in ('y_origin', 'height'):
        value = data[key]
        if value.shape != () or value.dtype.kind not in 'iu':
            raise ValueError('Delta vertical extent must contain integer scalars')
        values.append(int(value))
    bottom, height = values
    if bottom % 16 or height <= 0 or height % 16 or bottom < -1344 or bottom + height > 320:
        raise ValueError('Delta vertical extent exceeds the actual dimension')
    return bottom, height


def checked_indices(data):
    bottom, height = vertical_extent(data)
    raw = data['indices']
    if raw.ndim != 1 or raw.dtype.kind not in 'iu':
        raise ValueError('Delta indices must be an integer vector')
    indices = raw.astype(np.int64)
    if np.any((indices < 0) | (indices >= height * 256)):
        raise ValueError('Map delta exceeds its declared vertical extent')
    return bottom, height, indices

"""Joint world transforms baked by blender/bake_fbx.py, with the Bvh accessor API."""

import numpy as np


class Baked:
    def __init__(self, path):
        d = np.load(path)
        self.names = [str(x) for x in d["names"]]
        self.index = {n: i for i, n in enumerate(self.names)}
        self._pos = d["pos"]
        self._rot = d["rot"]
        self.frames = self._pos.shape[0]
        self._rate = float(d["rate"])

    def pos(self, name):
        return self._pos[:, self.index[name]]

    def rot(self, name):
        return self._rot[:, self.index[name]]

    @property
    def rate(self):
        return self._rate

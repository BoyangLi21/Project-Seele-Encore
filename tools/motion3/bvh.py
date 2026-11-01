"""Minimal BVH reader with numpy forward kinematics.

Joint local transform = T(translation) R, where translation is the position
channels when present (Bandai/Maya style) and the OFFSET otherwise, and R is
the product of the rotation channels in the order they are listed.
"""

import numpy as np


class Joint:
    __slots__ = ("name", "parent", "offset", "channels", "children", "end")

    def __init__(self, name, parent):
        self.name = name
        self.parent = parent
        self.offset = np.zeros(3)
        self.channels = []
        self.children = []
        self.end = None


def _axis_matrix(axis, deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    n = a.shape[0]
    m = np.zeros((n, 3, 3))
    if axis == "X":
        m[:, 0, 0] = 1; m[:, 1, 1] = c; m[:, 1, 2] = -s; m[:, 2, 1] = s; m[:, 2, 2] = c
    elif axis == "Y":
        m[:, 1, 1] = 1; m[:, 0, 0] = c; m[:, 0, 2] = s; m[:, 2, 0] = -s; m[:, 2, 2] = c
    else:
        m[:, 2, 2] = 1; m[:, 0, 0] = c; m[:, 0, 1] = -s; m[:, 1, 0] = s; m[:, 1, 1] = c
    return m


class Bvh:
    def __init__(self, path):
        self.joints = []
        self.by_name = {}
        with open(path, encoding="utf-8", errors="replace") as f:
            tokens = f.read().split()
        i = 0
        stack = []
        current = None
        while i < len(tokens):
            t = tokens[i]
            if t in ("ROOT", "JOINT"):
                current = Joint(tokens[i + 1], stack[-1] if stack else None)
                if current.parent is not None:
                    current.parent.children.append(current)
                self.joints.append(current)
                self.by_name[current.name] = current
                i += 2
            elif t == "End":
                end_offset = None
                # End Site { OFFSET x y z }
                j = i
                while tokens[j] != "OFFSET":
                    j += 1
                end_offset = np.array([float(tokens[j + 1]), float(tokens[j + 2]), float(tokens[j + 3])])
                stack[-1].end = end_offset
                while tokens[j] != "}":
                    j += 1
                i = j + 1
            elif t == "{":
                stack.append(current)
                i += 1
            elif t == "}":
                stack.pop()
                i += 1
            elif t == "OFFSET":
                current.offset = np.array([float(tokens[i + 1]), float(tokens[i + 2]), float(tokens[i + 3])])
                i += 4
            elif t == "CHANNELS":
                n = int(tokens[i + 1])
                current.channels = tokens[i + 2:i + 2 + n]
                i += 2 + n
            elif t == "MOTION":
                i += 1
                break
            else:
                i += 1
        # Frames: N  Frame Time: dt
        while tokens[i] != "Frames:":
            i += 1
        self.frames = int(tokens[i + 1])
        i += 2
        while tokens[i] != "Time:":
            i += 1
        self.frame_time = float(tokens[i + 1])
        i += 2
        nch = sum(len(j.channels) for j in self.joints)
        data = np.array(tokens[i:i + self.frames * nch], dtype=np.float64)
        self.data = data.reshape(self.frames, nch)
        self._fk()

    def _fk(self):
        n = self.frames
        col = 0
        self.world_rot = {}
        self.world_pos = {}
        for j in self.joints:
            trans = np.tile(j.offset, (n, 1))
            rot = np.tile(np.eye(3), (n, 1, 1))
            pos_ch = {}
            for ch in j.channels:
                v = self.data[:, col]
                col += 1
                if ch.endswith("position"):
                    pos_ch[ch[0]] = v
                else:
                    rot = rot @ _axis_matrix(ch[0], v)
            if pos_ch:
                trans = np.stack([pos_ch.get("X", trans[:, 0]), pos_ch.get("Y", trans[:, 1]),
                                  pos_ch.get("Z", trans[:, 2])], axis=1)
            if j.parent is None:
                self.world_rot[j.name] = rot
                self.world_pos[j.name] = trans
            else:
                pr = self.world_rot[j.parent.name]
                pp = self.world_pos[j.parent.name]
                self.world_pos[j.name] = pp + np.einsum("nij,nj->ni", pr, trans)
                self.world_rot[j.name] = pr @ rot

    def pos(self, name):
        return self.world_pos[name]

    def rot(self, name):
        return self.world_rot[name]

    @property
    def rate(self):
        return 1.0 / self.frame_time

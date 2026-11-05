"""Offline rig, skinning and preview renderer for Project SEELE cinematics.

Reproduces GeckoLib 4's bone maths in its *baked* model space, which is what
the game draws:
  * geo pivots are baked as (-x, y, z) px, rotations as (-rx, -ry, +rz) deg;
  * a bone's local matrix is T(pos) T(pivot) Rz Ry Rx T(-pivot), where pos is
    GeckoLib's position field applied as (-posX, posY, posZ) / 16;
  * private meshes store file-space px, baked as (-(x+px), y+py, z+pz) / 16.
Model forward is -Z.  An entity with Minecraft yaw `yaw` is drawn with
T(entity) Ry(180 - yaw) S(scale).  Quaternions are (w, x, y, z) numpy arrays.

Clip quaternions (first_battle json) are file-space: baked = (w, -x, -y, z).
"""
import json
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont


# ----------------------------------------------------------------- quaternions
def qnorm(q):
    q = np.asarray(q, float)
    return q / np.linalg.norm(q)


def qmul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return np.array([aw * bw - ax * bx - ay * by - az * bz,
                     aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw])


def qconj(q):
    return np.array([q[0], -q[1], -q[2], -q[3]])


def qaxis(axis, angle):
    axis = np.asarray(axis, float)
    n = np.linalg.norm(axis)
    if n < 1e-12 or abs(angle) < 1e-12:
        return np.array([1.0, 0, 0, 0])
    s = math.sin(angle / 2) / n
    return np.array([math.cos(angle / 2), axis[0] * s, axis[1] * s, axis[2] * s])


def qx(a):
    return qaxis((1, 0, 0), a)


def qy(a):
    return qaxis((0, 1, 0), a)


def qz(a):
    return qaxis((0, 0, 1), a)


def qzyx(rz, ry, rx):
    return qmul(qmul(qz(rz), qy(ry)), qx(rx))


def qmat(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                     [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                     [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def matq(m):
    m = np.asarray(m, float)
    t = m[0, 0] + m[1, 1] + m[2, 2]
    if t > 0:
        s = math.sqrt(t + 1) * 2
        q = [0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s]
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        q = [(m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s]
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        q = [(m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s]
    else:
        s = math.sqrt(1 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        q = [(m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s]
    return qnorm(q)


def qslerp(a, b, t):
    a = qnorm(a)
    b = qnorm(b)
    d = float(np.dot(a, b))
    if d < 0:
        b = -b
        d = -d
    if d > 0.9995:
        return qnorm(a + (b - a) * t)
    th = math.acos(min(1.0, d))
    s = math.sin(th)
    return (math.sin((1 - t) * th) * a + math.sin(t * th) * b) / s


def qrot(q, v):
    return qmat(q) @ np.asarray(v, float)


def q_between(a, b):
    """Shortest-arc rotation taking direction a onto direction b."""
    a = np.asarray(a, float) / np.linalg.norm(a)
    b = np.asarray(b, float) / np.linalg.norm(b)
    c = np.cross(a, b)
    d = float(np.dot(a, b))
    if d < -0.999999:
        axis = np.cross(a, (1, 0, 0))
        if np.linalg.norm(axis) < 1e-6:
            axis = np.cross(a, (0, 1, 0))
        return qaxis(axis, math.pi)
    return qnorm([1 + d, c[0], c[1], c[2]])


def qangle(q):
    return 2 * math.acos(min(1.0, abs(float(q[0]))))


def clip_to_baked(q):
    """first_battle json quaternion (file space) -> baked GeckoLib quaternion."""
    return np.array([q[0], -q[1], -q[2], q[3]], float)


baked_to_clip = clip_to_baked  # the basis change is an involution


# ------------------------------------------------------------------ matrices
def translate(t):
    m = np.eye(4)
    m[:3, 3] = t
    return m


def rot4(q):
    m = np.eye(4)
    m[:3, :3] = qmat(q)
    return m


def entity_matrix(position, yaw_degrees, scale):
    """World placement of an entity model: T(pos) Ry(180 - yaw) S(scale)."""
    m = translate(position) @ rot4(qy(math.radians(180 - yaw_degrees)))
    m[:3, :3] *= scale
    return m


# ----------------------------------------------------------------------- rig
class Rig:
    def __init__(self, geo_path):
        geo = json.load(open(geo_path, encoding='utf8'))['minecraft:geometry'][0]
        self.parent, self.pivot, self.rest = {}, {}, {}
        bones = geo['bones']
        for b in bones:
            n = b['name']
            self.parent[n] = b.get('parent')
            p = b.get('pivot', [0, 0, 0])
            self.pivot[n] = np.array([-p[0], p[1], p[2]], float) / 16
            r = b.get('rotation', [0, 0, 0])
            self.rest[n] = qzyx(math.radians(r[2]), math.radians(-r[1]), math.radians(-r[0]))
        self.order, seen = [], set()

        def visit(n):
            if n in seen:
                return
            if self.parent[n]:
                visit(self.parent[n])
            seen.add(n)
            self.order.append(n)
        for b in bones:
            visit(b['name'])
        self.children = {n: [c for c in self.order if self.parent[c] == n] for n in self.order}

    def local(self, name, q=None, pos=None):
        q = self.rest[name] if q is None else q
        r = qmat(q)
        pv = self.pivot[name]
        m = np.eye(4)
        m[:3, :3] = r
        m[:3, 3] = pv - r @ pv + (0 if pos is None else np.asarray(pos, float))
        return m

    def fk(self, rot, pos=None, root=None):
        """Model-space (or root-premultiplied) matrices for every bone."""
        pos = pos or {}
        out = {}
        for n in self.order:
            p = self.parent[n]
            parent = out[p] if p else (np.eye(4) if root is None else root)
            out[n] = parent @ self.local(n, rot.get(n), pos.get(n))
        return out

    @staticmethod
    def hinge_offset(q, pivot, centre):
        """GeckoLib position (baked, blocks) that makes a bone turn about centre."""
        d = np.asarray(centre, float) - pivot
        return d - qmat(q) @ d


# --------------------------------------------------------------------- meshes
def _texture(path):
    return np.asarray(Image.open(path).convert('RGB'), float) / 255.0


def _sample(tex, uv):
    h, w = tex.shape[:2]
    x = np.clip((uv[:, 0] * w).astype(int), 0, w - 1)
    y = np.clip((uv[:, 1] * h).astype(int), 0, h - 1)
    return tex[y, x]


class RigidMesh:
    """Unit-01 style: each part follows one bone, plus the runtime's seam welding.

    Mirrors LocalTriangleMeshLayer.jointSkins: vertices shared by the two parts
    meeting at an elbow/ankle/wrist/hip/waist get half weight on each bone
    (snapped to the shared rest point), fading to 0 within 6 px of the seam,
    and the head's neck sleeve blends toward torso_upper.  LBS here, DQS in game.
    """

    JOINTS = [('torso_lower', 'torso_upper')] + [(u.replace('%s', s), l.replace('%s', s)) for s in 'lr' for u, l in
                                                 (('torso_lower', 'leg_%s'), ('arm_%s', 'forearm_%s'),
                                                  ('shin_%s', 'foot_%s'), ('forearm_%s', 'hand_%s'))]

    def __init__(self, mesh_path, texture_path, rig, skip=('finger_',), weld=True):
        m = json.load(open(mesh_path, encoding='utf8'))
        stride = m['stride']
        tex = _texture(texture_path)
        self.parts = []
        raw = {}
        for name, part in m['parts'].items():
            if name.startswith(skip) or name not in rig.pivot:
                continue
            v = np.array(part['vertices'], float).reshape(-1, stride)
            file_px = v[:, :3] + np.array(part['pivot'], float)
            xyz = file_px.copy()
            xyz[:, 0] *= -1
            xyz /= 16
            col = _sample(tex, v[:, 3:5].reshape(-1, 3, 2).mean(1))
            if 'tint' in part:
                col = col * np.array(part['tint'], float)[None, :]
            raw[name] = (xyz, file_px, col, np.array(part['pivot'], float))
        self.skin = {}
        if weld:
            for upper, lower in self.JOINTS:
                if upper not in raw or lower not in raw:
                    continue
                a, b = raw[upper][1], raw[lower][1]
                d = np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)
                close = d < 0.002
                ia, ib = np.nonzero(close)
                if len(ia) < 3:
                    continue
                seam = (a[ia] + b[ib]) / 2
                for name, other in ((upper, lower), (lower, upper)):
                    pts = raw[name][1]
                    dd = np.linalg.norm(pts[:, None, :] - seam[None, :, :], axis=2)
                    k = dd.argmin(1)
                    dist = dd[np.arange(len(pts)), k]
                    t = np.clip(1 - dist / 6.0, 0, 1)
                    w = 0.5 * t * t * (3 - 2 * t)
                    rest = raw[name][0].copy()
                    on = dist < 0.002
                    w[on] = 0.5
                    snap = seam[k[on]].copy()
                    snap[:, 0] *= -1
                    rest[on] = snap / 16
                    self.skin.setdefault(name, []).append((other, w, rest))
            if 'head' in raw and 'torso_upper' in raw:
                fp, pv = raw['head'][1], raw['head'][3]
                blend = np.clip((pv[1] + 1.5 - fp[:, 1]) / 7.0, 0, 1)
                blend[(fp[:, 1] > pv[1] - 3) & (fp[:, 2] < -6)] = 0
                self.skin.setdefault('head', []).append(('torso_upper', blend * blend * (3 - 2 * blend), raw['head'][0].copy()))
        for name, (xyz, _, col, _) in raw.items():
            self.parts.append((name, xyz.reshape(-1, 3, 3), col))
        self.rest = {name: raw[name][0] for name in raw}

    def triangles(self, mats, world):
        out_t, out_c = [], []
        for bone, tris, col in self.parts:
            m = world @ mats[bone]
            if bone in self.skin:
                own = np.ones(len(self.rest[bone]))
                acc = np.zeros((len(own), 3))
                for other, w, rest in self.skin[bone]:
                    take = np.minimum(own, w)
                    own -= take
                    mo = world @ mats[other]
                    acc += take[:, None] * (rest @ mo[:3, :3].T + mo[:3, 3])
                base = self.skin[bone][0][2]
                acc += own[:, None] * (base @ m[:3, :3].T + m[:3, 3])
                t = acc.reshape(-1, 3, 3)
            else:
                t = tris @ m[:3, :3].T + m[:3, 3]
            out_t.append(t)
            out_c.append(col)
        return np.concatenate(out_t), np.concatenate(out_c)


class SkinnedMesh:
    """weighted_angel_r10: one part, four influences per vertex (LBS preview)."""

    def __init__(self, mesh_path, texture_path, rig):
        m = json.load(open(mesh_path, encoding='utf8'))
        stride = m['stride']
        part = m['parts']['root']
        v = np.array(part['vertices'], float).reshape(-1, stride)
        xyz = v[:, :3] + np.array(part['pivot'], float)
        xyz[:, 0] *= -1
        xyz /= 16
        self.rest = np.c_[xyz, np.ones(len(xyz))]
        skin = m['skin']
        self.bones = skin['bones']
        self.idx = np.array(skin['indices'], int).reshape(-1, 4)
        self.w = np.array(skin['weights'], float).reshape(-1, 4)
        rest_mats = rig.fk({})
        self.rest_inv = np.stack([np.linalg.inv(rest_mats[b]) for b in self.bones])
        self.col = _sample(_texture(texture_path), v[:, 3:5].reshape(-1, 3, 2).mean(1))

    def vertices(self, mats, world):
        skin = np.stack([world @ mats[b] for b in self.bones]) @ self.rest_inv
        out = np.zeros((len(self.rest), 3))
        for k in range(4):
            s = skin[self.idx[:, k]]
            out += self.w[:, k:k + 1] * np.einsum('vij,vj->vi', s[:, :3, :], self.rest)
        return out

    def triangles(self, mats, world):
        return self.vertices(mats, world).reshape(-1, 3, 3), self.col


# ------------------------------------------------------------------- renderer
class Camera:
    def __init__(self, eye, target, fov=50.0, size=(640, 400), up=(0, 1, 0)):
        self.eye = np.asarray(eye, float)
        self.target = np.asarray(target, float)
        self.fov = fov
        self.size = size
        f = self.target - self.eye
        f /= np.linalg.norm(f)
        r = np.cross(f, up)
        r /= np.linalg.norm(r)
        u = np.cross(r, f)
        self.basis = np.stack([r, u, f])

    def to_camera(self, p):
        return (np.asarray(p, float) - self.eye) @ self.basis.T

    def project(self, cam, scale=1):
        w, h = self.size[0] * scale, self.size[1] * scale
        k = (h / 2) / math.tan(math.radians(self.fov) / 2)
        z = np.maximum(cam[..., 2], 1e-3)
        return np.stack([w / 2 + k * cam[..., 0] / z, h / 2 - k * cam[..., 1] / z], -1)


LIGHT = np.array([0.45, -0.8, 0.38])
LIGHT /= np.linalg.norm(LIGHT)


def render(camera, groups, ground=(-120, 120, -60, 160), tile=8.0, label=None, ss=2,
           markers=(), lines=(), sky=(186, 198, 214)):
    """groups: list of (triangles (T,3,3) world, colours (T,3)).  Painter's sort."""
    w, h = camera.size
    img = Image.new('RGB', (w * ss, h * ss), sky)
    draw = ImageDraw.Draw(img)
    # ground tiles
    x0, x1, z0, z1 = ground
    quads, cols = [], []
    for i, x in enumerate(np.arange(x0, x1, tile)):
        for j, z in enumerate(np.arange(z0, z1, tile)):
            quads.append([[x, 0, z], [x + tile, 0, z], [x + tile, 0, z + tile], [x, 0, z + tile]])
            cols.append((122, 128, 118) if (i + j) % 2 else (136, 142, 132))
    quads = np.array(quads, float)
    cq = camera.to_camera(quads)
    keep = (cq[..., 2] > 0.5).all(1)
    sq = camera.project(cq, ss)
    order = np.argsort(-cq[..., 2].mean(1))
    for i in order:
        if keep[i]:
            draw.polygon([tuple(p) for p in sq[i]], fill=cols[i])
    # body triangles
    tris = np.concatenate([g[0] for g in groups])
    col = np.concatenate([g[1] for g in groups])
    # shadows: straight down the light onto y=0
    shadow = Image.new('L', img.size, 0)
    sd = ImageDraw.Draw(shadow)
    st = tris - LIGHT[None, None, :] * (tris[..., 1:2] / LIGHT[1])
    cs = camera.to_camera(st)
    ok = (cs[..., 2] > 0.5).all(1)
    ss_pts = camera.project(cs, ss)
    for i in np.nonzero(ok)[0]:
        sd.polygon([tuple(p) for p in ss_pts[i]], fill=110)
    img = Image.composite(Image.new('RGB', img.size, (60, 62, 58)), img, shadow.point(lambda v: v))
    draw = ImageDraw.Draw(img)
    ct = camera.to_camera(tris)
    ok = (ct[..., 2] > 0.5).all(1)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    nl = np.linalg.norm(n, axis=1, keepdims=True)
    n = n / np.maximum(nl, 1e-12)
    view = tris.mean(1) - camera.eye
    flip = (n * view).sum(1) > 0
    n[flip] *= -1
    diff = np.clip(-(n @ LIGHT), 0, 1)
    shade = col * (0.42 + 0.58 * diff)[:, None]
    shade = np.clip(shade * 255, 0, 255).astype(int)
    sp = camera.project(ct, ss)
    depth = ct[..., 2].mean(1)
    for i in np.argsort(-depth):
        if ok[i]:
            c = shade[i]
            draw.polygon([tuple(p) for p in sp[i]], fill=(int(c[0]), int(c[1]), int(c[2])))
    for p, colour, r in markers:
        c = camera.to_camera(np.asarray(p, float)[None])
        if c[0, 2] > 0.5:
            q = camera.project(c, ss)[0]
            draw.ellipse([q[0] - r * ss, q[1] - r * ss, q[0] + r * ss, q[1] + r * ss], fill=colour)
    for a, b, colour in lines:
        c = camera.to_camera(np.array([a, b], float))
        if (c[:, 2] > 0.5).all():
            q = camera.project(c, ss)
            draw.line([tuple(q[0]), tuple(q[1])], fill=colour, width=2 * ss)
    img = img.resize((w, h), Image.LANCZOS)
    if label:
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype('arial.ttf', 15)
        except OSError:
            font = ImageFont.load_default()
        d.rectangle([0, 0, w, 20], fill=(0, 0, 0))
        d.text((5, 2), label, fill=(255, 255, 255), font=font)
    return img


def sheet(images, columns):
    w, h = images[0].size
    rows = (len(images) + columns - 1) // columns
    out = Image.new('RGB', (w * columns, h * rows), (0, 0, 0))
    for i, im in enumerate(images):
        out.paste(im, ((i % columns) * w, (i // columns) * h))
    return out

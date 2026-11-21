"""Design the three northern shore profiles from the frozen R64 world survey.

All control points use world X/Z. Silhouettes only affect natural columns in
a local margin, and fade back into the original shore at open-path endpoints.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as nd
from scipy.interpolate import CubicSpline


LEVEL = 62
WEST = [
    (-3240,-1300),(-3235,-1323),(-3228,-1345),(-3211,-1361),
    (-3197,-1385),(-3199,-1401),(-3209,-1422),(-3206,-1437),
    (-3192,-1452),(-3183,-1477),(-3180,-1502),(-3166,-1519),
    (-3147,-1522),(-3118,-1533),(-3095,-1527),(-3077,-1516),
    (-3066,-1498),(-3056,-1487),(-3042,-1492),(-3031,-1507),
    (-3018,-1521),(-2996,-1529),(-2972,-1531),(-2955,-1528),
    (-2934,-1519),(-2919,-1518),(-2903,-1523),(-2887,-1522),
    (-2869,-1512),(-2853,-1503),(-2832,-1505),(-2817,-1515),
    (-2801,-1535),(-2786,-1545),(-2778,-1559),(-2771,-1572),
    (-2752,-1578),(-2736,-1573)]
ISLAND = [
    (-1302,-2150),(-1294,-2158),(-1281,-2164),(-1267,-2162),
    (-1256,-2155),(-1250,-2145),(-1248,-2133),(-1254,-2122),
    (-1267,-2115),(-1277,-2109),(-1288,-2107),(-1297,-2112),
    (-1301,-2121),(-1301,-2132),(-1306,-2141)]
HEADLAND = [
    (-1378,-2142),(-1372,-2139),(-1360,-2130),(-1353,-2122),
    (-1342,-2115),(-1335,-2118),(-1331,-2127),(-1336,-2137),
    (-1335,-2146),(-1331,-2155),(-1334,-2165),(-1331,-2174)]
EAST = [
    (2836,-1826),(2846,-1825),(2858,-1827),(2866,-1832),
    (2871,-1839),(2877,-1847),(2879,-1853),(2877,-1858),
    (2884,-1861),(2894,-1863),(2900,-1861)]


def spline(vertices, closed=False):
    v = np.array(vertices, dtype=float)
    if closed:
        v = np.vstack([v, v[:1]])
    along = np.r_[0, np.cumsum(np.linalg.norm(np.diff(v, axis=0), axis=1))]
    return CubicSpline(along, v, bc_type="periodic" if closed else "natural")(
        np.linspace(0, along[-1], int(3 * along[-1]) + 2))


def smooth(weight):
    weight = np.clip(weight, 0., 1.)
    return weight * weight * (3. - 2. * weight)


def curve(wet, origin, vertices, closure, margin, ends, max_add):
    # Positive distances denote land. Only the portion close to the designed
    # profile changes. The mask retains the far bank of any neighboring basin.
    x0, z0 = origin
    z, x = np.ogrid[z0:z0+wet.shape[0], x0:x0+wet.shape[1]]
    line = spline(vertices, not closure)
    points = np.rint(line - [x0,z0]).astype(int)
    xy = list(map(tuple, points.tolist()))
    segment = Image.new("1", wet.shape[::-1])
    ImageDraw.Draw(segment).line(xy, fill=1, width=1)
    dist = nd.distance_transform_edt(~np.asarray(segment, bool))
    land_image = Image.new("1", wet.shape[::-1])
    tail = [(a-x0,b-z0) for a,b in closure]
    ImageDraw.Draw(land_image).polygon(xy+tail, fill=1)
    land = np.asarray(land_image, bool)
    desired = np.where(land, dist+0.5, -dist-0.5)
    blend = smooth((margin-dist)/(0.32*margin))
    if not closure:
        blend[land] = 1.0
    if ends:
        for (a,b),radius in zip((vertices[0], vertices[-1]), ends):
            blend *= smooth(np.hypot(x-a,z-b)/radius)
    old = nd.distance_transform_edt(~wet)-nd.distance_transform_edt(wet)
    target = old + blend*(desired-old)
    result = target < 0
    return wet & ~result, ~wet & result & (old <= max_add)


def design(name, src, out):
    with np.load(src / (name+'.npz')) as a:
        x0,z0 = int(a['x0']),int(a['z0'])
        h,k = a['h'],a['k']
        roots = a['r'].astype(bool)
    wet = (k==4)&(h==LEVEL)
    origin = (x0,z0)
    if name=='western_facility':
        operations = [curve(wet, origin, WEST, [(-2720,-1645),(-3310,-1645),(-3310,-1280)], 82,(34,42),10)]
    elif name=='northwest_lakes':
        # Complete the south face of the island and taper the end of the
        # neighboring headland separately, keeping the channel between them.
        operations = [curve(wet,origin,ISLAND,[],16,None,7),
                      curve(wet,origin,HEADLAND,[(-1342,-2191),(-1366,-2186),(-1380,-2158)],19,(14,17),5)]
    else:
        operations = [curve(wet,origin,EAST,[(2898,-1886),(2836,-1886)],17,(13,12),6)]
    fill = np.logical_or.reduce([i[0] for i in operations])
    add = np.logical_or.reduce([i[1] for i in operations]) & (k==3) & ~roots
    if name == "east_shelf":
        zz,xx = np.ogrid[z0:z0+h.shape[0], x0:x0+h.shape[1]]
        add &= (xx < 2875) & (zz > -1860)
    foreign = (k==4)&~wet
    add &= nd.distance_transform_edt(~foreign)>6
    add &= nd.distance_transform_edt((k!=5)&(k!=0))>7
    wet_after = (wet & ~fill) | add
    # Do not create isolated puddles on the hillside.
    add &= nd.binary_propagation(wet & ~fill,mask=wet_after)
    zz,xx=np.where(fill|add)
    sy=slice(int(zz.min()),int(zz.max())+1);sx=slice(int(xx.min()),int(xx.max())+1)
    np.savez_compressed(out/(name+'.npz'),x0=x0+sx.start,z0=z0+sy.start,level=LEVEL,
                        add=add[sy,sx],fill=fill[sy,sx])
    return dict(site=name,added=int(add.sum()),filled=int(fill.sum()),
                bounds=[x0+sx.start,z0+sy.start,x0+sx.stop,z0+sy.stop])


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--surveys',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();args.out.mkdir(exist_ok=True,parents=True)
    print(json.dumps([design(s,args.surveys,args.out) for s in
                      ('western_facility','northwest_lakes','east_shelf')],indent=2))

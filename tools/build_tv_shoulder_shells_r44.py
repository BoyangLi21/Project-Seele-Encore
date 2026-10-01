"""Original TV shoulder-seat silhouettes around the three measured EVA pylons.

Produces a new, independently loaded asset; never alters the world or the six
facet pads. Positions use the fixed gantry frame, metres, +Z toward the back.
The episode frames are privately observed shape references, never textures.
"""
from pathlib import Path
import hashlib
import json
import math
import struct
import argparse
import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import ConvexHull
import build_tv_machinery_r16 as m
from author_tv_shoulder_installation_r44 import prism_hits_triangle

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/rebuild_r44'
PRIVATE_OUTPUTS = BASE / 'hangar_machinery'
FRAME = BASE / 'facility_transit_r44/hangar_tv_calibration_v2/semantic_frame.json'
PAINT, EDGE, JOINT, DARK, RED = 0x74816B, 0xA5AEA0, 0x8D9A82, 0x293431, 0xAB3532
COLLISION = {}


def physical(part, x,y,z,w,h,d):
    COLLISION.setdefault(part,[]).append([[x,y,z],[x+w,y+h,z+d]])


def prism_xz(poly, bottom, top, color):
    """Convex panel with real thickness and bevelled plan perimeter."""
    centre = np.asarray(poly).mean(axis=0)
    for a, b in zip(poly, poly[1:] + poly[:1]):
        m.quad((a[0], bottom, a[1]), (a[0], top, a[1]),
               (b[0], top, b[1]), (b[0], bottom, b[1]), color)
        m.tri((centre[0], top, centre[1]), (b[0], top, b[1]), (a[0], top, a[1]), color)
        m.tri((centre[0], bottom, centre[1]), (a[0], bottom, a[1]), (b[0], bottom, b[1]), color)


def panel(x0, x1, z0, z1, y, thick, bevel=.22, color=PAINT):
    b = min(bevel, (x1-x0)/3, (z1-z0)/3)
    prism_xz([(x0+b,z0),(x1-b,z0),(x1,z0+b),(x1,z1-b),
              (x1-b,z1),(x0+b,z1),(x0,z1-b),(x0,z0+b)], y, y+thick, color)


def slope(x0, x1, z0, z1, y0, y1, thickness, color=PAINT):
    a,b,c,d=(x0,y0,z0),(x1,y0,z0),(x1,y1,z1),(x0,y1,z1)
    e,f,g,h=[(p[0],p[1]-thickness,p[2]) for p in (a,b,c,d)]
    for pts in ((a,d,c,b),(e,f,g,h),(a,b,f,e),(b,c,g,f),(c,d,h,g),(d,a,e,h)):
        m.quad(*pts,color)


def pipe(points, radius, color=DARK, segments=12):
    for a,b in zip(points,points[1:]):
        m.cylinder(a,b,radius,color,segments)


def hazard_phase(x,y,z,w,h):
    m.box(x,y,z,w,h,.032,DARK)
    pitch=.60
    for n in range(math.floor((x-h)/pitch),math.ceil((x+w)/pitch)+1):
        start=n*pitch-x
        poly=[(start,0),(start+.26,0),(start+.26+h,h),(start+h,h)]
        for limit,sign in ((0,1),(w,-1)):
            clipped=[]
            for a,b in zip(poly,poly[1:]+poly[:1]):
                da=sign*(a[0]-limit);db=sign*(b[0]-limit)
                if da>=0:clipped.append(a)
                if (da>=0)!=(db>=0):
                    t=da/(da-db);clipped.append(tuple(a[k]+(b[k]-a[k])*t for k in range(2)))
            poly=clipped
        for i in range(1,len(poly)-1):
            m.tri((x+poly[0][0],y+poly[0][1],z-.006),
                  (x+poly[i+1][0],y+poly[i+1][1],z-.006),
                  (x+poly[i][0],y+poly[i][1],z-.006),RED)


def moving_shell():
    # The narrow inner facet pad is kept separately. This U-shaped outer shell
    # sits entirely outside the pylon's submitted bounds, including release.
    panel(6.65,10.85,-6.45,7.50,53.05,1.12,.40)
    panel(5.55,6.65,-6.45,-5.54,53.05,1.12,.18)
    panel(5.55,6.65,7.10,7.50,53.05,1.12,.16)
    physical('shell_r',6.65,53.05,-6.45,4.20,1.12,13.95)
    physical('shell_r',5.55,53.05,-6.45,1.10,1.12,.91)
    physical('shell_r',5.55,53.05,7.10,1.10,1.12,.40)
    # Panel joint reveals are recessed dark grooves with a slim raised edge.
    for z in (-2.55, 1.25, 6.10):
        panel(8.03,10.40,z-.035,z+.035,54.173,.018,.012,DARK)
    for x in (8.05,10.38):
        panel(x-.025,x+.025,-3.28,6.98,54.173,.025,.014,EDGE)
    for z in (-3.15,6.78):
        panel(8.18,10.27,z-.30,z+.30,54.19,.095,.16,EDGE)
        for x in (8.5,10.10):
            m.cylinder((x,54.29,z),(x,54.36,z),.080,DARK,8)
    # Two short vertical accumulator housings, annular caps and hose loops.
    for z in (-2.55,5.55):
        physical('shell_r',9.32,54.18,z-.58,1.16,1.31,1.16)
        for radius, y0, y1, color in ((.58,54.18,54.42,DARK),(.47,54.40,55.25,JOINT),
                                     (.56,55.20,55.36,EDGE),(.35,55.36,55.49,JOINT)):
            m.cylinder((9.90,y0,z),(9.90,y1,z),radius,color,32)
        m.box(9.46,54.70,z-.43,.88,.12,.86,DARK)
        t=np.linspace(0,1,22)
        pipe([(9.45-1.05*math.sin(p*math.pi),54.82-.46*math.sin(p*math.pi),z+1.3*p) for p in t],.075)
        pipe([(10.25+.37*math.sin(p*math.pi),54.83-.62*math.sin(p*math.pi),z-.85*p) for p in t],.070)
    # Clipped diagonal hazard strips on the actual front metal face.
    m.warning(6.88,53.19,-6.49,3.75,.63)
    # Twin underside hinge bearings; this shell translates, it does not turn
    # around these decorative captive bearings during the shoulder release.
    for z in (-2.40,5.20):
        m.cylinder((10.65,53.37,z),(11.16,53.37,z),.47,DARK,32)
        m.cylinder((11.16,53.37,z),(11.25,53.37,z),.30,EDGE,32)


def platform(outer=14.20, part='platform_r', inspection_portal=None):
    # Broad raked shoulder approach replaces the narrow forklift silhouette.
    x0,x1,z0,z1,y0,y1=8.90,outer,-20.50,-6.58,48.96,52.70
    def sy(z):return y0+(z-z0)/(z1-z0)*(y1-y0)
    plates=[(x0,x1,z0,z1)] if inspection_portal is None else [
        (x0,x1,z0,-19.75),(11.62,x1,-19.75,-17.10),(x0,x1,-17.10,z1)]
    for ax,bx,az,bz in plates:
        # The real hollow receiver passes through a source-authored opening,
        # with full fore lip and outer bearing retained. Not a collision-only
        # subtraction or a runtime triangle cut.
        slope(ax,bx,az,bz,sy(az),sy(bz),.72)
        for z in np.arange(az,bz,.125):
            end=min(bz,z+.125);top=sy(end)
            physical(part,ax,sy(z)-.72,z,bx-ax,top-(sy(z)-.72),end-z)
    for z in (-18.8,-14.9,-11.0,-7.2):
        y=y0+(z-z0)/(z1-z0)*(y1-y0)
        start=11.62 if inspection_portal is not None and -19.75<z<-17.10 else x0+.26
        slope(start,x1-.26,z-.021,z+.021,y-.007,y+.007,.024,DARK)
    for x in (x0+.20,x1-.20):
        spans=[(z0+.30,z1-.30)] if inspection_portal is None or x>=11.62 else [(z0+.30,-19.75),(-17.10,z1-.30)]
        def band_y(z):return y0+.115+(z-(z0+.30))/((z1-.30)-(z0+.30))*(y1-.083-y0-.115)
        for first,last in spans:slope(x-.035,x+.035,first,last,band_y(first),band_y(last),.025,EDGE)
    # Chamfered rectangular access hatch on the inclined top face.
    hx0,hx1=(10.45,14.82) if outer>15 else (9.40,outer-.40)
    slope(hx0,hx1,-13.95,-10.55,sy(-13.95)+.048,sy(-10.55)+.048,.044,DARK)
    slope(hx0+.17,hx1-.18,-13.81,-10.69,sy(-13.81)+.073,sy(-10.69)+.073,.052,PAINT)
    for x in (hx0+.30,hx1-.34):
        for z in (-13.65,-10.90):
            y=y0+(z-z0)/(z1-z0)*(y1-y0)
            m.cylinder((x,y+.07,z),(x,y+.125,z),.07,EDGE,8)
    # Terminal round shaft and captive side flange, visible from low front.
    m.cylinder((8.57,47.43,-20.17),(outer+.04,47.43,-20.17),.64,DARK,40)
    for x in (8.53,9.02,outer-.13,outer-.02):
        m.cylinder((x,47.43,-20.17),(x+.06,47.43,-20.17),.79,JOINT,40)
    m.cylinder((outer+.04,47.43,-20.17),(outer+.09,47.43,-20.17),.48,EDGE,40)
    # Under-platform diagonal load ribs, kept outside the EVA/body lane.
    for x in (9.45,outer-.60):
        points=[(x,47.27,-19.85),(x,50.38,-9.65)] if inspection_portal is None else [
            (x,47.27,-19.85),(x,47.75,-17.00),(x,50.98,-9.65)]
        pipe(points,.18,JOINT,16)
        if inspection_portal is not None:
            for first,last in zip(points,points[1:]):
                first,last=np.array(first),np.array(last)
                for t0,t1 in zip(np.linspace(0,1,81)[:-1],np.linspace(0,1,81)[1:]):
                    p,q=first+(last-first)*t0,first+(last-first)*t1
                    lo,hi=np.minimum(p,q)-.18,np.maximum(p,q)+.18
                    physical(part,*lo,*(hi-lo))
    for z in (-19.3,-15.0,-10.7):
        y=y0+(z-z0)/(z1-z0)*(y1-y0)-.77
        start=11.62 if inspection_portal is not None and z==-19.3 else 9.17
        m.cylinder((start,y,z),(outer-.33,y,z),.12,DARK,12)
        if inspection_portal is not None:physical(part,start,y-.12,z-.12,outer-.33-start,.24,.24)
    # Thin rails only at the outer platform lip. Never across a pylon mouth.
    if inspection_portal is not None:
        # Once this cover is a real personnel inspection surface, its two
        # visible raised plates must also support feet; neither is an overlay
        # painted above an unchanged collision floor.
        for ax,bx,az,bz,offset,thick in ((hx0,hx1,-13.95,-10.55,.048,.044),
                                       (hx0+.17,hx1-.18,-13.81,-10.69,.073,.052)):
            for z in np.arange(az,bz,.125):
                end=min(bz,z+.125)
                physical(part,ax,sy(z)+offset-thick,z,bx-ax,sy(end)-sy(z)+thick,end-z)
        # Authored whole rail segments terminate at the actual service entry;
        # no runtime clipping or removal of unrelated load geometry occurs.
        for first, last in ((-20.10, inspection_portal[0]), (inspection_portal[1], -6.90)):
            for z in np.arange(first, last + .001, 2.4):
                y=sy(z)
                m.cylinder((outer-.25,y+.06,z),(outer-.25,y+1.15,z),.045,EDGE,12)
                physical(part,outer-.295,y+.06,z-.045,.09,1.09,.09)
            for offset,r,color in ((1.15,.048,EDGE),(.66,.032,JOINT)):
                pipe([(outer-.25,sy(first)+offset,first),(outer-.25,sy(last)+offset,last)],r,color,12)
                for z in np.arange(first,last,.125):
                    end=min(last,z+.125)
                    physical(part,outer-.25-r,sy(z)+offset-r,z,2*r,sy(end)-sy(z)+2*r,end-z)
        return
    for z in np.arange(-20.1,-6.9,2.4):
        y=y0+(z-z0)/(z1-z0)*(y1-y0)
        m.cylinder((outer-.25,y+.06,z),(outer-.25,y+1.15,z),.045,EDGE,12)
        physical(part,outer-.295,y+.06,z-.045,.09,1.09,.09)
    pipe([(outer-.25,y0+1.15,-20.1),(outer-.25,y1+1.02,-6.90)],.048,EDGE,12)
    pipe([(outer-.25,y0+.66,-20.1),(outer-.25,y1+.53,-6.90)],.032,JOINT,10)
    for z in np.arange(-20.1,-6.90,.25):
        y=sy(z)
        for offset,r in ((1.15,.048),(.66,.032)):
            physical(part,outer-.25-r,y+offset-r,z,2*r,.25*(y1-y0)/(z1-z0)+2*r,.25)


def front_beam_stage(index):
    # Five genuinely separate overlapping stages per half. During opening all
    # telescope to the outboard receiver, retaining width inside the wet bay.
    x=index*2.15
    y0=48.48-.08*index;top=50.44+.08*index
    depth=1.89+.14*index;z=-18.45-depth/2
    wall=.055
    # Four hollow walls, open sleeve ends: a smaller stage really fits inside
    # the following stage, with .025m vertical and .015m side running gaps.
    m.box(x,y0,z,2.33,wall,depth,PAINT)
    m.box(x,top-wall,z,2.33,wall,depth,PAINT)
    m.box(x,y0+wall,z,2.33,top-y0-2*wall,wall,PAINT)
    m.box(x,y0+wall,z+depth-wall,2.33,top-y0-2*wall,wall,PAINT)
    name=f'front_stage_{index}_r'
    for yy,hh,zz,dd in ((y0,wall,z,depth),(top-wall,wall,z,depth),
                         (y0+wall,top-y0-2*wall,z,wall),(y0+wall,top-y0-2*wall,z+depth-wall,wall)):
        physical(name,x,yy,zz,2.33,hh,dd)
    panel(x+.14,x+2.18,z+.15,z+depth-.15,top+.004,.025,.14,EDGE)
    panel(x+.23,x+2.06,z+.29,z+depth-.29,top+.032,.012,.12,PAINT)
    hazard_phase(x+.10,y0+.09,z-.037,2.12,.78)
    for xx in (x+.30,x+2.03):
        m.bolts(xx,49.45,z-.065,0,.42,DARK)
    m.box(x+.11,49.27,z-.055,2.08,.053,.040,DARK)


def lower_frame():
    # Explicitly authored load path for the complete lower frame. The old
    # 65m front uprights are replaced as whole parts, never cut in Java.
    for side in (-1,1):
        # The actor-frame deck is 29m wide and sits .96m above this gantry
        # origin. Keep complete posts/caps outside its moving footprint.
        x=side*15.85
        for z in (-5.8,6.3):
            physical('cage_frame_lower_r44',x-.85,-.62,z-.95,1.70,47.75,1.90)
            m.housing(x-.85,-.62,z-.95,1.70,47.75,1.90,.30,PAINT)
            m.box(x-.26,.8,z-.99,.52,44.60,.055,DARK)
            m.box(x-.055,.8,z-1.05,.11,44.60,.05,EDGE)
            for y in (2.,10.,18.,26.,34.,42.):
                m.housing(x-1.00,y,z-1.03,2.,.52,2.06,.16,JOINT)
                m.bolts(x-.65,y+.13,z-1.08,1.30,.23,DARK)
            for y in (11.,29.,44.):m.box(x-.14,y,z-1.11,.28,1.0,.045,0xBCC4AD)
            m.housing(x-1.15,46.80,z-1.14,2.30,.43,2.28,.18,JOINT)
        for y in (3.,23.,46.70):
            physical('cage_frame_lower_r44',x-.85,y,-4.85,1.70,.88,10.35)
            m.housing(x-.85,y,-4.85,1.70,.88,10.35,.22,PAINT)
        for z in (-3.75,3.50):
            m.cylinder((side*14.30,21,z),(side*14.30,24,z),.48,JOINT,24)
            for y in (21.,23.9):m.cylinder((side*14.30,y-.05,z),(side*14.30,y+.10,z),.60,DARK,24)
    # Braced base and transverse bearing members preserve a physically
    # separate lower frame from the EVA's moving carrier deck.
    for z in (-5.8,6.3):
        # The front central well belongs to the vertically retracting
        # carrier_clamp (|X|<=6.1, down64m), so a full crossing here would
        # intersect it even when the final deck itself is clear.
        spans=((-15.85,-6.40),(6.40,15.85)) if z<0 else ((-15.85,15.85),)
        for x0,x1 in spans:
            physical('cage_frame_lower_r44',x0,-1.82,z-.60,x1-x0,1.20,1.20)
            m.housing(x0,-1.82,z-.60,x1-x0,1.20,1.20,.22,DARK)


def fixed_support():
    # These outer columns are only six metres above the retained lower cap;
    # broad sloped aprons and paired shell seats carry the visible load.
    for z in (-5.50,7.80):
        physical('fixed_support_r',14.32,47.18,z-.48,1.75,5.26,.96)
        physical('fixed_support_r',13.10,52.34,z-.62,3.28,.70,1.24)
        m.housing(14.32,47.18,z-.48,1.75,5.26,.96,.18,JOINT)
        m.housing(13.10,52.34,z-.62,3.28,.70,1.24,.20,PAINT)
        m.cylinder((14.80,52.47,z),(14.80,53.00,z),.28,DARK,24)
    for z in (-2.80,6.20):
        # Exact closed support patch: top=53.044, shell bottom=53.050.
        m.housing(10.30,52.34,z-.52,5.46,.38,1.04,.12,JOINT)
        physical('fixed_support_r',10.30,52.34,z-.52,5.46,.38,1.04)
        panel(10.30,10.60,z-.52,z+.52,52.72,.324,.09,JOINT)
        physical('fixed_support_r',10.30,52.72,z-.52,.30,.324,1.04)
        pipe([(10.45,52.64,z),(15.10,51.65,z)],.19,JOINT,16)
    # A real flanged loadgirder, not14m of opaque fullsection masking the
    # mechanic's inspection field. Both caps join the original columns;
    # the narrower web and captive stiffeners keep a continuous loadpath.
    for x,y,w,h in ((14.40,51.48,1.36,.12),(15.00,51.60,.16,.62),(14.40,52.22,1.36,.12)):
        m.box(x,y,-5.80,w,h,14.20,PAINT)
        physical('fixed_support_r',x,y,-5.80,w,h,14.20)
    for z in (-5.80,-2.80,1.20,5.20,8.28):
        m.box(14.70,51.60,z,.76,.62,.12,JOINT)
        physical('fixed_support_r',14.70,51.60,z,.76,.62,.12)
    # The new outward-facing arm facet needs a longer real retraction stroke.
    # Its fixed barrel anchor is above the crew and outside the green clevis.
    for z in (1.16,1.88):
        m.housing(15.60,52.32,z-.40,.50,1.08,.80,.12,JOINT)
        m.housing(16.05,53.40,z-.40,1.70,.53,.80,.12,JOINT)
        physical('fixed_support_r',15.60,52.32,z-.40,.50,1.08,.80)
        physical('fixed_support_r',16.05,53.40,z-.40,1.70,.53,.80)
    # The reference-scaled5.3m apron terminates inward of the existingpost.
    # This realunder-apron bridge joins its rearunderside to the original
    # loadcolumn, rather than leaving a shortened platefloating beside it.
    m.housing(11.50,51.70,-6.70,4.40,.28,1.20,.08,JOINT)
    physical('fixed_support_r',11.50,51.70,-6.70,4.40,.28,1.20)


def beam_receiver(outer=14.20,part='front_receiver_r'):
    # Open X-facing receiver, not a solid block swallowing the five sleeves.
    width=outer-10.62
    for x,y,z,w,h,d in ((10.62,47.97,-20.14,width,.105,3.20),
                         (10.62,51.145,-20.14,width,.105,3.20),
                         (10.62,48.075,-20.14,width,3.070,.105),
                         (10.62,48.075,-17.045,width,3.070,.105),
                         (outer-.105,48.075,-20.035,.105,3.070,2.99)):
        m.box(x,y,z,w,h,d,JOINT)
        physical(part,x,y,z,w,h,d)
    for y in (48.20,50.89):
        m.cylinder((10.82,y,-19.89),(outer-.22,y,-19.89),.105,EDGE,16)
    for x in ([11.22,outer-.57] if outer>14 else [11.20]):
        m.cylinder((x,49.56,-20.19),(x,49.56,-20.49),.48,DARK,32)
        m.cylinder((x,49.56,-20.50),(x,49.56,-20.60),.24,EDGE,24)


def side_rails():
    # Alternative visible geometry for measured guards; installation must
    # replace their present model, otherwise duplicated white rails persist.
    for z in np.arange(-20.5,15.51,2.4):
        m.cylinder((17.48,48.03,z),(17.48,49.20,z),.045,EDGE,12)
        m.cylinder((17.48,48.04,z),(17.48,48.14,z),.105,JOINT,16)
    for y,r in ((49.20,.050),(48.62,.033)):
        m.cylinder((17.48,y,-20.5),(17.48,y,15.5),r,EDGE,12)


def reflected(values,side):
    a=np.asarray(values,dtype=float).reshape(-1,3,6).copy()
    a[:,:,0]*=side
    if side<0:a=a[:,[0,2,1],:]
    return a.reshape(-1).tolist()


def bounds(values):
    a=np.asarray(values).reshape(-1,6)[:,:3]
    return [a.min(axis=0).tolist(),a.max(axis=0).tolist()]


def box_vertices(box):
    lo,hi=np.asarray(box,dtype=float)
    return np.array([[x,y,z] for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])])


def convex_voxel_cover(points,pitch=.02):
    """Conservative exact SAT voxel cover, merged into rectangular runs.

    Every selected cube intersects the real convex casting. Consequently any
    extra collision point is within sqrt(3)*pitch of a visible solid point.
    Broad single casting AABBs had .65m false volume and are not acceptable.
    """
    p=np.asarray(points);h=ConvexHull(p);axes=[*h.equations[:,:3],*np.eye(3)]
    edges={tuple(sorted((int(t[i]),int(t[(i+1)%3])))) for t in h.simplices for i in range(3)}
    for a,b in edges:
        for axis in np.eye(3):
            q=np.cross(p[b]-p[a],axis);length=np.linalg.norm(q)
            if length>1e-9:axes.append(q/length)
    axes=np.asarray(axes);projection=p@axes.T;low=projection.min(0);high=projection.max(0)
    radius=pitch/2*np.abs(axes).sum(1)
    lo=np.floor(p.min(0)/pitch).astype(int);hi=np.ceil(p.max(0)/pitch).astype(int)
    grid=np.array(np.meshgrid(*(np.arange(lo[i],hi[i]) for i in range(3)),indexing='ij')).reshape(3,-1).T
    middle=(grid+.5)*pitch;proj=middle@axes.T
    inside=np.all((proj+radius>=low-1e-9)&(proj-radius<=high+1e-9),axis=1)
    cells=grid[inside];runs={}
    for y,z in sorted(set(map(tuple,cells[:,1:]))):
        xs=cells[(cells[:,1]==y)&(cells[:,2]==z),0]
        assert len(xs)==xs.max()-xs.min()+1,'Convex SAT cell row unexpectedly non-contiguous'
        key=(int(xs.min()),int(xs.max()+1));runs.setdefault((int(y),key),[]).append(int(z))
    slabs=[]
    for (y,(x0,x1)),zs in sorted(runs.items()):
        start=last=zs[0]
        for z in zs[1:]+[zs[-1]+2]:
            if z!=last+1:
                slabs.append((x0,x1,y,start,last+1));start=z
            last=z
    grouped={}
    for x0,x1,y,z0,z1 in slabs:grouped.setdefault((x0,x1,z0,z1),[]).append(y)
    boxes=[]
    for (x0,x1,z0,z1),ys in sorted(grouped.items()):
        ys.sort();start=last=ys[0]
        for y in ys[1:]+[ys[-1]+2]:
            if y!=last+1:
                boxes.append([[x0*pitch,start*pitch,z0*pitch],[x1*pitch,(last+1)*pitch,z1*pitch]])
                start=y
            last=y
    return boxes,{'voxel_pitch_m':pitch,'maximum_extra_collision_distance_m':math.sqrt(3)*pitch,
        'exact_sat_intersecting_cubes':len(cells),'merged_collision_boxes':len(boxes),
        'proof':'SAT convex face/box face/edge-cross axes; each covered voxel intersects the actual casting, rigid translation preserves the bound'}


def convex_green_body(points):
    points=np.asarray(points);centre=points.mean(0)
    for ids in ConvexHull(points).simplices:
        a,b,c=points[ids];normal=np.cross(b-a,c-a)
        if normal@(np.array([a,b,c]).mean(0)-centre)<0:b,c=c,b
        m.tri(a,b,c,PAINT)


def shift(opening,row):
    def ramp(v,a,b):
        p=np.clip((v-a)/(b-a),0,1)
        return p*p*(3-2*p)
    return np.asarray(row['exact_geometric_outward_normal_world'])*2.1*ramp(opening,0,.25)+np.array([row['side']*5.35*ramp(opening,.23,.88),0,0])


def export_glb(parts,path):
    # Small self-contained glTF writer; no external Blender install needed.
    doc={'asset':{'version':'2.0','generator':'Original R44 machinery generator'},'scene':0,
         'scenes':[{'nodes':[]}],'nodes':[],'meshes':[],'materials':[{'pbrMetallicRoughness':
         {'metallicFactor':.25,'roughnessFactor':.72},'doubleSided':False}], 'bufferViews':[],'accessors':[]}
    blob=bytearray()
    for name,values in parts.items():
        a=np.asarray(values,np.float32).reshape(-1,6)
        # glTF displays +Y upward just like our metres-based fixed frame.
        tri=a[:,:3].reshape(-1,3,3)
        normal=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);normal/=np.linalg.norm(normal,axis=1)[:,None]
        arrays=(a[:,:3],a[:,3:6]/255,np.repeat(normal,3,axis=0))
        ids=[]
        for q in arrays:
            while len(blob)%4:blob.append(0)
            start=len(blob);raw=np.ascontiguousarray(q,dtype='<f4').tobytes();blob.extend(raw)
            view=len(doc['bufferViews']);doc['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':len(raw),'target':34962})
            acc=len(doc['accessors']);doc['accessors'].append({'bufferView':view,'componentType':5126,'count':len(q),
                'type':'VEC3','min':q.min(axis=0).tolist(),'max':q.max(axis=0).tolist()});ids.append(acc)
        doc['meshes'].append({'name':name,'primitives':[{'attributes':{'POSITION':ids[0],'COLOR_0':ids[1],'NORMAL':ids[2]},'material':0,'mode':4}]})
        n=len(doc['nodes']);doc['nodes'].append({'name':name,'mesh':len(doc['meshes'])-1});doc['scenes'][0]['nodes'].append(n)
    doc['buffers']=[{'byteLength':len(blob)}]
    raw=json.dumps(doc,separators=(',',':')).encode();raw+=b' '*((-len(raw))%4)
    path.write_bytes(struct.pack('<III',0x46546C67,2,28+len(raw)+len(blob))+struct.pack('<I4s',len(raw),b'JSON')+raw+struct.pack('<I4s',len(blob),b'BIN\0')+blob)


def preview(parts,path,opening=False,camera=None,target=None,fov_degrees=None,resolution=(1600,1000)):
    camera=np.array([30.,72.,-56.] if camera is None else camera,dtype=float)
    target=np.array([0.,51.8,-5.8] if target is None else target,dtype=float)
    forward=target-camera;forward/=np.linalg.norm(forward)
    right=np.cross(forward,[0,1,0]);right/=np.linalg.norm(right)
    up=np.cross(right,forward)
    width,height=resolution
    focal=1700 if fov_degrees is None else height/(2*math.tan(math.radians(fov_degrees)/2))
    def project(p):
        q=np.asarray(p)-camera
        depth=q@forward
        return np.stack([width/2+focal*(q@right)/depth,height/2-focal*(q@up)/depth],axis=-1),depth
    rgb=np.zeros((height,width,3),dtype=np.uint8);rgb[:]=[22,31,36]
    zbuffer=np.full((height,width),math.inf)
    # Raster depth, rather than a painter's centroid sort: overlapping access
    # hatches and annular bearings must not show false triangular seams.
    triangles=[]
    for values in parts.values():
        a=np.asarray(values).reshape(-1,3,6)
        xy,depth=project(a[:,:,:3])
        for t,d,col in zip(xy,depth,a[:,:,3:].mean(axis=1)):
            x0=max(0,int(np.floor(t[:,0].min())));x1=min(width,int(np.ceil(t[:,0].max()))+1)
            y0=max(0,int(np.floor(t[:,1].min())));y1=min(height,int(np.ceil(t[:,1].max()))+1)
            if x1<=x0 or y1<=y0 or d.min()<=0:continue
            aa,bb,cc=t
            denominator=(bb[1]-cc[1])*(aa[0]-cc[0])+(cc[0]-bb[0])*(aa[1]-cc[1])
            if abs(denominator)<1e-7:continue
            yy,xx=np.mgrid[y0:y1,x0:x1];xx=xx+.5;yy=yy+.5
            u=((bb[1]-cc[1])*(xx-cc[0])+(cc[0]-bb[0])*(yy-cc[1]))/denominator
            v=((cc[1]-aa[1])*(xx-cc[0])+(aa[0]-cc[0])*(yy-cc[1]))/denominator
            w=1-u-v
            zd=1/(u/d[0]+v/d[1]+w/d[2])
            hit=(u>=-1e-7)&(v>=-1e-7)&(w>=-1e-7)&(zd<zbuffer[y0:y1,x0:x1])
            zbuffer[y0:y1,x0:x1][hit]=zd[hit];rgb[y0:y1,x0:x1][hit]=np.clip(col,0,255).astype(np.uint8)
    im=Image.fromarray(rgb);draw=ImageDraw.Draw(im)
    draw.text((28,24),'R44 authored shoulder-seat geometry | OPEN' if opening else 'R44 authored shoulder-seat geometry | CLOSED',fill=(234,237,226))
    draw.text((28,47),'Offline engineering preview. Actual actor, body pads, collision and Minecraft artistic review remain pending.',fill=(170,186,185))
    im.save(path)


def private_destination(out_path, resource_path=None):
    out_path = Path(out_path).resolve()
    private_root = PRIVATE_OUTPUTS.resolve()
    if out_path.parent != private_root:
        raise ValueError('Output must be an independent new revision directly below artifacts/rebuild_r44/hangar_machinery; never nest inside a published revision')
    if out_path.exists():
        raise ValueError('Output revision already exists; preserve it and choose a fresh revision')
    resource_path = (out_path / 'tv_shoulder_shells_r44.json' if resource_path is None
                     else Path(resource_path).resolve())
    if resource_path.parent != out_path or resource_path.name != 'tv_shoulder_shells_r44.json':
        raise ValueError('Resource must be tv_shoulder_shells_r44.json inside the new private output')
    return out_path, resource_path


def checked_inputs(contacts_path, body_path, out_path, resource_path=None):
    contacts_path, body_path = Path(contacts_path).resolve(), Path(body_path).resolve()
    out_path, resource_path = private_destination(out_path, resource_path)
    contacts = json.loads(contacts_path.read_text(encoding='utf8'))['contacts']
    bodies = json.loads(body_path.read_text(encoding='utf8'))['actors']
    if len(contacts) != 6 or {(r['variant'], r['side']) for r in contacts} != {(v, s) for v in range(3) for s in (-1, 1)}:
        raise ValueError('Explicit contact input must contain the six actual variant/side installations')
    for row in contacts:
        if not row.get('clevis_fixed_gantry_local') or row.get('closed_exact_arm_and_pylon_prism_sat_conflicts') != 0:
            raise ValueError('Legacy/unvalidated contacts rejected; measured solid clevis and actual skin SAT required')
    for variant in range(3):
        parts = bodies[str(variant)]['parts']
        if not all(name in parts for name in ('head', 'pylon_l', 'pylon_r', 'arm_l', 'arm_r')):
            raise ValueError('Actual submitted body is missing required parts')
        if not all(part.get('complete_submitted_part_triangles') for part in parts.values()):
            raise ValueError('Explicit body input must contain complete native triangles for every submitted part')
    return contacts_path, body_path, out_path, resource_path, contacts, bodies


def main(contacts_path, body_path, out_path, resource_path=None):
    global CONTACTS,BODY,OUT,RESOURCE
    CONTACTS,BODY,OUT,RESOURCE,contacts,bodies=checked_inputs(contacts_path,body_path,out_path,resource_path)
    OUT.mkdir(parents=True,exist_ok=False)
    frames=json.loads(FRAME.read_text(encoding='utf8'))['bays']
    m.PARTS.clear();COLLISION.clear()
    m.use('shell_r');moving_shell()
    m.use('platform_r');platform()
    m.use('front_receiver_r');beam_receiver()
    m.use('thin_side_rails_r');side_rails()
    m.use('fixed_support_r');fixed_support()
    for i in range(5):m.use(f'front_stage_{i}_r');front_beam_stage(i)
    for name,values in list(m.PARTS.items()):m.PARTS[name[:-1]+'l']=reflected(values,-1)
    for name,boxes in list(COLLISION.items()):
        COLLISION[name[:-1]+'l']=[[[ -b[1][0],b[0][1],b[0][2]],[-b[0][0],b[1][1],b[1][2]]] for b in boxes]
    # EVA-02's real east lift pocket is an independent preserved component.
    # Its right mechanical apron/receiver stop .21m before the X=85 boundary.
    m.use('platform_2_r');platform(12.20,'platform_2_r')
    m.use('front_receiver_2_r');beam_receiver(12.20,'front_receiver_2_r')
    m.use('cage_frame_lower_r44');lower_frame()
    components=[];body_checks=[];casting_collision=[]
    for row in contacts:
        variant,side=row['variant'],row['side'];suffix='l' if side<0 else 'r'
        name='shell_'+suffix
        if 'clevis_fixed_gantry_local' in row:
            name=f'shell_{variant}_{suffix}'
            m.PARTS[name]=m.PARTS['shell_'+suffix].copy()
            m.use(name);convex_green_body(row['clevis_fixed_gantry_local'])
            cover,proof=convex_voxel_cover(row['clevis_fixed_gantry_local'])
            COLLISION[name]=[b for b in COLLISION['shell_'+suffix]]+cover
            casting_collision.append({'part':name,**proof})
        values=m.PARTS[name];a=np.asarray(values).reshape(-1,6)[:,:3]
        swept=np.concatenate([a+shift(p,row) for p in np.linspace(0,1,121)])
        origin=np.asarray(frames[variant]['eva_feet'])+np.array([0,-.96,0])
        pylon=np.asarray(bodies[str(variant)]['parts']['pylon_'+suffix]['world_bounds']).reshape(2,3)-origin
        # Every U panel/cylinder/hose vertex must stay outside the conservative
        # pylon box at every sampled release state. Topology is checked below.
        collisions=0;minimum_gap=math.inf
        for opening in np.linspace(0,1,121):
            moved=a+shift(opening,row)
            inside=np.all((moved>=pylon[0]-.25)&(moved<=pylon[1]+.25),axis=1)
            # The v3 shell is constrained by the real Y-band, not by the
            # pylon's unrelated widest point lower down. Whole-mesh tests
            # below supersede this diagnostic global-box count.
            collisions+=int(inside.sum())
            delta=np.maximum(pylon[0]-.25-moved,0)+np.maximum(moved-(pylon[1]+.25),0)
            minimum_gap=min(minimum_gap,float(np.linalg.norm(delta,axis=1).min()))
        full_contact_band=bodies[str(variant)]['parts']['pylon_'+suffix].get('top_band_depth_metres',1.5)>=20
        if not full_contact_band:assert collisions==0,('shell crosses measured pylon',variant,side,collisions)
        # Triangle AABBs are sufficient for these convex separate U panels;
        # broadphase overlaps are retained explicitly for native review.
        triangle=np.asarray(values).reshape(-1,3,6)[:,:,:3]
        overlaps=0
        for opening in np.linspace(0,1,121):
            q=triangle+shift(opening,row)
            overlaps+=int(np.all((q.max(axis=1)>=pylon[0]-.25)&(q.min(axis=1)<=pylon[1]+.25),axis=1).sum())
        if not full_contact_band:assert overlaps==0,('shell triangle sweeps pylon box',variant,side,overlaps)
        exact_pylon=0;exact_arm=0
        if full_contact_band:
            ptri=np.array([t['world_vertices'] for t in bodies[str(variant)]['parts']['pylon_'+suffix]['top_band_triangles']])-origin
            atri=np.array([t['world_vertices'] for t in bodies[str(variant)]['parts']['arm_'+suffix]['top_band_triangles']])-origin
            for opening in np.linspace(0,1,121):
                move=shift(opening,row)
                solids=[box_vertices(b)+move for b in COLLISION[name]]
                if 'clevis_fixed_gantry_local' in row:solids.append(np.asarray(row['clevis_fixed_gantry_local'])+move)
                for solid in solids:
                    mask=np.all((ptri.max(1)>=solid.min(0))&(ptri.min(1)<=solid.max(0)),axis=1)
                    exact_pylon+=sum(prism_hits_triangle(solid,t,.003) for t in ptri[mask])
                    arm_mask=np.all((atri.max(1)>=solid.min(0))&(atri.min(1)<=solid.max(0)),axis=1)
                    exact_arm+=sum(prism_hits_triangle(solid,t,.003) for t in atri[arm_mask])
            assert exact_pylon==0,('Actual full-pylon swept collision',variant,side,exact_pylon)
            assert exact_arm==0,('Actual complete-arm swept collision',variant,side,exact_arm)
        all_body_overlap=0;other_body_overlaps={};exact_other_body={};unresolved_body={}
        for body_part_name,part in bodies[str(variant)]['parts'].items():
            if full_contact_band and body_part_name in ('pylon_l','pylon_r','arm_l','arm_r'):continue
            bb=np.asarray(part['world_bounds']).reshape(2,3)-origin
            if not np.all((swept.max(axis=0)>=bb[0]-.20)&(swept.min(axis=0)<=bb[1]+.20)):
                continue
            for opening in np.linspace(0,1,121):
                q=triangle+shift(opening,row)
                n=int(np.all((q.max(axis=1)>=bb[0]-.20)&(q.min(axis=1)<=bb[1]+.20),axis=1).sum())
                all_body_overlap+=n
                if n:other_body_overlaps[body_part_name]=other_body_overlaps.get(body_part_name,0)+n
            if body_part_name not in other_body_overlaps:continue
            if not part.get('complete_submitted_part_triangles'):
                unresolved_body[body_part_name]='Bounds overlap; no complete native triangles, actual penetration is UNKNOWN'
                continue
            actual=np.asarray([t['world_vertices'] for t in part['top_band_triangles']])-origin
            assert actual.shape[0]*3==part['submitted_vertices'],('Incomplete submitted body',variant,body_part_name)
            exact_hits=0
            for opening in np.linspace(0,1,121):
                move=shift(opening,row)
                solids=[box_vertices(b)+move for b in COLLISION[name]]
                if 'clevis_fixed_gantry_local' in row:solids.append(np.asarray(row['clevis_fixed_gantry_local'])+move)
                for solid in solids:
                    mask=np.all((actual.max(1)>=solid.min(0))&(actual.min(1)<=solid.max(0)),axis=1)
                    exact_hits+=sum(prism_hits_triangle(solid,t,.003) for t in actual[mask])
            exact_other_body[body_part_name]=exact_hits
        diagnostic={'variant':variant,'side':side,'actual_pylon_hits':exact_pylon,'actual_arm_hits':exact_arm,
            'other_body_bbox_overlaps':other_body_overlaps,'exact_other_body_triangle_hits':exact_other_body,
            'unresolved_body':unresolved_body,'candidate_installed':False,'native_passed':False,'visual_passed':False}
        (OUT/f'shell_contact_sweep_{variant}_{suffix}.json').write_text(json.dumps(diagnostic,indent=2),encoding='utf8')
        assert not unresolved_body,('Native full-body triangles required; bbox overlap is UNKNOWN',diagnostic)
        assert not any(exact_other_body.values()),('Actual shell/body swept penetration',diagnostic)
        body_checks.append({'variant':variant,'side':side,'parts':len(bodies[str(variant)]['parts']),
            'samples':121,'guard_m':.20,'triangle_aabb_overlaps':all_body_overlap,
            'exact_other_body_triangle_hits':exact_other_body,'unresolved_body':unresolved_body})
        components.append({'id':f'shell_{variant}_{suffix}','part':name,'variant':variant,'side':side,
            'fixed_gantry_origin_world':origin.tolist(),'contact_part_preserved':f'shoulder_pad_{variant}_{suffix}',
            'pivot_local':row['contact_centre_fixed_gantry_local'],'motion':'translation_only_with_exact_facet_pad',
            'normal':row['exact_geometric_outward_normal_world'],'normal_lift_m':2.1,'normal_interval':[0,.25],
            'outboard_m':side*5.35,'outboard_interval':[.23,.88],'closed_bounds_local':bounds(values),
            'sampled_sweep_bounds_local':[swept.min(axis=0).tolist(),swept.max(axis=0).tolist()],
            'pylon_bounds_local':pylon.tolist(),'pylon_guard_m':.25,'minimum_vertex_to_guarded_pylon_m':minimum_gap,
            'sampled_triangle_box_overlaps':overlaps,'actual_complete_pylon_sweep_collisions':exact_pylon,
            'actual_complete_arm_sweep_collisions':exact_arm,
            'clevis_actual_skin_contact':row.get('closed_exact_arm_and_pylon_prism_sat_conflicts'),
            'motion_samples':121})
    for side in (-1,1):
        suffix='l' if side<0 else 'r'
        for name in ('platform','front_receiver','thin_side_rails','fixed_support'):
            row={'id':name+'_'+suffix,'part':name+'_'+suffix,'side':side,
                'pivot_local':[0,0,0],'motion':'fixed','closed_bounds_local':bounds(m.PARTS[name+'_'+suffix]),
                'sampled_sweep_bounds_local':bounds(m.PARTS[name+'_'+suffix])}
            if side==1 and name in ('platform','front_receiver'):
                for variant in (0,1):components.append(row|{'id':row['id']+f'_{variant}','variant':variant})
                part=name+'_2_r'
                components.append(row|{'id':part,'part':part,'variant':2,'closed_bounds_local':bounds(m.PARTS[part]),
                    'sampled_sweep_bounds_local':bounds(m.PARTS[part]),'preserved_native_component':'complete_original_EVA02_east_lift_arrival_pocket_x85..98/z-262..-248'})
            else:components.append(row)
        for i in range(5):
            name=f'front_stage_{i}_{suffix}';values=m.PARTS[name]
            travel=side*(9.2-i*2.15);a=np.asarray(values).reshape(-1,6)[:,:3]
            swept=np.concatenate([a,a+np.array([travel,0,0])])
            components.append({'id':name,'part':name,'side':side,'stage':i,
                'pivot_local':[side*10.75,49.46,-18.45],'motion':'telescoping_translation',
                'translation_open_local':[travel,0,0],'opening_interval':[0,.72],
                'closed_bounds_local':bounds(values),'sampled_sweep_bounds_local':[swept.min(axis=0).tolist(),swept.max(axis=0).tolist()]})
    components.append({'id':'cage_frame_lower_r44','part':'cage_frame_lower_r44','pivot_local':[0,0,0],
        'motion':'fixed','closed_bounds_local':bounds(m.PARTS['cage_frame_lower_r44']),
        'sampled_sweep_bounds_local':bounds(m.PARTS['cage_frame_lower_r44'])})
    resource={'stride':6,'frame':'fixed_gantry_local_metres_world_axes','parts':m.PARTS,'components':components,'collision_parts':COLLISION,
        'casting_collision':casting_collision,
        'source_sha256':{'contacts':hashlib.sha256(CONTACTS.read_bytes()).hexdigest(),'actual_triangles':hashlib.sha256(BODY.read_bytes()).hexdigest()},
        'engineering_dimensions':{'shell_whole_housing_width_m':5.30,'shell_nominal_centre_x_m':8.20,
            'shell_outboard_plate_width_m':4.20,'shell_depth_m':13.95,'shell_inner_lobes_are_pylon_bypass':True,
            'front_beam_nominal_span_m':21.5,'front_beam_thickness_m':2.6,'platform_width_m':5.30,
            'eva02_right_platform_width_m':3.30,'eva02_original_east_lift_pocket_preserved':True,
            'base_beam_top_local_y':-.62,'full_carrier_deck_minimum_local_y':-.54,
            'base_beam_to_full_carrier_deck_vertical_gap_m':.08,
            'carrier_clamp_vertical_well_front_clear_width_m':12.80,
            'carrier_clamp_to_front_outrigger_side_gap_m':.30,
            'platform_rise_m':3.74,'platform_start_matches_real_crew_feet_local_y':48.96,
            'ramp_collision_maximum_vertical_error_m':.125*3.74/13.92,'rail_radius_m':.05,
            'warning':'Image-ratio engineering adaptation, never asserted official TV metres'},
        'integration':{'preserve_original_pad_resource':True,'shell_motion_matches_facet_pad':True,
            'replace_parts':['whole cage_frame replaced by cage_frame_lower_r44','whole shoulder_fixed_mounts replaced by fixed_support_l/r'],
            'fixed_platform_requires_real_collision_surface':True,'front_beam_requires_server_interlock_and_collision':True,
            'thin_side_rails_replace_existing_block_visual_not_duplicate':True,
            'world_write_performed':False,'native_visual_passed':False,'user_accepted':False}}
    RESOURCE.write_text(json.dumps(resource,separators=(',',':')),encoding='utf8')
    (OUT/'manifest.json').write_text(json.dumps({k:v for k,v in resource.items() if k!='parts'},indent=2),encoding='utf8')
    variant_names={c['part'] for c in components if c.get('variant',1)==1 and c['motion']=='translation_only_with_exact_facet_pad'}
    full={k:v for k,v in m.PARTS.items() if not k.startswith('thin_side_rails') and k not in {'cage_frame_lower_r44','platform_2_r','front_receiver_2_r'}
          and (not k.startswith('shell_') or k in variant_names)}
    export_glb(full,OUT/'shoulder_seats_closed.glb')
    preview(full,OUT/'shoulder_seats_closed.png')
    opening={k:v.copy() for k,v in full.items()}
    for row in contacts:
        if row['variant']!=1:continue
        suffix='l' if row['side']<0 else 'r';name=f'shell_1_{suffix}' if f'shell_1_{suffix}' in opening else 'shell_'+suffix
        a=np.asarray(opening[name]).reshape(-1,6);a[:,:3]+=shift(1,row);opening[name]=a.reshape(-1).tolist()
    for c in components:
        if c['motion']=='telescoping_translation':
            a=np.asarray(opening[c['part']]).reshape(-1,6);a[:,:3]+=c['translation_open_local'];opening[c['part']]=a.reshape(-1).tolist()
    export_glb(opening,OUT/'shoulder_seats_open.glb')
    preview(opening,OUT/'shoulder_seats_open.png',True)
    receipt={'resource':str(RESOURCE),'sha256':hashlib.sha256(RESOURCE.read_bytes()).hexdigest(),
             'parts':len(m.PARTS),'triangles':sum(len(v)//18 for v in m.PARTS.values()),'shell_motion_samples':726,
             'pylon_triangle_aabb_collisions':0,'all_body_shell_checks':body_checks,
             'static_collision_geometry_required':True,'native_passed':False,'visual_passed':False}
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
    print(json.dumps(receipt))


if __name__=='__main__':
    p=argparse.ArgumentParser(description='Bake only a fresh private candidate; never install assets or reuse a published revision.')
    p.add_argument('--contacts',type=Path,required=True);p.add_argument('--body',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--resource',type=Path)
    p.add_argument('--check-inputs-only',action='store_true',help='Check complete current inputs and private destination without creating output or baking')
    args=p.parse_args()
    try:
        if args.check_inputs_only:
            contacts,body,out,resource,rows,actors=checked_inputs(args.contacts,args.body,args.out,args.resource)
            print(json.dumps({'contacts_sha256':hashlib.sha256(contacts.read_bytes()).hexdigest(),
                              'body_sha256':hashlib.sha256(body.read_bytes()).hexdigest(),
                              'contacts':len(rows),'actual_body_parts':[len(actors[str(v)]['parts']) for v in range(3)],
                              'private_output':str(out),'resource':str(resource),'output_created':False}))
        else:
            main(args.contacts,args.body,args.out,args.resource)
    except (ValueError,KeyError,FileNotFoundError) as failure:
        p.error(str(failure))

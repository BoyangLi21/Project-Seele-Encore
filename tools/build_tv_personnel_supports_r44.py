"""Private complete bearing revision paired with the permanent staff decks.

Only fixed components change. Published v4 and installed meshes remain intact.
Every authored beam member carries an explicit physical box; no floor is
drawn by the gantry when it is instead owned by the native world grating.
"""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
import build_tv_shoulder_shells_r44 as a

ROOT = Path(__file__).resolve().parents[1]


def member(part, x, y, z, w, h, d, color=a.JOINT):
    a.m.box(x, y, z, w, h, d, color); a.physical(part, x, y, z, w, h, d)


def longitudinal(part, x, y, z, length):
    for xx, yy, ww, hh in [(x, y, .10, .045), (x + .035, y + .045, .03, .19), (x, y + .235, .10, .045)]:
        member(part, xx, yy, z, ww, hh, length, a.DARK)


def transverse(part, x, y, z, width):
    for yy, hh, zz, dd in [(y, .045, z, .20), (y + .045, .19, z + .085, .03), (y + .235, .045, z, .20)]:
        member(part, x, yy, zz, width, hh, dd, a.JOINT)


def standard_staff_bearings():
    part = 'staff_deck_bearings_r'
    # Rear stringers touch the actual native last-row side stringer underside
    # at local52.05; transverse member welds into the retained front column.
    for x in (14.50, 16.40): longitudinal(part, x, 51.77, -6.80, 1.40)
    transverse(part, 14.50, 51.77, -5.70, 2.)
    # Crossbeam joins the real receiver bottom and carries the staff bridge.
    transverse(part, 13.70, 47.80, -20.18, 2.80)
    for x in (14.50, 16.40): longitudinal(part, x, 48.52, -23.50, 3.50)
    for x in (14.60, 16.30):
        # Continuous welded riser from the receiver-bearing member to bridge.
        member(part, x, 48.04, -20.10, .10, .76, .12, a.DARK)


def fixed02():
    part = 'fixed_support_2_r'
    # Full front column/cap migrates onto the retained lower longitudinal
    # bearing, never the preserved east lift's floor/door/aperture domain.
    for z in (-3.0, 7.8):
        a.m.housing(14.32, 47.18, z - .48, 1.75, 5.26, .96, .18, a.JOINT)
        a.physical(part, 14.32, 47.18, z - .48, 1.75, 5.26, .96)
        a.m.housing(13.10, 52.34, z - .62, 3.28, .70, 1.24, .20, a.PAINT)
        a.physical(part, 13.10, 52.34, z - .62, 3.28, .70, 1.24)
        a.m.cylinder((14.80, 52.47, z), (14.80, 53.00, z), .28, a.DARK, 24)
    for z in (-2.8, 6.2):
        a.m.housing(10.30, 52.34, z - .52, 5.46, .38, 1.04, .12, a.JOINT)
        a.physical(part, 10.30, 52.34, z - .52, 5.46, .38, 1.04)
        a.panel(10.30, 10.60, z - .52, z + .52, 52.72, .324, .09, a.JOINT)
        a.physical(part, 10.30, 52.72, z - .52, .30, .324, 1.04)
        a.pipe([(10.45, 52.64, z), (15.10, 51.65, z)], .19, a.JOINT, 16)
    for x, y, w, h in [(14.40, 51.48, 1.36, .12), (15.00, 51.60, .16, .62), (14.40, 52.22, 1.36, .12)]:
        member(part, x, y, -3.62, w, h, 12.02, a.PAINT)
    for z in (-3.62, -2.8, 1.2, 5.2, 8.28): member(part, 14.70, 51.60, z, .76, .62, .12)
    for z in (1.16, 1.88):
        a.m.housing(15.60, 52.32, z - .40, .50, 1.08, .80, .12, a.JOINT)
        a.m.housing(16.05, 53.40, z - .40, 1.70, .53, .80, .12, a.JOINT)
        a.physical(part, 15.60, 52.32, z - .40, .50, 1.08, .80)
        a.physical(part, 16.05, 53.40, z - .40, 1.70, .53, .80)
    # Transfer clear volume is ahead of the migrated whole bearing assembly.
    # A low load member reconnects the apron to the retained lower side frame,
    # rather than reintroducing a horizontal obstacle through the stair.
    longitudinal(part, 15.30, 46.96, -7.10, 4.40)
    transverse(part, 11.60, 46.96, -7.10, 3.80)
    # Complete apron diagonals stay behind the personnel landing instead of
    # piercing it. The inboard extension returns to the existing casting seat.
    member(part, 9.70, 51.80, -6.90, .20, .10, 3.10, a.JOINT)
    for end in [(9.80, 51.90, -3.80)]:
        start = np.array([15.35, 47.24, -3.80]); finish = np.array(end)
        a.m.cylinder(start, finish, .085, a.DARK, 12)
        for first, last in zip(np.linspace(0, 1, 65)[:-1], np.linspace(0, 1, 65)[1:]):
            p, q = start + (finish - start) * first, start + (finish - start) * last
            lo, hi = np.minimum(p, q) - .085, np.maximum(p, q) + .085
            a.physical(part, *lo, *(hi - lo))
    # The independent 02 personnel lane is deliberately lower than the
    # machinery rake: footworld=-392, stringer underside local50.80.
    # A continuous pair of small I stringers, not an invisible collision slab,
    # bears the whole two metre lane and its full-width turn landing.
    for x in (10.50, 12.40): longitudinal(part, x, 50.52, -16.50, 12.00)
    for z in (-16.50, -12.50, -7.10, -4.70):
        transverse(part, 10.50, 50.52, z, 2.00)
    transverse(part, 10.50, 46.96, -7.10, 4.90)
    for x in (10.60, 12.30):
        member(part, x, 47.24, -7.10, .10, 3.28, .12, a.DARK)


def platform02_utility():
    part = 'platform_2_r'
    def sy(z): return 48.96 + (z + 20.50) * (52.70 - 48.96) / 13.92
    for x0, x1, z0, z1 in [(8.90,12.20,-20.50,-19.75),(11.62,12.20,-19.75,-17.10),
                            (8.90,12.20,-17.10,-16.64),(8.90,10.50,-16.64,-6.58)]:
        a.slope(x0, x1, z0, z1, sy(z0), sy(z1), .72)
        for z in np.arange(z0, z1, .125):
            last = min(z1, z + .125)
            a.physical(part, x0, sy(z) - .72, z, x1 - x0, sy(last) - sy(z) + .72, last - z)
    a.m.cylinder((8.57, 47.43, -20.17), (12.24, 47.43, -20.17), .64, a.DARK, 40)
    for x in (8.53, 9.02, 12.07, 12.18): a.m.cylinder((x, 47.43, -20.17), (x + .06, 47.43, -20.17), .79, a.JOINT, 40)
    for z in (-20.1, -17.7):
        a.m.cylinder((11.95, sy(z) + .06, z), (11.95, sy(z) + 1.15, z), .045, a.EDGE, 12)
        a.physical(part, 11.905, sy(z) + .06, z - .045, .09, 1.09, .09)
    for height, radius in ((1.15, .048), (.66, .032)):
        a.m.cylinder((11.95, sy(-20.1) + height, -20.1), (11.95, sy(-16.94) + height, -16.94), radius, a.EDGE, 12)
        for z in np.arange(-20.1, -16.94, .125):
            last = min(z + .125, -16.94)
            a.physical(part, 11.95 - radius, sy(z) + height - radius, z,
                       2 * radius, sy(last) - sy(z) + 2 * radius, last - z)


def inspection_edges(part, outer, front_portal=None):
    """True worker edges delimit green work face from receiver/shoulder ends."""
    def sy(z):return 48.96+(z+20.50)*3.74/13.92
    # Both equipment ends remain visible and physical behind these boundaries.
    # The independent lane enters through the outer side, not either end.
    front=[(8.955,outer)] if front_portal is None else [(8.955,front_portal[0]),(front_portal[1],outer)]
    if front_portal is not None:
        assert 8.955<=front_portal[0]<front_portal[1]<=outer
    segments=[(np.array([8.955,sy(-16.5),-16.5]),np.array([8.955,sy(-7.5),-7.5]))]
    segments.extend((np.array([start,sy(-16.5),-16.5]),np.array([end,sy(-16.5),-16.5]))for start,end in front if end>start)
    segments.append((np.array([8.955,sy(-7.5),-7.5]),np.array([outer,sy(-7.5),-7.5])))
    for first,last in segments:
        length=np.linalg.norm(last-first);count=max(2,int(np.ceil(length/2.4))+1)
        for p in np.linspace(first,last,count):
            a.m.cylinder(p+[0,.06,0],p+[0,1.15,0],.045,a.EDGE,12)
            a.physical(part,p[0]-.045,p[1]+.06,p[2]-.045,.09,1.09,.09)
        for height,r in ((1.15,.048),(.66,.032)):
            a.m.cylinder(first+[0,height,0],last+[0,height,0],r,a.EDGE,12)
            for t0,t1 in zip(np.linspace(0,1,81)[:-1],np.linspace(0,1,81)[1:]):
                p,q=first+(last-first)*t0+[0,height,0],first+(last-first)*t1+[0,height,0]
                low,high=np.minimum(p,q)-r,np.maximum(p,q)+r
                a.physical(part,*low,*(high-low))


def main(base, out):
    base = Path(base); out, resource = a.private_destination(out)
    d = json.loads(base.read_text('utf8')); a.m.PARTS.clear(); a.COLLISION.clear()
    # The broad green casting remains an actual fixed inspection surface.
    # Its two metre rail opening and steel lip connect it to the independent
    # personnel lane; only its receiver and shoulder swept ends are equipment.
    a.m.use('platform_r'); a.platform(inspection_portal=(-16.50,-14.50))
    inspection_edges('platform_r',13.95)
    a.slope(14.20,14.50,-16.50,-14.50,48.96+4*3.74/13.92,48.96+6*3.74/13.92,.12,a.JOINT)
    for z in np.arange(-16.50,-14.50,.125):
        end=min(z+.125,-14.50); low=48.96+(z+20.5)*3.74/13.92; high=48.96+(end+20.5)*3.74/13.92
        a.physical('platform_r',14.20,low-.12,z,.30,high-low+.12,end-z)
    a.m.PARTS['platform_l']=a.reflected(a.m.PARTS['platform_r'],-1)
    a.COLLISION['platform_l']=[[[-b[1][0],b[0][1],b[0][2]],[-b[0][0],b[1][1],b[1][2]]] for b in a.COLLISION['platform_r']]
    a.m.use('staff_deck_bearings_r'); standard_staff_bearings()
    a.m.PARTS['staff_deck_bearings_l'] = a.reflected(a.m.PARTS['staff_deck_bearings_r'], -1)
    a.COLLISION['staff_deck_bearings_l'] = [[[-b[1][0], b[0][1], b[0][2]], [-b[0][0], b[1][1], b[1][2]]] for b in a.COLLISION['staff_deck_bearings_r']]
    a.m.use('fixed_support_2_r'); fixed02()
    a.m.use('platform_2_r'); platform02_utility()
    # The48mm transverse tube must end inside the casting boundary. Its
    # former centre at10.50 protruded into the retained full-width low lane.
    inspection_edges('platform_2_r',10.452)
    for name in a.m.PARTS:
        d['parts'][name] = a.m.PARTS[name]; d['collision_parts'][name] = a.COLLISION[name]
    components = []
    for c in d['components']:
        if c['part'] in ('platform_2_r','platform_r','platform_l'):
            b = a.bounds(d['parts'][c['part']]); components.append(c | {'closed_bounds_local': b, 'sampled_sweep_bounds_local': b})
        elif c['part'] == 'fixed_support_r':
            components += [c | {'id': c['id'] + '_0', 'variant': 0}, c | {'id': c['id'] + '_1', 'variant': 1}]
        else: components.append(c)
    for name, variants in [('staff_deck_bearings_l', [-1]), ('staff_deck_bearings_r', [0, 1]), ('fixed_support_2_r', [2])]:
        for variant in variants:
            b = a.bounds(d['parts'][name]); row = {'id': name + '_' + str(variant), 'part': name, 'motion': 'fixed', 'pivot_local': [0, 0, 0], 'closed_bounds_local': b, 'sampled_sweep_bounds_local': b}
            if variant != -1: row['variant'] = variant
            components.append(row)
    d['components'] = components
    d['personnel_platform_revision'] = {'permanent_world_grating_not_entity_floor': True, 'world_layout_requires': 'personnel_platforms_v5_layout_v4',
                                        'whole_operator_surface_interlock_required': True, 'native_full_routes_passed': False,
                                        'root_install_allowed': False, 'author_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    out.mkdir(parents=True, exist_ok=False); resource.write_text(json.dumps(d, separators=(',', ':')), 'utf8')
    receipt = {'base_sha256': hashlib.sha256(base.read_bytes()).hexdigest(), 'candidate_sha256': hashlib.sha256(resource.read_bytes()).hexdigest(),
               'changed_moving_parts': False, 'full_body_and_other_entities_clearance': 'PENDING', 'whole_02_support_load_path': 'Connected lower member and diagonal upper apron/transfer bearings authored; full space/native proof pending',
               'native_apply_allowed': False, 'world_write_performed': False}
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2), 'utf8'); print(json.dumps(receipt))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--base', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    args = p.parse_args(); main(args.base, args.out)

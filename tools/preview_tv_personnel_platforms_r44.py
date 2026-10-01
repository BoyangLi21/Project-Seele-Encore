"""Read-only composite of authored cage, native grating and measured EVA skin.

Border guards in this diagnostic are proposed geometry, not applied world cells.
No artificial actor pose or hidden floor is substituted for the measured data.
"""
from pathlib import Path
import argparse, hashlib, json, math
import numpy as np
from PIL import Image, ImageDraw
import build_tv_shoulder_shells_r44 as a
from build_tv_personnel_deck_assets_r44 import authored, rotated
from build_tv_personnel_guard_assets_r44 import members

ROOT = Path(__file__).resolve().parents[1]


def main(asset, layout, body, out, boundaries=None):
    out = Path(out)
    if out.exists(): raise ValueError('Fresh diagnostic output required')
    out.mkdir(parents=True)
    cage, plan, skin = [json.loads(Path(p).read_text('utf8')) for p in (asset, layout, body)]
    exact_ops=json.loads(Path(boundaries).read_text('utf8')) if boundaries else None
    previews = []
    for variant in (0, 2):
        origin = np.array([-11.5 + 42 * variant, -442.96, -239.5])
        parts = {}
        for c in cage['components']:
            if c.get('variant', variant) != variant: continue
            parts[c['part']] = cage['parts'][c['part']]
        for name, part in skin['actors'][str(variant)]['parts'].items():
            t = np.asarray([t['world_vertices'] for t in part['top_band_triangles']], dtype=float).reshape(-1, 3)
            color = (115, 105, 156) if variant == 0 else (148, 68, 60)
            values = np.column_stack((t - origin, np.tile(color, (len(t), 1))))
            parts['actual_body_' + name] = values.reshape(-1).tolist()
        a.m.PARTS = {}; a.m.use('permanent_native_grating')
        floors = [c for c in plan['floor_cells'] if c['variant'] == variant]
        tiles = {(c['position'][0], c['position'][2]) for c in floors}
        for cell in floors:
            q = np.array(cell['position'])
            prop = dict(s.split('=') for s in cell['after'].split('[')[1][:-1].split(','))
            boxes = [rotated(b, prop['facing']) for b in authored(prop['profile'], int(prop['level']))]
            for box in boxes:
                lo = np.array(box[:3]) + q - origin
                a.m.box(*lo, *(np.array(box[3:]) - box[:3]), 0x66736E)
            if exact_ops is not None:continue
            # Borders outside the two metre floor: top follows actual native
            # stair/ramp datum. These outlines are a proposal, not final ops.
            top = max(b[4] for b in boxes) + q[1]
            y = math.ceil(top); drop = round((y - top) * 4)
            for dx, dz, facing in [(-1,0,'west'),(1,0,'east'),(0,-1,'north'),(0,1,'south')]:
                if (q[0]+dx, q[2]+dz) in tiles: continue
                # The existing public entrance is open in this diagnostic.
                if cell['role'] == 'supported_front_access_bridge' and dz == -1: continue
                if 'entry_stair' in cell['role'] and dx == 1: continue
                if variant == 2 and cell['side'] == 1 and dx == -1 and q[2] in (-254,-253): continue
                if not (variant == 2 and cell['side'] == 1) and q[2] in (-256,-255) and dx == -cell['side']: continue
                adjacent = np.array([q[0]+dx,y,q[2]+dz])
                face = facing
                # Guard base authored north; map its plane onto neighbouring
                # cell boundary facing the actual deck, retaining net width.
                for b in members(drop):
                    rb = rotated(b, face)
                    lo = np.array(rb[:3]) + adjacent - origin
                    a.m.box(*lo, *(np.array(rb[3:]) - rb[:3]), 0x9BA49A)
        if exact_ops is not None:
            native=json.loads((ROOT/'artifacts/rebuild_r44/hangar_machinery/tv_personnel_guard_native_v1/native_union_readback/native64.json').read_text('utf8'))
            native.update(json.loads((ROOT/'artifacts/rebuild_r44/hangar_machinery/tv_personnel_deck_native_v1/native_union_readback/full_native_collision_shapes.json').read_text('utf8')))
            a.m.use('exact_native_boundary_and_open_door_geometry')
            for op in exact_ops:
                q=np.array(op['position'])
                if round((q[0]+11.5)/42)!=variant or op['role'] not in ('personnel_boundary_guard','finite_personnel_entry_gate'):continue
                state=op['after'].replace('open=false','open=true')
                for b in native[state]:
                    b=np.array(b).reshape(2,3);lo=b[0]+q-origin
                    a.m.box(*lo,*(b[1]-b[0]),0x9BA49A if 'guard' in state else 0x526B60)
        # Actual public front corridor datum retained; shown only for access.
        a.m.use('existing_front_public_corridor_context')
        a.m.box(-20.5,48.76,-28.5,41.,.20,4.,0x48524E)
        a.m.use('person_height_1_8m')
        # A prospective fixed inspection station on the actual green face,
        # connected by the portal. Its native access is still to be tested.
        x, z = (11.5, -15.5) if variant == 0 else (9.7, -12.5)
        feet = 48.96 + (z + 20.5 + .3) * 3.74/13.92
        a.m.box(x-.22,feet,z-.12,.18,.85,.24,0xCB8A37)
        a.m.box(x+.04,feet,z-.12,.18,.85,.24,0xCB8A37)
        a.m.box(x-.25,feet+.85,z-.15,.50,.65,.30,0xD9A747)
        a.m.box(x-.13,feet+1.50,z-.13,.26,.30,.26,0xDEC9AC)
        parts.update(a.m.PARTS)
        a.export_glb(parts,out/f'bay_{variant}_whole_personnel.glb')
        for name, camera, target in [('whole',[39,72,-67],[0,49,-6]),
                                     ('human',[15.5,52.5175,-13],[11.5,51.8,-15.5])]:
            if variant == 2 and name == 'human': camera,target=[11.5,52.58,-9],[9.7,51.5,-12.5]
            path = out/f'bay_{variant}_{name}.png'
            a.preview(parts,path,camera=camera,target=target)
            im=Image.open(path); draw=ImageDraw.Draw(im)
            draw.rectangle((0,0,1600,90),fill=(22,31,36))
            draw.text((20,15),f'Bay {variant:02d} | actual submitted EVA skin + whole candidate cage + native grating geometry',fill='white')
            draw.text((20,38),'Orange figure: 1.8m. Exact native proposed guards / open doors; EVA tint is diagnostic, not actual livery.',fill=(219,187,124))
            draw.text((20,61),'NOT installed. Whole staffing / green inspection / native lifecycle pending. No artistic/native PASS.',fill=(231,144,119))
            im.save(path); previews.append(str(path))
    reference = ROOT/'artifacts/tv_facilities_r16/references/tv_cage.png'
    ref=Image.open(reference).convert('RGB'); ref.thumbnail((800,700))
    made=Image.open(out/'bay_0_whole.png'); made.thumbnail((1120,700))
    compare=Image.new('RGB',(1920,760),(22,31,36));compare.paste(ref,(0,50));compare.paste(made,(800,50))
    draw=ImageDraw.Draw(compare);draw.text((20,15),'Private TV source reference',fill='white');draw.text((820,15),'Engineering candidate; camera/pose/light differ',fill='white')
    compare.save(out/'private_tv_comparison.png')
    inputs=(asset,layout,body,boundaries) if boundaries else (asset,layout,body)
    (out/'receipt.json').write_text(json.dumps({'inputs':{str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in inputs},'images':previews,'native_passed':False,'art_passed':False,'world_write':False,'remaining':['whole surface coverage and green inspection access','whole platform occupied prepare/motion native interlock','full native entry and return','support / producer / world / entities / complete interfaces']},indent=2),'utf8')
    print(json.dumps({'output':str(out),'images':previews}))


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    for key in ('asset','layout','body','out'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--boundaries',type=Path)
    args=p.parse_args();main(args.asset,args.layout,args.body,args.out,args.boundaries)

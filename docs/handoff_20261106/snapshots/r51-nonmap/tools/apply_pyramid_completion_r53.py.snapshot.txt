"""Root-only exact installer for reviewed pyramid/lab completion candidates."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import msvcrt
import nbtlib
import numpy as np
import regional_voxels as vox
import extend_world_depth_r52 as extension
from query_blocks import iter_selected_sections, iter_block_entities
from apply_s20_approved_semantic_repairs import atomic_replace

DIM = 'projectseele:geofront'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure(world, rows):
    selected = {}
    for r in rows:
        x, y, z = r['pos']
        selected.setdefault((x // 16, z // 16), set()).add(y // 16)
    sections = {(x, z, y): (p, i) for x, z, y, p, i in iter_selected_sections(world, DIM, selected)}
    assert len(sections) == sum(map(len, selected.values())), 'Unmeasured candidate section'
    lo = tuple(min(r['pos'][i] for r in rows) for i in range(3))
    hi = tuple(max(r['pos'][i] for r in rows) for i in range(3))
    tags = dict(iter_block_entities(world, DIM, lo, hi, selected_chunks=set(selected)))
    actual = {}
    for r in rows:
        x, y, z = q = tuple(r['pos'])
        pal, idx = sections[x // 16, z // 16, y // 16]
        actual[q] = pal[int(idx[((y & 15) << 8) | ((z & 15) << 4) | (x & 15)])]
    return actual, tags


def matches(tag, snbt):
    return tag is None if snbt is None else tag is not None and tag == nbtlib.parse_nbt(snbt)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--candidate', type=Path, action='append', required=True)
    p.add_argument('--stage', required=True)
    p.add_argument('--authority', type=Path)
    p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    assert a.stage.replace('_', '').isalnum()
    base = a.base.resolve()
    world = base / 'WORLD'
    out = base / 'pyramid_completion' / a.stage
    assert not (out / 'APPLIED.json').exists(), 'Applied epoch is immutable'
    rows_by_pos = {}
    sources = []
    for path in a.candidate:
        path = path.resolve()
        candidate = json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes())
        assert candidate['schema'] == 'projectseele.r53.exact-static-candidate.v1'
        assert Path(candidate['world']).resolve() == world and candidate['dimension'] == DIM
        assert candidate['world_written'] is False and not candidate.get('holds')
        rows = candidate['cells']
        inverse = {tuple(r['pos']): r for r in candidate['inverse']}
        assert len(rows) == len(inverse) == len(candidate['positiveEditMask']) > 0
        assert {tuple(q) for q in candidate['positiveEditMask']} == set(inverse)
        for r in rows:
            q = tuple(r['pos'])
            back = inverse[q]
            assert all(r.get(k) == back.get(v) for k, v in [('before', 'after'), ('after', 'before'), ('before_nbt', 'after_nbt'), ('after_nbt', 'before_nbt')])
            assert r['before'] != r['after'] or r.get('before_nbt') != r.get('after_nbt')
            if q in rows_by_pos:
                assert all(rows_by_pos[q].get(k) == r.get(k) for k in ('before', 'after', 'before_nbt', 'after_nbt')), ('Candidate overlap disagrees', q)
            else:
                rows_by_pos[q] = r
        sources.append(dict(path=str(path), sha256=digest(path), cells=len(rows)))
    rows = [rows_by_pos[q] for q in sorted(rows_by_pos)]
    vox.WORLD = extension.WORLD = world
    vox.OUT = out
    vox.DIM = DIM
    lock = extension.acquire_world_lock()
    receipt = None
    authority = None
    try:
        actual, tags = measure(world, rows)
        conflicts = [dict(pos=r['pos'], actual=actual[tuple(r['pos'])], expected=r['before'], nbt_equal=matches(tags.get(tuple(r['pos'])), r.get('before_nbt'))) for r in rows if actual[tuple(r['pos'])] != r['before'] or not matches(tags.get(tuple(r['pos'])), r.get('before_nbt'))]
        out.mkdir(parents=True, exist_ok=True)
        if a.authority:
            plan = json.loads((a.authority / 'PLAN.json').read_text('utf8'))
            target = world / plan['target_relative_path']
            assert world in target.resolve().parents
            assert digest(target) == plan['exact_before_sha256']
            assert digest(a.authority / 'candidate.dat') == plan['candidate_sha256']
            assert target.read_bytes() == (a.authority / 'before.dat').read_bytes()
            source = Path(plan['source_path'])
            assert digest(source) == plan['source_candidate_sha256'], 'Apply the Source compatibility patch before chamber authority'
            from facility_frame_nbt_r52 import unpack_position
            from rebind_highest_chamber_r52 import state
            chamber = nbtlib.load(a.authority / 'candidate.dat')['data']
            witnesses = [dict(pos=unpack_position(image['Pos']), before=state(image['State']), before_nbt=None if 'NBT' not in image else image['NBT'].snbt()) for image in chamber['Images']]
            witnesses += [dict(pos=r['pos'], before=None, before_nbt=r['nbt']) for r in plan['two_original_readers_current_exact']]
            chamber_states, chamber_tags = measure(world, witnesses)
            assert all((r['before'] is None or chamber_states[tuple(r['pos'])] == r['before']) and matches(chamber_tags.get(tuple(r['pos'])), r['before_nbt']) for r in witnesses), 'Actual original chamber image/reader changed'
            authority = dict(path=target, before=target.read_bytes(), after=(a.authority / 'candidate.dat').read_bytes())
        report = dict(world=str(world), stage=a.stage, sources=sources, cells=len(rows), conflicts=conflicts, world_written=False, native_game_verified=False)
        (out / 'PREFLIGHT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf8')
        assert not conflicts, ('Candidate exact precondition changed', conflicts[:8])
        painter = vox.Painter(vertical_bounds=(-1344, 320))
        for r in rows:
            q = tuple(r['pos'])
            new_tag = None if r.get('after_nbt') is None else nbtlib.parse_nbt(r['after_nbt'])
            if r['before'] == r['after']:
                assert new_tag is not None
                painter.update_block_entity(q, r['before'], tags.get(q), new_tag, r['owner'])
            else:
                painter.exact((*q, *q), r['before'], r['after'], r['owner'])
                if new_tag is not None:
                    painter.block_entities[q] = new_tag
        painter.meta.update(root_author=True, reviewed_exact_candidates=sources, playable=False)
        folder = painter.save_plan(a.stage)
        with gzip.open(folder / 'exact_forward.json.gz', 'wt', encoding='utf8') as f:
            json.dump(rows, f, ensure_ascii=False)
        with gzip.open(folder / 'exact_inverse.json.gz', 'wt', encoding='utf8') as f:
            json.dump([dict(r, before=r['after'], after=r['before'], before_nbt=r.get('after_nbt'), after_nbt=r.get('before_nbt')) for r in rows], f, ensure_ascii=False)
        if not a.apply:
            print(json.dumps(dict(cells=len(rows), conflicts=0, candidates=len(sources), authority=bool(authority), world_written=False)))
            return
        assert not list(folder.glob('applied_*'))
        if authority:
            (out / 'authority_before.dat').write_bytes(authority['before'])
        receipt = painter.apply(a.stage, session_lock=lock)
        if authority:
            assert authority['path'].read_bytes() == authority['before']
            atomic_replace(authority['path'], authority['after'])
        actual, after_tags = measure(world, rows)
        assert all(actual[tuple(r['pos'])] == r['after'] and matches(after_tags.get(tuple(r['pos'])), r.get('after_nbt')) for r in rows)
        edited = set(rows_by_pos)
        assert all(after_tags.get(q) == t for q, t in tags.items() if q not in edited), 'Unrelated complete BE changed'
        if authority:
            assert authority['path'].read_bytes() == authority['after']
        report.update(world_written=True, receipt=receipt, full_state_nbt_readback_cells=len(rows), complete_removed_bes=sum(r.get('before_nbt') is not None and r.get('after_nbt') is None for r in rows), unrelated_bes_preserved=sum(q not in edited for q in tags), highest_authority_installed=bool(authority), pending=['actual floor/lift/swipe/transport execution and native visual review'])
        (out / 'APPLIED.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf8')
        print(json.dumps({k: v for k, v in report.items() if k not in ('sources', 'receipt')}, ensure_ascii=False))
    except BaseException:
        if authority and authority['path'].read_bytes() != authority['before']:
            atomic_replace(authority['path'], authority['before'])
        if receipt:
            applied = list((out / a.stage).glob('applied_*'))
            assert len(applied) == 1
            for path in (applied[0] / 'before').glob('r.*.mca'):
                atomic_replace(world / 'dimensions/projectseele/geofront/region' / path.name, path.read_bytes())
            (applied[0] / 'ROLLED_BACK.json').write_text('{"reason":"pyramid composite validation failed"}', 'utf8')
        raise
    finally:
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        lock.close()


if __name__ == '__main__':
    main()

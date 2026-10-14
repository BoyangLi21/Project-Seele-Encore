"""Targeted offline contract tests; synthetic fixtures never become WORLD data."""
import contextlib
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import upright_native_anchor_selection_r53 as m
import audit_current_anchor_complete_motion_r53 as sweep


class CurrentAnchorSweep(unittest.TestCase):
    def test_native_prune_requires_actual_obb_overlap(self):
        a, b = [0., 0, 0], [1., 1, 0]
        corner = [.48, .63, -.02, .52, .67, .02]
        self.assertTrue(m.segment_box(a, b, corner, m.RADIUS))
        self.assertFalse(m.rod_box_intersects_native(a, b, corner))
        self.assertTrue(m.rod_box_intersects_native(a, b, [.53, .53, -.02, .57, .57, .02]))

    def test_sparse_native_cells_keep_measured_axis_order(self):
        class World:
            tiles = {(2, -4, 1): (('minecraft:air', 'projectseele:nerv_shaft_panel'), np.zeros(4096, dtype=np.uint16))}
            status = {(2, 1): 'full'}
        World.tiles[(2, -4, 1)][1][7*256+9*16+5] = 1
        self.assertEqual(list(m.NativeBearingCells(World()).near([37, -57, 25], 2)), [(37, -57, 25)])

    def test_prism_sat_matches_independent_linear_program(self):
        from scipy.optimize import linprog
        random = np.random.default_rng(53014)
        fixtures = [(np.array([[1., 0, 0], [0, 1., 0], [1., 1., 0]]), np.zeros(3), np.zeros(3),
                     ('finite', np.zeros(3), np.eye(3), np.full(3, .05)))]
        for i in range(80):
            tri = random.normal(size=(3, 3))
            start = random.normal(size=3)
            end = start+random.normal(size=3)*(400 if i % 3 == 0 else 2)
            basis, _ = np.linalg.qr(random.normal(size=(3, 3)))
            fixtures.append((tri, start, end, ('finite', random.normal(size=3), basis, np.full(3, .25))))
        for tri, start, end, box in fixtures:
            _, centre, basis, half = box
            origin = (tri[0]+start-centre)@basis
            matrix = np.column_stack([(tri[1]-tri[0])@basis, (tri[2]-tri[0])@basis, (end-start)@basis])
            lp = linprog(np.zeros(3), A_ub=np.vstack([matrix, -matrix, [1., 1., 0]]),
                         b_ub=np.concatenate([half-origin, half+origin, [1.]]), bounds=[(0, 1)]*3, method='highs')
            self.assertEqual(bool(len(sweep.prism_hits(tri[None], start, end, box))), lp.success)

    def test_global_translation_clip_is_finite(self):
        start, end = np.array([-1000., 0, 0]), np.array([1000., 0, 0])
        bounds = (np.array([-2., -1, -1]), np.array([2., 1, 1]))
        clipped = sweep.clipped_translation(start, end, *bounds, np.array([-.1]*3), np.array([.1]*3), 0)
        np.testing.assert_allclose(clipped, [[-2.1, 0, 0], [2.1, 0, 0]])
        self.assertIsNone(sweep.clipped_translation(start, end, *bounds, np.array([0., 3, 0]), np.array([1., 4, 1]), 0))

    def test_reinforced_attach_needs_optin_width_and_two_real_feet(self):
        import attach_upright_native_seats_r52 as attach
        folder = m.ROOT/'.Codex/map_complete_20261013/requirements_audit/anchor_tool/tests'
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=folder) as tmp:
            root = Path(tmp)
            request = dict(socket_id='synthetic', leg='test', side=1, rail_bearing=[1/3, 0, 1/3],
                actual_rail_weld_triangle=[[0, 0, 0], [1, 0, 0], [0, 0, 1]], maximum_native_connector_m=8)
            prefix = [1/3, -.2, 1/3]
            main = dict(socket_id='synthetic', at=[0, -10, 0], state='synthetic', bearing=[0, -9, 0], normal=[0, 1, 0],
                connector_via_world=[prefix, [0, -8.8, 0]], connector_width_m=.25, native_seat_width_m=.35,
                finite_connector_limit_m=20, selected_by='applied_current_lining', secondary_native_seat=dict(
                    at=[2, -10, 0], state='synthetic', bearing=[2, -9, 0], normal=[0, 1, 0],
                    connector_via_world=[prefix, [2, -8.8, 0]], native_seat_width_m=.35, selected_by='applied_current_lining'))
            steel = root/'steel.json'; seats = root/'seats.json'; out = root/'out.json'
            common = dict(model_source_sha256='synthetic', directory_geometry_sha256='synthetic')
            steel.write_text(json.dumps(dict(common, socket_requests=[request], pieces=[])), encoding='utf8')
            argv = ['attach', '--steel', str(steel), '--seats', str(seats), '--output', str(out)]
            seats.write_text(json.dumps(dict(common, seats=[main])), encoding='utf8')
            with patch('sys.argv', argv), self.assertRaises(AssertionError): attach.main()
            argv += ['--maximum-connector-path', '20', '--allow-reinforced-long-brackets']
            for bad in (dict(main, connector_width_m=.12), dict(main, secondary_native_seat=None)):
                seats.write_text(json.dumps(dict(common, seats=[bad])), encoding='utf8')
                with patch('sys.argv', argv), self.assertRaises(AssertionError): attach.main()
            seats.write_text(json.dumps(dict(common, seats=[main])), encoding='utf8')
            with patch('sys.argv', argv), contextlib.redirect_stdout(io.StringIO()): attach.main()
            result = json.loads(out.read_text())
            self.assertTrue(result['supports_complete'])
            self.assertEqual(len(result['anchors']), 2)
            receipt = json.loads(out.with_suffix('.SUPPORT_RECEIPT.json').read_text())['connector_lengths'][0]
            self.assertLess(receipt['actual_connector_length_m'], 20)
            self.assertLess(receipt['diagonal_weld_to_foot_length_m'], 20)
            self.assertAlmostEqual(receipt['combined_steel_length_m'],
                receipt['actual_connector_length_m']+receipt['diagonal_weld_to_foot_length_m']-.2)


class CurrentAnchors(unittest.TestCase):
    def test_explicit_inputs(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            m.parse_args([])

    def test_applied_source_and_axis_order(self):
        folder = m.ROOT / '.Codex/map_complete_20261013/requirements_audit/anchor_tool/tests'
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=folder) as tmp:
            p = Path(tmp).resolve()
            self.assertTrue(p.is_relative_to(folder.resolve()))
            world = p/'WORLD'; world.mkdir()
            before = np.zeros((1, 4096), np.uint16); after = before.copy()
            index = 7*256+9*16+5
            after[0, index] = 1
            before[0, index+1] = after[0, index+1] = 1
            after[0, index+2] = 2
            candidate = p/'CIVIL.npz'
            np.savez(candidate, section_keys=np.array([[2, -3, -4]]), before=before, after=after,
                     palette=np.array(['minecraft:air', 'projectseele:nerv_shaft_panel', 'minecraft:iron_block']))
            receipt = p/'APPLIED.json'
            receipt.write_text(json.dumps(dict(applied=False, world=str(world), npz_sha256=m.sha(candidate))))
            with self.assertRaises(ValueError): m.verify_applied(world, candidate, receipt)
            receipt.write_text(json.dumps(dict(world_written=True, root_author=True, sections=1,
                full_selected_sections_read_back=1, receipt=dict(world=str(world), verified=True),
                candidate_sha256=m.sha(candidate))))
            self.assertEqual(m.verify_applied(world, candidate, receipt), m.sha(candidate))
            with self.assertRaises(ValueError): m.verify_applied(p, candidate, receipt)
            ownership = m.Ownership(candidate)
            self.assertEqual(ownership.expected((37, -57, -39)), 'projectseele:nerv_shaft_panel')
            self.assertIsNone(ownership.expected((38, -57, -39)))
            self.assertIsNone(ownership.expected((39, -57, -39)))
            self.assertIsNone(ownership.expected((0, 0, 0)))
            candidate.write_bytes(candidate.read_bytes()+b'x')
            with self.assertRaises(ValueError): m.verify_applied(world, candidate, receipt)

    def test_retained_scope(self):
        self.assertTrue(m.retained_city((-12, -400, -54)))
        self.assertTrue(m.retained_city((88, 80, -46)))
        self.assertFalse(m.retained_city((89, 80, -46)))
        self.assertFalse(m.retained_city((72, 81, -35)))
        self.assertFalse(m.retained_city((72, -411, -35)))

    def test_finite_faces_and_normal_exit(self):
        self.assertTrue(m.finite_face([[0, 0, 0, 1, 1, 1]], [.5, 1, .5], [0, 1, 0]))
        self.assertFalse(m.finite_face([[0, 0, 0, 1, 1, 1]], [.05, 1, .5], [0, 1, 0]))
        self.assertFalse(m.finite_face([[0, 0, 0, 1, .5, 1]], [.5, 1, .5], [0, 1, 0]))
        path = m.folded_path([0, 0, .5], [0, -1, 0], [2, -1.5, .5], [-1, 0, 0])
        self.assertIsNotNone(path)
        self.assertTrue(np.array_equal(path[1], [0, -.5, .5]))
        self.assertIsNone(m.folded_path([0, 0, 0], [0, -1, 0], [2, 2, 0], [-1, 0, 0]))
        self.assertIsNone(m.folded_path([0, 0, 0], [0, -1, 0], [20, -2, 0], [-1, 0, 0]))

    def test_local_clearance_rejects_unknown_and_blockers(self):
        class World:
            def __init__(self, obstacle=None): self.obstacle = obstacle
            def block(self, p):
                if p == (2, -2, 0): return 'solid'
                if p == (1, -2, 0) and self.obstacle != 'none': return self.obstacle
                return 'minecraft:air'
        class Gates:
            def intersects(self, a, b, radius): return None
        path = m.folded_path([0, 0, .5], [0, -1, 0], [2, -1.5, .5], [-1, 0, 0])
        shapes = {'solid': [[0, 0, 0, 1, 1, 1]]}
        self.assertTrue(m.path_clear(path, (2, -2, 0), World('none'), shapes, Gates())[0])
        self.assertEqual(m.path_clear(path, None, World('none'), shapes, Gates())[1], 'native_collision')
        self.assertEqual(m.path_clear(path, (2, -2, 0), World(), shapes, Gates())[1], 'unknown_chunk_or_native_shape')
        self.assertEqual(m.path_clear(path, (2, -2, 0), World('solid'), shapes, Gates())[1], 'native_collision')
        self.assertTrue(m.segment_box([0, 0, 0], [2, 0, 0], [.9, -.1, -.1, 1.1, .1, .1]))
        self.assertFalse(m.segment_box([0, 0, 0], [2, 0, 0], [.9, 1, 1, 1.1, 2, 2]))

    def test_current_capture_source(self):
        sockets = dict(model_source_sha256=m.sha(m.ROOT/'src/main/resources/assets/projectseele/mesh/upright_outer_captured_r52.json'),
                       head_transfer_source_sha256=m.sha(m.ROOT/'src/main/resources/assets/projectseele/mesh/outer_head_transfer_r53.json'),
                       sockets=[dict(actual_rail_weld_triangle=[[0, 0, 0], [1, 0, 0], [1, 0, 1]],
                                     rail_bearing=[2/3, 0, 1/3], normal=[0, -1, 0])])
        result = m.source_check(sockets, m.ROOT/'src/main/resources/assets/projectseele/mesh/upright_outer_captured_r52.json',
                                m.ROOT/'src/main/resources/assets/projectseele/mesh/outer_head_transfer_r53.json')
        self.assertGreater(result['source_halfspace_margin_m'], .30)
        sockets['sockets'][0]['normal'] = [0, 0, 0]
        with self.assertRaises(ValueError):
            m.source_check(sockets, m.ROOT/'src/main/resources/assets/projectseele/mesh/upright_outer_captured_r52.json',
                           m.ROOT/'src/main/resources/assets/projectseele/mesh/outer_head_transfer_r53.json')


if __name__ == '__main__':
    unittest.main()

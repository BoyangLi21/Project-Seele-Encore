# map_buildings: buried houses (E5) and door-frame gaps (E6)

Read-only scans of a stopped world copy, plus planners that write row files for
`tools/write_deep_cells.py`. Set `BUILDINGS_WORLD` to the world folder (default: the
map-buildings copy on E:). Run from a work folder that holds copies of these scripts;
every script reads and writes its data files next to itself.

Order:
1. `doors.py <region dir> doors.json`: every building door, blocked thresholds and gaps beside it.
2. `scan_all.py <region dir> <workers>`: walls.npy, fill.npy (about an hour with 6 workers, ~4 GB RAM).
3. `refine.py`, `refine_fill.py`: walls_room.npy, fill_room.npy (rooms only, no planters under trees).
4. `stations.py <world>/mtr/projectseele/geofront stations.json`; zones.json comes from regional_plan.json.
5. `cluster.py`, `sites.py`, `depth.py`, `make_list.py <out>`: groups, houses.json, the E5 list.
6. `e6_plan.py <out>`: rows that close the gaps beside doors with the frame block next to them.
7. `e5_plan.py <sites.json> <out>`: rows that dig a half-buried house out (interior fill, footprint,
   2-column apron at the floor, 1:1 grassed slope, trees on cut ground removed whole).

The writer refuses city-lift, lift and launch protected cells and, by default, any row on a block entity.

Floating buildings (the floor hangs over open space with ground or water below):
8. `float_scan.py <region dir> <workers>`: float.npy, every building cell with open space under it.
9. `float_cluster.py`, `float_rank.py`: pieces, then house-like (walls on the floor) and exposed (the gap shows at the edge).
10. `float_views.py <views.json>`: side and aerial views for `shots.py`.
11. `f_plan.py <sites.json> <out>`: fill under the floor; the outer ring continues the base block down;
    the ground around rises 1:1 to the base but never more than one cell above a road or path next to it.

Round 2 (2026-11-11):
12. `deep_check.py`, `deep_plan.py B01,B03 <out>`: swallowed buildings, exposure to sky, and rows that take
    them away and close the slope (writer needs --allow-block-entities; the replaced blocks' entities are dropped).
13. `e13_plan.py <sites.json> <out> [float file]`: ground a platform edge: 1:1 earth cone where the drop is
    small, 8-cell retaining walls with 3-column grass benches where it is deep; `write` clips a sample.

Round 4 (2026-11-11 evening):
14. `rails.py`: MTR rail paths per block (quadratic through the tangent intersection) -> column map.
15. `viaduct_piers.py <plates.json> <out>`: spans over MAXSPAN with no support within 6 columns of the
    rail get 2x2 piers of the deck block. Still over-reports dense stone viaducts; check pictures first.
16. `e13_plan.py` plants bushes and small trees on terrace benches at the density of the woods around.
    A platform piece is only E13 if it is terrain-like: elevated road/station decks and viaducts
    (open space used underneath) must stay empty — bay-side batch B and C1/C3 were withdrawn for that.
17. `e13_views.py`, `b07_plan.py` (paves pits at street level, clears terrain resting on floors).
18. `e13_plan.py` (round 5): the fill takes the place of trunks inside it; dirt left under removed
    trunks turns to grass; as many trees replanted on the new ground as were taken off it (same log);
    retaining walls are capped next to roads too.
19. `cliff_plan.py <dig rows> <x0,z0,x1,z1> <out>`: cliffs left at the edge of a dig-out become a
    1:1 slope (up to 6 high) or stone-brick terraces with planted benches.

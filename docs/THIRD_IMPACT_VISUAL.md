# Third Impact visual contract

This sequence is an explicitly staged visual prototype. Code presence is not
acceptance: every model or renderer change must still pass the views below.

## Reference boundary

- The film tableau uses nine Mass-Production Evangelions as the outer
  Sephirot, with Unit-01 at Tiferet, and presents the Tree in an inverted
  orientation.
- `EOE_INVERTED` rotates the presented diagram as one object. Array index 0
  remains Keter/כתר but occupies the nadir, index 9 remains Malkuth/מלכות but
  occupies the crown, and Tiferet/תפארת remains the geometric centre. Every
  visible Hebrew node/path inscription is also rotated 180 degrees; keeping
  upright type over inverted nodes would not reproduce the film composition.
- The reconstructed glyph uses the factual Golden Dawn graph: ten Sephirot,
  22 paths and the Hebrew letters Aleph through Tav. It does not ship or trace
  an Evangelion frame, official artwork, or a third-party diagram.
- Name and graph cross-checks:
  - https://en.wikipedia.org/wiki/The_End_of_Evangelion#Religion,_philosophy_and_psychology
  - https://evangelion.fandom.com/wiki/Tree_of_Life
  - https://commons.wikimedia.org/wiki/File:Tree_of_Life_(Sephiroth).svg
  - https://hermetic.com/jwmt/v1n3/pathworking
  - https://hermeticgoldendawn.org/h-o-g-d-dictionary/
- The Hebrew divine-name row follows the common Golden Dawn/Hermetic
  correspondence. It is labelled as that reconstruction and is not presented
  as a facsimile of an ancient Jewish manuscript or an Evangelion asset.

## Current composition

- Explicit `EOE_INVERTED` layout: Keter is the low point, Malkuth the high
  point, and the shared server/client node array keeps all ten labels and EVA
  positions attached to the same semantic nodes.
- Node field: 62 blocks wide by 134.4 blocks high (before rings),
  reduced from 84 by 179.2.
- Pure-red double paths, concentric Sephira rings and text, without black
  label boxes or text shadows. The path lanes and rings are deliberately thin
  so they remain a backplate rather than a red wall over the EVA silhouettes.
- Hebrew is the visible language. There is no detached custom title and no
  `HORIZON AETERNITATIS` row. The renderer draws ten external numeral/name
  rows, ten each of external divine-name, archangel and angelic-order rows,
  22 path letters, four internal correspondence rows per node, and 22 smaller
  path-number inscriptions: 124 emitted label roles in total. The four-row
  exterior clusters are deliberately smaller and tighter than the previous
  two-row layout. Latin transliterations remain code/report metadata only and
  are not rendered.
- Each Sephira also has 12 fine radial register marks. Internal circle/path
  inscriptions use normal depth and sit behind the real EVA meshes; external
  names and primary path letters remain a readable foreground layer. This
  provides the reference diagram's dense, arcane character without importing,
  tracing or packaging the supplied screenshot.
- Tiferet's six light rays use about half the old span and less than one third
  of the old peak width/alpha; the real crucified Unit-01 must remain the focal
  silhouette.
- All nine production units and all nearby EVA variants receive one complete
  front-facing yaw (body, head, previous-frame rotations and pitch).
- Every deployed production unit receives the synchronized `VISUAL_RITUAL`
  state. Ritual rendering no longer infers intent from `NoAI + NoGravity`, so
  an inert Visual-Lab subject can still display idle, move, attack or revive.
- Unit-01's crucified flag has priority over Visual Lab, weapon, aim and
  movement animations. Entering the tableau clears held weapons and forces the
  dedicated arms-out animation.

## Manual acceptance pass

1. Run `/seele visual setup`, followed by `/seele visual impact`. The second
   command immediately stages the tree, parks all nine vessels and moves the
   player to the deterministic full-front camera.
2. For the normal story timeline, instead give the player
   `/give @s projectseele:seele_scenario`, aim at Unit-01 and use it once. Wait
   15 seconds for the tree phase.
3. Capture the complete front, a 30-degree side view, and a close Tiferet view.
4. Reject the pass if any of these occurs:
   - Unit-01's arms are not horizontally outstretched;
   - an old aim/weapon animation replaces either arm;
   - a production EVA shows its back while another shows its front;
   - Keter appears at the top rather than the inverted low point;
   - Hebrew letters are mirrored, the source-name rows are unreadable, or the
     smaller divine-name rows collapse into solid blocks at the normal
     scenario viewing distance;
   - the tree is clipped out of a normal-FOV front capture.
5. Use the scenario item on Unit-01 a second time to verify clean release and
   slow-falling recovery.
6. During the normal story timeline, save and leave after the tree appears,
   then re-enter the world. The nine indexed vessels must be reconciled at the
   same Sephirot, and the tree must resume at its saved visual age rather than
   restart or duplicate. Repeat once after respawn and once after a dimension
   round trip.

## Current automated evidence

Run the dedicated batch with:

```text
gradlew runClient -PquickPlayWorld=SEELE_TOKYO3_REBUILT -PvisualCapture=true -PvisualCaptureUnit=impact
```

The desktop equivalent is `tools/start_test.bat visual impact`. The client
checks nine living vessels, all nine front-facing yaws, nine synchronized
ritual states, a crucified Unit-01, and both local triangle meshes before
writing three separately settled views:
`impact_front.png`, `impact_oblique.png`, and `impact_tiferet_close.png`. The
first proves the full glyph fits; the oblique view exposes depth/mirroring;
the close view makes the Unit-01 cross silhouette and label legibility reviewable.

Both the normal story timeline and `/seele visual impact` also emit a
server-side `Third Impact tableau audit` line. Its structural gate requires
exactly nine distinct occupied outer nodes, nine front-facing vessels and,
when present, a crucified front-facing Unit-01 centred at Tiferet. A
`valid=true` audit proves state and placement only; it is not visual approval.

The active 4,226-triangle Unit-01 mesh also has a direct offline pose sheet at
`external-assets/work/unit01-crucified-final/`: front and back show the full
horizontal cross silhouette, while the side view confirms both arms remain in
one plane rather than folding behind the torso. This passes the animation pose
offline; the complete in-game tableau remains separately blocked below.

The formal timeline is now stored per dimension in schema-v2 `SavedData`.
It records the event origin/yaw/tick, frozen RUNNING/ACCEPTED/REJECTED outcome
and each `nodeIndex -> vessel UUID`. Every vessel also stores its event UUID
and node, so recovery can adopt or de-duplicate entities after a non-atomic
world save. The timeline waits for all formation chunks plus a 20-tick entity
settle window before reconciliation or the final decision. A finite Forge
chunk ticket is acquired for every distinct Tree node chunk at start/restore
and released with the timeline, so an edge node cannot freeze the event at
tick zero. Rejected outcomes keep ageing while their idempotent UUID cleanup
retries instead of permanently occupying the dimension. Protocol v4 carries
the event UUID and `initialTreeAge`; login, respawn and dimension change resend
only the current dimension's tree, while the client advances the same tree in
place instead of restarting or merging events by origin. `/seele visual impact` remains deliberately
non-persistent. These are compiled/state contracts until the save/reload pass
above is performed in game.

The latest repository-captured full-front image is
`run/screenshots/projectseele_visual/20260713-012435/impact_front.png` and is a
visual `FAIL`: the complete red graph renders and occupies about 72% of the
frame, but its lines obscure the EVA silhouettes and the labels are not
readable at the captured resolution. A later user-provided close Tiferet view
also rejects the oversized six-ray glory because it paints a red wall behind
Unit-01. The thinner Hebrew revision above has compiled and passed the offline
composition gate but remains `BLOCKED` pending a new runtime screenshot.
Log-only facts (`massCount=9`,
`massFacingFront=9`, `crucifiedUnit01=true`) do not override that decision.

## Offline composition preview

`tools/render_tree_of_life_preview.py` provides a fast framing loop without
starting Minecraft. It parses the ten nodes and 22 paths from
`TreeOfLifeLayout.java`, parses all visible Hebrew labels and their current
role-specific scales from `ClientFxManager.java`, and parses the front-capture distance and
vertical target from `VisualCaptureManager.java`. It then projects the current
layout to a 1280x720 image, with nine front-facing vessel probes and a rigid
cross-shaped Unit-01 probe at Tiferet:

```text
python tools/render_tree_of_life_preview.py --layout current --strict
```

The ignored output directory is
`external-assets/work/tree-of-life-preview/`. It contains
`tree_of_life_front.png`, a machine-readable JSON report and a short text
report. `--fov-degrees` overrides the default 70-degree vertical-FOV
assumption; Minecraft's player FOV is an option rather than a Java source
constant. `--strict` returns a failing exit code for clipping, sub-8-pixel
labels, any label/subject collision, missing path-letter backing or an
oversized frame.

`--layout candidate` is retained as a regression reconstruction of the adopted
candidate:

```text
python tools/render_tree_of_life_preview.py --layout candidate --strict
```

The candidate has now been adopted in Java. `ClientFxManager` owns the ten
`LABEL_X_OFFSETS`, 22 `PATH_LABEL_OFFSETS`, compact Hebrew node/divine-name
rows, leader lines, role-specific microtype and a pure-red/no-shadow text contract.
`VisualCaptureManager` uses the adopted 38-block top margin. The JSON report
records these parsed values under `adopted_java_layout`; it is no longer a list
of unapplied suggestions. The `current` and `candidate` PNGs must be
pixel-identical.

The adopted current source passes the offline strict gate: all 124 emitted
Hebrew label/symbol boxes are on-screen, every row is rotated 180 degrees, there is
no detached heading row, and role-specific projected-height floors are met
(1.5–2.5 px backplate microtext, 2.25–5 px external correspondence rows,
5.5 px path letters). No label bounding
boxes collide, no label intersects any of the ten ritual-body probes, and all
22 path letters use the canonical Golden Dawn edge mapping. Text, rings and
paths are pure red with no label backdrop or shadow. At the current 180-block
capture the complete layout occupies about 34.3% of the frame width and 66.5%
of its height. The same gate also requires `EOE_INVERTED`, Keter at the nadir,
Malkuth at the crown, Tiferet at the geometric centre and exact Latin/Hebrew
index mappings. This is an offline composition pass only;
it cannot prove real mesh pose, Minecraft depth behaviour, exact vanilla-font
rasterisation or animation state. The latest real in-game image remains the
older `FAIL`, so the adopted layout is `BLOCKED` pending a fresh capture rather
than visually accepted.

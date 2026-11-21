# Project SEELE — three-stage direct-capture ordinary attack R05

Date: 2026-08-27

Status: **three independent raw ACCAD attacks are connected directly to the
active Tiger rig in the isolated Motion Lab; human approval is still required
before any normal-gameplay authority changes**.

## Body-motion contract

The body remains a direct normalized-landmark transfer. There are no authored
body poses, IK correction, physics projection, joint-limit projection, or
smoothing filters. Target limb lengths replace human limb lengths, while each
captured source joint direction and frame timing remains intact.

The three 60 Hz, 81-frame clips are:

| Motion Lab name | Raw source | Source window | Duration |
|---|---|---:|---:|
| `ordinary_attack_jab_left` | ACCAD Male2 E1 JabLeft | 18–58 | 1.3333333 s |
| `ordinary_attack_cross_right` | ACCAD Male2 E4 CrossRight | 5–45 | 1.3333333 s |
| `ordinary_attack_hook_right` | ACCAD Male2 E6 HookRight | 16–56 | 1.3333333 s |

These are separate captures, not a mirrored or time-shifted copy. Their
combined resource contains 3 clips, 50 bones, and 243 frames.

## Hand treatment

ACCAD's body landmark files do not contain finger capture. The R05 hand layer
therefore uses the DFKI Hand Motion Embodiment grasp reference (CC BY 4.0) to
hold a compact anatomical fist throughout each strike. It affects only the 26
finger bones already present in the active Tiger rig:

- the four native long digits per hand, including their existing root, tip,
  and distal joints;
- the existing native thumb root on each hand; its empty compatibility tip
  socket has no mesh and is not animated;
- no new digit, thumb segment, or detached mesh is generated.

The source thumb was previously split incorrectly: only 5 of its 15 connected
triangles followed the thumb bone, while the proximal 10 remained on the palm.
R05 reunites all 15 original triangles, places the pivot on the measured palm
seam, and rotates the rigid source thumb into a numerically solved opposition
pose against the index/middle stack. No replacement thumb geometry is added.

The body capture is not edited by this layer.

## Measured transfer checks

| Clip | Minimum source/target segment-direction dot | Maximum local 60 Hz step |
|---|---:|---:|
| left jab | 0.999923 | 23.0657° |
| right cross | 0.999923 | 28.5168° |
| right hook | 0.999923 | 20.9038° |

All clips report 50 active bones, 26 visible finger-control bones, zero manual pose
keyframes, and no IK or physics correction.

## Motion Lab review

```mcfunction
/seele motionlab reset
/seele motionlab camera
/seele motionlab demo unit01 stop
/seele motionlab demo unit01 attack_a
/seele motionlab demo unit01 attack_b
/seele motionlab demo unit01 attack_c
/seele motionlab demo unit01 attack_combo
```

- `attack_a`: left jab
- `attack_b`: right cross
- `attack_c`: right hook
- `attack_combo`: jab → cross → hook, repeated for review

These commands select isolated visual review data only. They do not replace
normal gameplay attack authority, collision, damage, or network state.

## Review artifacts

- fist close-up:
  `artifacts/motion_research/ordinary_attack_r05/FIST_R07_HAND_CLOSEUP.png`
- synchronized raw-human/EVA cross comparison:
  `artifacts/motion_research/ordinary_attack_r05/EVA_E4_RAW_HUMAN_DIRECT_RIG_R04_COMPARISON.mp4`
- combined three-clip database:
  `artifacts/motion_research/ordinary_attack_r05/EVA_ORDINARY_ATTACK_THREE_STAGE_R01.json`

# Project SEELE — Third-Party Motion Notices

This file records motion sources evaluated by the external 3D pipeline. Raw
source files and private review renders are not committed to the public mod.
Promotion into a release pack additionally requires a per-clip provenance and
QA record.

## Bandai Namco Research Motion Dataset

- Creator: Bandai Namco Research Inc.
- Official page: https://github.com/BandaiNamcoResearchInc/Bandai-Namco-Research-Motiondataset
- Licence: Creative Commons Attribution-NonCommercial 4.0 International.
- Licence text: https://creativecommons.org/licenses/by-nc/4.0/
- Shipped clip: `assets/projectseele/motion/eva_dash_r59.json`, the EVA sprint, from
  dataset-1 `dash_masculinity_001`.
- Modifications: one gait cycle resampled to 51 frames and retargeted to the
  Unit-01 rig by `tools/finale/run_retarget.py` (limb directions from the capture,
  EVA limb lengths and hinges); sideways arm flare halved, foot turn from the shin
  limited to 75 degrees, trunk leaned 8 degrees further forward, arm swing x1.4,
  leg swing x1.3.
- Non-commercial use only, which matches this project being free.

## 100STYLE Dataset

- Creators: Ian Mason, Sebastian Starke and Taku Komura.
- Official page: https://www.ianxmason.com/100style/
- Archive record: https://zenodo.org/records/8127870
- Licence: Creative Commons Attribution 4.0 International.
- Licence text: https://creativecommons.org/licenses/by/4.0/
- Local use: strict allowlist selection, official-frame trimming, coordinate
  normalization, retargeting to the Project SEELE review skeleton, contact
  detection/repair and private QA rendering.
- Modifications must be identified whenever a derived clip is distributed.

## ACCAD Open Motion Project

- Creator/attribution party: Advanced Computing Center for the Arts and
  Design, The Ohio State University.
- Official page: https://accad.osu.edu/research/motion-lab/mocap-system-and-data
- Licence: Creative Commons Attribution 3.0 Unported.
- Licence text: https://creativecommons.org/licenses/by/3.0/
- Local use: exact-package download, source inventory, evaluated-axis
  normalization, retarget experiments, contact analysis and private QA.
- Promoted R05 Longinus source: Male2 `E4 CrossRight`, using the captured
  foot load, hip/shoulder drive and recovery as a one-handed spear jab. The
  target-rig derivative adds right-palm socket contact and forward-axis
  alignment without forcing the left hand onto the shaft.
- Distributed derivatives must give appropriate credit and identify changes.

## CMU Graphics Lab Motion Capture Database

- Creator/attribution party: Carnegie Mellon University Graphics Lab.
- Official page: https://mocap.cs.cmu.edu/
- Terms evidence: https://mocap.cs.cmu.edu/faqs.php
- Terms summary: the official FAQ permits copying, modification and
  redistribution without permission and permits embedding in products, but
  prohibits directly selling the data even after format conversion.
- ML training permission is not stated expressly and remains unverified.
- Local use: exact-trial research candidates only; no whole-library ingestion.

## Cologne Motion Capture Database (CMCD)

- Creator/attribution party: Cologne Game Lab / TH Köln.
- Official page and licence: https://mocap.web.th-koeln.de/about.php
- Licence: Creative Commons Attribution 4.0 International.
- Local use: exact-frame selection from `KingKong2`, coordinate normalization,
  Tiger retargeting, target-rig constraint repair and private QA rendering.
- Distributed derivatives must retain attribution and identify modifications.

## UT Dallas Motion Capture Database

- Creator/attribution party: University of Texas at Dallas Motion Capture
  Database project.
- Archived project page:
  https://web.archive.org/web/20210919020421/http://mocaputd.com/
- Archived complete package endpoint:
  https://web.archive.org/web/20210919020421id_/http://mocaputd.com/download/prone-crawling/?wpdmdl=586
- Licence: Creative Commons Attribution 4.0 International, as stated by the
  archived project page.
- Accepted source: `MCP_prone01.fbx`, `2,862,144` bytes, SHA-256
  `df634e5921b01fb3f567ad6fea4451be4f7570309f1278a3ca26b53e6625182e`.
- Local use: FBX-to-BVH conversion, 120-to-60 Hz sampling, Tiger retargeting,
  exact root-only grounding, loop closure, transition edge matching and
  private QA rendering. Distributed derivatives must retain attribution and
  identify these changes.

## Motion-X / Motion-X++

- Creators: Jing Lin, Ailing Zeng, Shunlin Lu, Yuanhao Cai, Ruimao Zhang,
  Haoqian Wang, Lei Zhang, and the Motion-X++ authors listed by the project.
- Official project: https://motion-x-dataset.github.io/
- Official repository: https://github.com/IDEA-Research/Motion-X
- Licence: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 for the
  Motion-X material, subject to the original sub-dataset licences documented
  by the project.
- Rejected R04 candidate: `Shaolin_KungFu_Staff_Workout_Training_13_clip2.npy`,
  SHA-256 `2b6917fcc56f7347ad045c03c347f1823d83ae4be50e50915bd8074cb6292f56`.
- Local use: frames 0–43, SMPL-X body landmark extraction, Tiger retargeting
  and private QA rendering. R05 rejected the motion because it did not read as
  a forward spear thrust; it is not present in the promoted runtime action.
- Any retained research derivative remains non-commercial ShareAlike material
  and is not covered by the repository's MIT code licence.

## Quaternius Universal Animation Library 2

- Creator: Quaternius.
- Official page: https://quaternius.com/packs/universalanimationlibrary2.html
- Licence: CC0 1.0.
- Local role: import/viewer/runtime placeholder QA only. These authored,
  stylised animations are not accepted as EVA biomechanics evidence.

## Code-only architecture references

The MIT-licensed JLPM22 MotionMatching implementation may be studied or
adapted with its copyright and licence notice:
https://github.com/JLPM22/MotionMatching

Its sample motion files and the separate Environment-aware Motion Matching
dataset are not assumed to inherit the code licence. They require independent
data provenance before use.

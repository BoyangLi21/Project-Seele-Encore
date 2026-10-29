#!/usr/bin/env python3
"""Apply explicitly approved S20 semantic repair packets.

This tool is intentionally narrow.  It accepts no arbitrary packet, validates
the exact approved packet hashes and source region hashes, then applies only
the block transitions recorded in the reviewed CSV files.  The source
baseline is never opened for writing; callers must provide a fresh copied save.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from dataclasses import dataclass
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import struct
import sys
import time
import zlib

import nbtlib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from inspect_map_assets import decode_modern_section, palette_state  # noqa: E402
import survey_facility_target as survey  # noqa: E402


R01_SOURCE = (
    ROOT / "run" / "saves" / "_archive"
    / "SEELE_S20_REBUILD-post-handoff-reconcile-20260801-150700"
)
DIMENSION = Path("dimensions/projectseele/geofront")
MARKER = ".projectseele_spatial_preview_read_only.json"
SECTOR_BYTES = 4096
HEADER_BYTES = 8192

PROFILES = {
    "r01": {
        "source": R01_SOURCE,
        "approval_hash_mode": "canonical_payload",
        "source_tree_sha256": (
            "13f17ccfacd6ea3b09e0010579d32cc46a928f6ec4cfcbaea4fae303a0bd59db"
        ),
        "receipt": ".projectseele_approved_semantic_repairs_r01.json",
        "approved": {
            "S20-R02-WRONG-ROUTE-ABC-PREVIEW-r01": (
                "31150b6b7ed95bacbf9b6530ce4796c3b5451c8b32bce66e725af562d514aa20"
            ),
            "S20-R04-EAST-CORRIDOR-CORNERS-PREVIEW-r01": (
                "296cc6843a808cc58b9eec7f92f2242de68ce858e1c9b247b67ad3a505ce70eb"
            ),
            "S20-R05-OBSERVATION-B1-PREVIEW-r01": (
                "eac96e22b062be462324ad5db138859133e78ef4f6abfa230bd0142ccdbea7e4"
            ),
        },
    },
    "r06-r07": {
        "source": ROOT / "run" / "saves" / "SEELE_S20_RECOVERY_R02_R04_R05",
        "approval_hash_mode": "packet_manifest_file",
        "source_tree_sha256": None,
        "receipt": ".projectseele_approved_semantic_repairs_r06_r07.json",
        "approved": {
            "S20-R06-OBSERVATION-TO-COMMAND-PREVIEW-r01": (
                "e0ac15bc5fdbe87d6ef29aa9441fa390989f67e156ed6debd4e6c9be15917c7b"
            ),
            "S20-R07-ORPHAN-ROUTE-CLEANUP-PREVIEW-r01": (
                "b133bae241b961e5fbeafcaa07a8ff1fd4e2c45ae404ff3315a780face356eae"
            ),
        },
    },
    "r10-r12": {
        "source": ROOT / "run" / "saves" / "SEELE_S20_RECOVERY_R06_R07",
        "approval_hash_mode": "packet_manifest_payload",
        "source_tree_sha256": None,
        "receipt": ".projectseele_approved_semantic_repairs_r10_r12.json",
        "approved": {
            "S20-R10-COMMAND-LIFT-RELOCATION-PREVIEW-r01": (
                "a9b2aefbe3dcde117c613e0e1d46222f4bd14c4b529e8aa796eae2789d3bdf4f"
            ),
            "S20-R11-OBSERVATION-HANGAR-LIFT-PREVIEW-r01": (
                "748d32032326bdfe642c930608748c447be0a426a8504626f5e9ab7934e11e81"
            ),
            "S20-R12-THREE-LAUNCH-WELL-ADDITIVE-RESTORE-PREVIEW-r01": (
                "fd7eac28d08053491e623de907cf5ea76a8adadd8799ad7de0746de0ec9f4103"
            ),
        },
    },
    "r13": {
        # The human approved the exact R13 voxel transition set, then made
        # unrelated in-game corridor edits in the same Anvil region.  Keep
        # those edits as the source baseline and rebase only when every
        # approved CSV `before` state still matches byte-decoded world data.
        "source": ROOT / "run" / "saves" / "SEELE_S20_RECOVERY_R10_R12",
        "approval_hash_mode": "canonical_payload",
        "allow_region_rebase": True,
        "source_tree_sha256": None,
        "receipt": ".projectseele_approved_semantic_repairs_r13.json",
        "approved": {
            "S20-R13-COMMAND-HIERARCHY-SOURCE-RESTORE-PREVIEW-r01": (
                "e12cf2c04e5a3a7fbd8b9339039561b07f309161c2341efa797faf15762c7172"
            ),
        },
    },
    "r14-r16": {
        # R14-R16 were rendered from R13 before the human made a few further
        # in-game lift-shaft corrections.  Rebase is allowed only at the
        # region-file level: rewrite_region still requires every approved CSV
        # `before` state to match the freshly saved human baseline exactly.
        # Any overlapping manual edit therefore fails closed instead of being
        # overwritten.
        "source": ROOT / "run" / "saves" / "SEELE_S20_RECOVERY_R13",
        "approval_hash_mode": "canonical_payload",
        "allow_region_rebase": True,
        "source_tree_sha256": None,
        "receipt": ".projectseele_approved_semantic_repairs_r14_r16.json",
        "approved": {
            "S20-R14-CORRECT-OBSERVATION-HANGAR-LIFT-PREVIEW-r01": (
                "42f13b0f4cc0b6a143e1cf9a8302a146857009d0a4d24f74a2dd47c928b77975"
            ),
            "S20-R15-ROLLBACK-WRONG-WEST-LIFT-PREVIEW-r01": (
                "85cd02fc87e0d1031c467f85501af0d335a368e2759b755248d878de9ba89508"
            ),
            "S20-R16-THREE-LAUNCH-WELL-WALK-DECKS-PREVIEW-r01": (
                "1abba6ba7b2f9487473bf5db4d6d00493c7e267699eca70f99ef2cb4dda9ba9c"
            ),
        },
    },
    "r17": {
        # R17 was rendered before the human performed the next in-game
        # inspection.  Region-level rebasing is allowed, but rewrite_region
        # still checks all 6,235 approved `before` states against the freshly
        # saved world and rejects any overlapping manual edit.
        "source": ROOT / "run" / "saves" / "SEELE_S20_RECOVERY_R14_R16",
        "approval_hash_mode": "canonical_payload",
        "allow_region_rebase": True,
        "source_tree_sha256": None,
        "receipt": ".projectseele_approved_semantic_repairs_r17.json",
        "approved": {
            "S20-R17-COMMAND-AUTHORED-ENCLOSURE-PREVIEW-r01": (
                "d83b909d75067f6c4635f21603d350e9b636c280f70cd99a6b2c30b22007b8ff"
            ),
        },
    },
    "r18-r20": {
        # R18 and R20 were explicitly approved together; R19 was rejected and
        # must never be included in this profile.  The live R17 save may carry
        # unrelated human edits, so each approved CSV before-state remains the
        # fail-closed rebase authority.
        "source": ROOT / "run" / "saves" / "SEELE_S20_RECOVERY_R17",
        "approval_hash_mode": "canonical_payload",
        "allow_region_rebase": True,
        "source_tree_sha256": None,
        "receipt": ".projectseele_approved_semantic_repairs_r18_r20.json",
        "approved": {
            "S20-R18-COMMAND-LIFT-MEASURED-ENDPOINT-PREVIEW-r01": (
                "05ee8c2c38d8a90497076b01375b716f252588d17d80e608936a88f0141a1b6a"
            ),
            "S20-R20-NORTH-PERIPHERY-RESIDUE-PREVIEW-r01": (
                "edae03aef18f85a86c27e17d8053b0de67da793760c04d6be7a30d8292990a39"
            ),
        },
    },
    "r21-r22": {
        # R21 and R22 were explicitly approved together.  R23 is excluded:
        # the human requested a fully closed command front wall, so its r01
        # geometry must be superseded by a newly rendered packet/hash.
        "source": ROOT / "run" / "saves" / "SEELE_S20_RECOVERY_R18_R20",
        "approval_hash_mode": "canonical_payload",
        "allow_region_rebase": True,
        "source_tree_sha256": None,
        "receipt": ".projectseele_approved_semantic_repairs_r21_r22.json",
        "approved": {
            "S20-R21-PYRAMID-SLOPE-BOX-RESTORE-PREVIEW-r01": (
                "c46f87129683d35398a4653e04d6ba12df21ee63c8ed8e976c23424a5fd0a700"
            ),
            "S20-R22-TOKYO3-TWO-CONFLICT-TOWERS-PREVIEW-r01": (
                "b5ee706a153bd8a5872ee3168ad34a868cb55b86f7d4d1353c9581616f7e1ffc"
            ),
        },
    },
    "r23": {
        # R23-r02 supersedes the unapproved r01 packet.  It is based on the
        # already applied R21/R22 world and includes the two measured upper
        # front-wall seams requested by the human.
        "source": ROOT / "run" / "saves" / "SEELE_S20_RECOVERY_R21_R22",
        "approval_hash_mode": "canonical_payload",
        "allow_region_rebase": True,
        "source_tree_sha256": None,
        "receipt": ".projectseele_approved_semantic_repairs_r23.json",
        "approved": {
            "S20-R23-COMMAND-WALL-CONTROLS-CLEAR-GLASS-PREVIEW-r02": (
                "24265cfe04a7f0aa9f12ff93f91c3c077be9043a8727e3c52b7c05178926ada1"
            ),
        },
    },
    "r24-r25": {
        # R24/R25 were rendered against the current human-edited R23 save.
        # Apply only the approved material substitutions on a fresh copy;
        # all command-dais geometry and controls remain human-authored.
        "source": ROOT / "run" / "saves" / "SEELE_S20_RECOVERY_R23",
        "approval_hash_mode": "canonical_payload",
        "allow_region_rebase": True,
        "source_tree_sha256": None,
        "receipt": ".projectseele_approved_semantic_repairs_r24_r25.json",
        "approved": {
            "S20-R24-COMMAND-FRONT-CLEAR-GLASS-PREVIEW-r01": (
                "53813c6d10df29fdc30fa18d3c79b72f9e2439312718f94b52423a4c69558d63"
            ),
            "S20-R25-HANGAR-OBSERVATION-CLEAR-GLASS-PREVIEW-r01": (
                "df46df0c59d457ceba753f048b6401e6edc5e4f2e593e9a066ad1a24d53cdec3"
            ),
        },
    },
    "r28": {
        # The command-room MAGI are the sole canonical trio.  R28 removes
        # only the exact source-generated duplicate sculptures in the deep
        # lab, preserving its shell, floor, shaft and every accepted route.
        "source": ROOT / "run" / "saves" / "SEELE_S20_RECOVERY_R24_R25",
        "approval_hash_mode": "packet_manifest_file_unordered",
        "allow_region_rebase": True,
        "source_tree_sha256": None,
        "receipt": ".projectseele_approved_semantic_repairs_r28.json",
        "approved": {
            "S20-R28-RETIRE-DUPLICATE-DEEP-MAGI-PREVIEW-r01": (
                "f586e4fed79530f64f318e4e245d7d2971efadc5a6fde62299029afad1df1466"
            ),
        },
    },
    "r30-r02-b1-preview": {
        # R30-r02 deliberately starts from immutable R28 and is applied only
        # to a disposable visual-review clone.  Unlike the revoked five-floor
        # R30, this packet owns one supported 745-voxel vestibule, changes air
        # only and removes/replaces no baseline block.
        "source": ROOT / "run" / "saves" / "SEELE_S20_RECOVERY_R28",
        "approval_hash_mode": "canonical_payload",
        "allow_region_rebase": False,
        "source_tree_sha256": None,
        "receipt": ".projectseele_preview_r30_r02_b1.json",
        "approved": {
            "S20-R30-r02-B1-SECURITY-VESTIBULE-PREVIEW-r01": (
                "fca5b9d5c37ff8819641f4d9e56ea16fc8a1678f0fc6541cc9c7de68fc217cbe"
            ),
        },
    },
    "r30-r02-b2-preview": {
        # B2 is reviewed only on top of the disposable B1 visual clone.  It
        # reuses the measured floor and existing side walls, adding a single
        # supported service vestibule without removing baseline voxels.
        "source": ROOT / "run" / "saves" / "SEELE_S20_R30_R02_B1_VISUAL",
        "approval_hash_mode": "canonical_payload",
        "allow_region_rebase": False,
        "source_tree_sha256": None,
        "receipt": ".projectseele_preview_r30_r02_b2.json",
        "approved": {
            "S20-R30-r02-B2-SERVICE-VESTIBULE-PREVIEW-r01": (
                "b2bc9209a1c2fc2275b97a15f98a97b225d2128d4cb6f6c0b06e5a8f4e69984d"
            ),
        },
    },
    "r30-r02-b3-preview": {
        # B3 is the first shared personnel node and is valid only on top of
        # the disposable B1+B2 clone.  It preserves both reviewed handoffs,
        # uses the existing floor and adds no remote or floating structure.
        "source": ROOT / "run" / "saves" / "SEELE_S20_R30_R02_B1_B2_VISUAL",
        "approval_hash_mode": "canonical_payload",
        "allow_region_rebase": False,
        "source_tree_sha256": None,
        "receipt": ".projectseele_preview_r30_r02_b3.json",
        "approved": {
            "S20-R30-r02-B3-PERSONNEL-JUNCTION-PREVIEW-r01": (
                "66afd39bf13aac12ea79d55ea6177055bddd411285e2ac51720b3192334b51de"
            ),
        },
    },
    "r30": {
        # R30 is the first regional construction packet based directly on the
        # preserved R28 authority.  Keep it as its own transaction so a later
        # dependent packet cannot hide a failed before-state check.
        "source": ROOT / "run" / "saves" / "SEELE_S20_RECOVERY_R28",
        "approval_hash_mode": "packet_manifest_file",
        "accepted_modes": {
            "READ_ONLY_IN_MEMORY_EXACT_VOXEL_PREVIEW",
        },
        "allow_region_rebase": True,
        "source_tree_sha256": None,
        "receipt": ".projectseele_approved_semantic_repairs_r30.json",
        "approved": {
            "S20-R30-PYRAMID-INFILL-AND-FLOWS-PREVIEW-r01": (
                "394f0aca095f567a682c886ecf935fe4eba0ab067ded909663aac51c2ef2ef3c"
            ),
        },
    },
    "r31-r02": {
        # R31-r02 was rendered against virtual R28 + R30.  Region hashes may
        # therefore differ after R30, but every chained CSV before-state must
        # match exactly before this transaction is allowed to write.
        "source": ROOT / "run" / "saves" / "SEELE_S20_RECOVERY_R28",
        "approval_hash_mode": "packet_manifest_file",
        "accepted_modes": {
            "READ_ONLY_VIRTUAL_R28_PLUS_R30_EXACT_VOXEL_PREVIEW",
        },
        "required_receipts": {
            ".projectseele_approved_semantic_repairs_r30.json",
        },
        "allow_region_rebase": True,
        "source_tree_sha256": None,
        "receipt": ".projectseele_approved_semantic_repairs_r31_r02.json",
        "approved": {
            "S20-R31-DEEP-ACCESS-INTERFACE-PREVIEW-r02": (
                "655065af2259579e2143d3d19820bd6b63b463d352f62c889dcc1bd0b855afc4"
            ),
        },
    },
    "r32": {
        # R32 was rendered against virtual R28 + R30 + R31-r02 and is applied
        # only after both receipts exist on the same cloned destination.
        "source": ROOT / "run" / "saves" / "SEELE_S20_RECOVERY_R28",
        "approval_hash_mode": "packet_manifest_file",
        "accepted_modes": {
            "READ_ONLY_VIRTUAL_R28_PLUS_R30_PLUS_R31_EXACT_VOXEL_PREVIEW",
        },
        "required_receipts": {
            ".projectseele_approved_semantic_repairs_r30.json",
            ".projectseele_approved_semantic_repairs_r31_r02.json",
        },
        "allow_region_rebase": True,
        "source_tree_sha256": None,
        "receipt": ".projectseele_approved_semantic_repairs_r32.json",
        "approved": {
            "S20-R32-H01-PUBLIC-INTERCHANGE-PREVIEW-r01": (
                "6088e54c4b7083b58b991093e0941a784252004fd2b3196be25ac61fdcbb8271"
            ),
        },
    },
    "s21-b1": {
        # First independently shippable S21 breakpoint. r01 was visually
        # rejected because one aperture cell had no floor. r02 is rendered
        # from frozen R28, adds that single supported footing, and removes the
        # same two guarded obstruction voxels into a fresh destination copy.
        "source": ROOT / "run" / "saves" / "SEELE_S20_RECOVERY_R28",
        "approval_hash_mode": "canonical_payload",
        "allow_region_rebase": False,
        "source_tree_sha256": None,
        "receipt": ".projectseele_s21_command_rear_b1_r02.json",
        "approved": {
            "S21-COMMAND-REAR-B1-N2-N5-PREVIEW-r02": (
                "01c75269bc62731d8b940cab8f5336d0697e5ff26513d2e564d3903689976274"
            ),
        },
    },
    "s21-b1-b2": {
        # Fresh cumulative preview from immutable R28.  Each packet remains
        # independently sealed; no broad region rebase is permitted.
        "source": ROOT / "run" / "saves" / "SEELE_S20_RECOVERY_R28",
        "approval_hash_mode": "canonical_payload",
        "allow_region_rebase": False,
        "source_tree_sha256": None,
        "receipt": ".projectseele_s21_command_rear_b1_b2.json",
        "approved": {
            "S21-COMMAND-REAR-B1-N2-N5-PREVIEW-r02": (
                "01c75269bc62731d8b940cab8f5336d0697e5ff26513d2e564d3903689976274"
            ),
            "S21-COMMAND-REAR-B2-N2-N4-PREVIEW-r02": (
                "179b7977af7119a2e05229ab6b5843aae4b7114ea17729970be2a58e9c3204c7"
            ),
        },
    },
    "s21-rear-complete": {
        # Four independently sealed rear-circulation breakpoints, composed
        # only onto immutable R28. B3 opens the measured ladder/stair landing;
        # B4 adds the three-block, laterally anchored maintenance crossing.
        "source": ROOT / "run" / "saves" / "SEELE_S20_RECOVERY_R28",
        "approval_hash_mode": "canonical_payload",
        "allow_region_rebase": False,
        "source_tree_sha256": None,
        "receipt": ".projectseele_s21_command_rear_complete.json",
        "approved": {
            "S21-COMMAND-REAR-B1-N2-N5-PREVIEW-r02": (
                "01c75269bc62731d8b940cab8f5336d0697e5ff26513d2e564d3903689976274"
            ),
            "S21-COMMAND-REAR-B2-N2-N4-PREVIEW-r02": (
                "179b7977af7119a2e05229ab6b5843aae4b7114ea17729970be2a58e9c3204c7"
            ),
            "S21-COMMAND-REAR-B3-N3-N2-PREVIEW-r02": (
                "ac5d79dcf6468d5170b63da9475824cbbe7403a9d8e110f6ca2be0b2696a0323"
            ),
            "S21-COMMAND-REAR-B4-N1-N3-PREVIEW-r02": (
                "11655a8e63330ef4a25681caf62d61bdea19631b0684aec984ceadf8a0ffe861"
            ),
        },
    },
}

# Human visual review revoked these packets after they damaged the spatial
# contract of the R28 baseline.  Keep their profile metadata only as forensic
# provenance; the apply entry point must never accept them again, even if an
# old receipt or approval hash is present on disk.
REVOKED_PROFILES = {
    "r30-r02-b1-preview": (
        "revoked 2026-08-06: semantic location was misclassified; the packet "
        "added an unauthorised room inside the command-centre volume"
    ),
    "r30-r02-b2-preview": (
        "revoked 2026-08-06: depends on rejected B1 and added another "
        "unauthorised room inside the command-centre volume"
    ),
    "r30-r02-b3-preview": (
        "revoked 2026-08-06: depends on rejected B1/B2 and extended the same "
        "semantically invalid command-centre infill"
    ),
    "r30": (
        "revoked 2026-08-06: open air was treated as buildable volume; "
        "packet 394f0aca... is forensic-only"
    ),
    "r31-r02": (
        "revoked 2026-08-06: depends on revoked R30 and severed an existing "
        "corridor; packet 655065af... is forensic-only"
    ),
    "r32": (
        "revoked 2026-08-06: depends on revoked R30/R31 and failed the "
        "interchange review; packet 6088e54c... is forensic-only"
    ),
}


@dataclass(frozen=True)
class Change:
    packet: str
    x: int
    y: int
    z: int
    before: str
    after: str
    kind: str
    reason: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def packet_sha(directory: Path) -> str:
    rows = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name != "packet.sha256":
            rows.append(
                f"{sha256_file(path)}  "
                f"{path.relative_to(directory).as_posix()}"
            )
    return hashlib.sha256(("\n".join(rows) + "\n").encode("ascii")).hexdigest()


def packet_manifest_file_sha(directory: Path) -> str:
    """Validate every manifest entry, then hash the approved manifest file.

    ``Path.write_text`` uses CRLF on Windows, so the on-disk manifest hash is
    intentionally distinct from the canonical LF payload hash returned by
    :func:`packet_sha`.  R06/R07 were explicitly approved by the former.
    """
    manifest_path = directory / "packet.sha256"
    actual_rows = manifest_path.read_text(encoding="ascii").splitlines()
    expected_rows = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name != "packet.sha256":
            expected_rows.append(
                f"{sha256_file(path)}  "
                f"{path.relative_to(directory).as_posix()}"
            )
    if actual_rows != expected_rows:
        raise RuntimeError(f"packet manifest contents are stale: {directory}")
    return sha256_file(manifest_path)


def packet_manifest_file_sha_unordered(directory: Path) -> str:
    """Validate a complete sealed manifest whose generator sorted case-folded.

    R28 was reviewed by the SHA-256 of ``packet.sha256`` itself.  Its Windows
    generator placed ``README.md`` before ``block_diff.csv``; file order has
    no write semantics, but every listed path and byte hash remains sealed.
    """
    manifest_path = directory / "packet.sha256"
    actual_rows = manifest_path.read_text(encoding="ascii").splitlines()
    expected_rows = [
        f"{sha256_file(path)}  {path.relative_to(directory).as_posix()}"
        for path in directory.rglob("*")
        if path.is_file() and path.name != "packet.sha256"
    ]
    if len(actual_rows) != len(set(actual_rows)) \
            or set(actual_rows) != set(expected_rows):
        raise RuntimeError(f"packet manifest contents are stale: {directory}")
    return sha256_file(manifest_path)


def packet_manifest_payload_sha(directory: Path) -> str:
    """Validate and hash the exact manifest payload shown for approval.

    R10/R11 add an endpoint walkspace board after the immutable APPLY packet
    is sealed.  That board is human-facing evidence only; it cannot influence
    Anvil writes.  Every sealed file (especially ``00_manifest.json`` and
    ``block_diff.csv``) must still match the approved manifest byte-for-byte,
    and no other unsealed file is accepted.
    """
    manifest_path = directory / "packet.sha256"
    actual_rows = manifest_path.read_text(encoding="ascii").splitlines()
    allowed_evidence = {"08_endpoint_walkspace.png"}
    sealed_paths = []
    extra_paths = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.name == "packet.sha256":
            continue
        relative = path.relative_to(directory).as_posix()
        if relative in allowed_evidence:
            extra_paths.append(relative)
        else:
            sealed_paths.append(path)
    expected_rows = [
        f"{sha256_file(path)}  {path.relative_to(directory).as_posix()}"
        for path in sealed_paths
    ]
    if actual_rows != expected_rows:
        raise RuntimeError(f"packet manifest contents are stale: {directory}")
    unexpected = set(extra_paths) - allowed_evidence
    if unexpected:
        raise RuntimeError(
            f"unexpected unsealed packet evidence: {sorted(unexpected)}"
        )
    payload = "\n".join(actual_rows) + "\n"
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def load_packets(packet_root: Path, approved: dict[str, str],
                 source_name: str, hash_mode: str,
                 accepted_modes: set[str] | None = None
                 ) -> tuple[list[Change], dict, list[dict]]:
    changes: list[Change] = []
    expected_regions: dict[str, str] = {}
    manifests: list[dict] = []
    occupied: dict[tuple[int, int, int], Change] = {}
    for repair_id, approved_sha in approved.items():
        directory = packet_root / repair_id
        if hash_mode == "canonical_payload":
            actual_sha = packet_sha(directory)
        elif hash_mode == "packet_manifest_file":
            actual_sha = packet_manifest_file_sha(directory)
        elif hash_mode == "packet_manifest_file_unordered":
            actual_sha = packet_manifest_file_sha_unordered(directory)
        elif hash_mode == "packet_manifest_payload":
            actual_sha = packet_manifest_payload_sha(directory)
        else:
            raise RuntimeError(f"unsupported approval hash mode: {hash_mode}")
        if actual_sha != approved_sha:
            raise RuntimeError(
                f"packet hash mismatch for {repair_id}: "
                f"expected {approved_sha}, got {actual_sha}"
            )
        manifest = json.loads(
            (directory / "00_manifest.json").read_text(encoding="utf-8")
        )
        if manifest.get("repair_id") != repair_id:
            raise RuntimeError(f"repair id mismatch in {directory}")
        modes = accepted_modes or {"READ_ONLY_IN_MEMORY_PREVIEW"}
        if manifest.get("mode") not in modes:
            raise RuntimeError(f"unexpected preview mode for {repair_id}")
        if manifest.get("world_files_written") is not False:
            raise RuntimeError(f"preview provenance is not read-only: {repair_id}")
        manifest_source = manifest.get(
            "source_save", manifest.get("source_world")
        )
        if manifest_source != source_name:
            raise RuntimeError(
                f"source save mismatch for {repair_id}: expected "
                f"{source_name}, got {manifest_source}"
            )
        for name, digest in manifest.get("region_file_hashes", {}).items():
            old = expected_regions.setdefault(name, digest)
            if old != digest:
                raise RuntimeError(f"conflicting source hash for {name}")
        packet_changes: list[Change] = []
        with (directory / "block_diff.csv").open(
                "r", encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                change = Change(
                    repair_id, int(row["x"]), int(row["y"]), int(row["z"]),
                    row["before"], row["after"], row["change"], row["reason"]
                )
                key = (change.x, change.y, change.z)
                prior = occupied.get(key)
                if prior is not None and (
                        prior.before != change.before or prior.after != change.after):
                    raise RuntimeError(
                        f"approved packets conflict at {key}: "
                        f"{prior.packet} vs {change.packet}"
                    )
                occupied[key] = change
                packet_changes.append(change)
        if len(packet_changes) != int(manifest["changed_blocks"]):
            raise RuntimeError(f"CSV count mismatch for {repair_id}")
        changes.extend(packet_changes)
        manifests.append(manifest)
    return changes, expected_regions, manifests


def parse_state(state: str) -> nbtlib.Compound:
    if "[" not in state:
        return nbtlib.Compound({"Name": nbtlib.String(state)})
    name, raw = state[:-1].split("[", 1)
    properties = {}
    for item in raw.split(","):
        key, value = item.split("=", 1)
        properties[key] = nbtlib.String(value)
    return nbtlib.Compound({
        "Name": nbtlib.String(name),
        "Properties": nbtlib.Compound(properties),
    })


def encode_indices(indices: np.ndarray, palette_size: int) -> nbtlib.LongArray:
    bits = max(4, (palette_size - 1).bit_length())
    per_long = 64 // bits
    packed = [0] * math.ceil(4096 / per_long)
    for index, value in enumerate(indices.tolist()):
        slot = index // per_long
        shift = (index % per_long) * bits
        packed[slot] |= int(value) << shift
    signed = [value if value < (1 << 63) else value - (1 << 64)
              for value in packed]
    return nbtlib.LongArray(signed)


def decompress_chunk(compression: int, payload: bytes) -> bytes:
    if compression == 1:
        return gzip.decompress(payload)
    if compression == 2:
        return zlib.decompress(payload)
    if compression == 3:
        return payload
    raise ValueError(f"unsupported region compression {compression}")


def chunk_blob(root: nbtlib.File) -> bytes:
    output = io.BytesIO()
    root.write(output)
    payload = zlib.compress(output.getvalue(), level=6)
    length = len(payload) + 1
    return struct.pack(">I", length) + b"\x02" + payload


def section_for(root: nbtlib.File, section_y: int):
    for section in root.get("sections", []):
        if int(section["Y"]) == section_y:
            return section
    return None


def local_index(change: Change) -> int:
    return (change.y & 15) * 256 + (change.z & 15) * 16 + (change.x & 15)


def apply_chunk(root: nbtlib.File, chunk_changes: list[Change],
                removable_block_entities: set[tuple[int, int, int]] | None = None
                ) -> None:
    block_entities = {
        (int(entry.get("x", 0)), int(entry.get("y", 0)), int(entry.get("z", 0)))
        for entry in root.get("block_entities", [])
    }
    touched = {(c.x, c.y, c.z) for c in chunk_changes}
    overlap = touched & block_entities
    allowed_removals = removable_block_entities or set()
    forbidden_overlap = overlap - allowed_removals
    if forbidden_overlap:
        raise RuntimeError(
            f"approved diff touches block entities: {sorted(forbidden_overlap)}")
    if overlap:
        # Opt-in only.  The default remains fail-closed; a caller may remove
        # an explicitly enumerated natural worldgen block entity after it has
        # inspected both the coordinate and the block state.  Authored/runtime
        # devices are never accepted through this path.
        kept = [entry for entry in root.get("block_entities", [])
                if (int(entry.get("x", 0)), int(entry.get("y", 0)),
                    int(entry.get("z", 0))) not in overlap]
        root["block_entities"] = nbtlib.List[nbtlib.Compound](kept)

    by_section: dict[int, list[Change]] = defaultdict(list)
    for change in chunk_changes:
        by_section[change.y // 16].append(change)

    for section_y, section_changes in by_section.items():
        section = section_for(root, section_y)
        if section is None:
            raise RuntimeError(f"missing section y={section_y}")
        block_states = section.get("block_states")
        if block_states is None:
            raise RuntimeError(f"missing block_states at section y={section_y}")
        palette, decoded = decode_modern_section(section)
        if not palette:
            raise RuntimeError(f"empty palette at section y={section_y}")
        indices = np.asarray(decoded, dtype=np.int32).copy()
        original = indices.copy()
        state_to_index = {
            palette_state(entry): index for index, entry in enumerate(palette)
        }

        expected_indices = set()
        for change in section_changes:
            index = local_index(change)
            current = palette_state(palette[int(indices[index])])
            # Preserve a newer human/runtime edit when it already equals the
            # explicitly approved final state.  Any third state still fails
            # closed below; this is idempotent satisfaction, not a wildcard
            # rebase or permission to overwrite manual work.
            if current == change.after:
                continue
            if current != change.before:
                raise RuntimeError(
                    f"source mismatch at {(change.x, change.y, change.z)}: "
                    f"expected {change.before}, got {current}"
                )
            expected_indices.add(index)
            target = state_to_index.get(change.after)
            if target is None:
                target = len(palette)
                palette.append(parse_state(change.after))
                state_to_index[change.after] = target
            indices[index] = target

        actual_indices = set(np.flatnonzero(indices != original).tolist())
        if actual_indices != expected_indices:
            raise RuntimeError(
                f"section semantic delta mismatch at y={section_y}: "
                f"expected {len(expected_indices)}, got {len(actual_indices)}"
            )
        block_states["palette"] = nbtlib.List[nbtlib.Compound](palette)
        if len(palette) == 1:
            block_states.pop("data", None)
        else:
            block_states["data"] = encode_indices(indices, len(palette))

    # The approved geometry moves light-emitting floor blocks.  Mark only the
    # touched chunks for vanilla's light engine to rebuild on first load.
    root["isLightOn"] = nbtlib.Byte(0)


def rewrite_region(path: Path,
                   changes_by_chunk: dict[tuple[int, int], list[Change]],
                   removable_block_entities: set[tuple[int, int, int]] | None = None,
                   block_entity_additions: dict[tuple[int, int, int], nbtlib.Compound] | None = None,
                   surface_rebuild: bool = False
                   ) -> bytes:
    source = path.read_bytes()
    if len(source) < HEADER_BYTES:
        raise RuntimeError(f"truncated region header: {path}")
    parts = path.stem.split(".")
    region_x, region_z = int(parts[1]), int(parts[2])
    timestamps = source[SECTOR_BYTES:HEADER_BYTES]
    chunks: list[bytes | None] = [None] * 1024
    seen_chunks: set[tuple[int, int]] = set()

    for index in range(1024):
        location = source[index * 4:index * 4 + 4]
        sector_offset = int.from_bytes(location[:3], "big")
        sector_count = location[3]
        if sector_offset == 0 or sector_count == 0:
            continue
        byte_offset = sector_offset * SECTOR_BYTES
        if byte_offset + 5 > len(source):
            raise RuntimeError(f"chunk {index} points beyond {path.name}")
        length = struct.unpack(">I", source[byte_offset:byte_offset + 4])[0]
        if length <= 1 or length + 4 > sector_count * SECTOR_BYTES:
            raise RuntimeError(f"invalid chunk length at {path.name}:{index}")
        compression = source[byte_offset + 4]
        if compression & 0x80:
            raise RuntimeError(f"external chunk stream at {path.name}:{index}")
        original_blob = source[byte_offset:byte_offset + 4 + length]
        chunk_x = region_x * 32 + index % 32
        chunk_z = region_z * 32 + index // 32
        selected = changes_by_chunk.get((chunk_x, chunk_z))
        if selected:
            payload = source[byte_offset + 5:byte_offset + 4 + length]
            root = nbtlib.File.parse(io.BytesIO(
                decompress_chunk(compression, payload)
            ))
            if int(root.get("xPos", chunk_x)) != chunk_x \
                    or int(root.get("zPos", chunk_z)) != chunk_z:
                raise RuntimeError(f"chunk coordinate mismatch at {chunk_x},{chunk_z}")
            apply_chunk(root, selected, removable_block_entities)
            if surface_rebuild:
                root.pop('Heightmaps', None)
                root.pop('isLightOn', None)
                root.pop('starlight.light_version', None)
                for section in root.get('sections', []):
                    for key in ('BlockLight', 'SkyLight', 'starlight.blocklight_state', 'starlight.skylight_state'):
                        section.pop(key, None)
            additions = {pos: entry for pos, entry in (block_entity_additions or {}).items()
                         if pos[0] >> 4 == chunk_x and pos[2] >> 4 == chunk_z}
            if additions:
                touched = {(c.x,c.y,c.z) for c in selected}
                existing = list(root.get("block_entities", []))
                occupied = {(int(e["x"]),int(e["y"]),int(e["z"])) for e in existing}
                for pos, entry in additions.items():
                    if pos not in touched or pos in occupied:
                        raise RuntimeError(f"unowned or occupied block-entity addition: {pos}")
                    if tuple(int(entry[a]) for a in ("x","y","z")) != pos:
                        raise RuntimeError(f"block-entity position mismatch: {pos}")
                    existing.append(entry)
                root["block_entities"] = nbtlib.List[nbtlib.Compound](existing)
            chunks[index] = chunk_blob(root)
            seen_chunks.add((chunk_x, chunk_z))
        else:
            chunks[index] = original_blob

    missing = set(changes_by_chunk) - seen_chunks
    if missing:
        raise RuntimeError(f"missing changed chunks in {path.name}: {sorted(missing)}")

    locations = bytearray(SECTOR_BYTES)
    body = bytearray()
    next_sector = 2
    for index, blob in enumerate(chunks):
        if blob is None:
            continue
        sectors = math.ceil(len(blob) / SECTOR_BYTES)
        if sectors > 255 or next_sector >= 1 << 24:
            raise RuntimeError(f"region allocation overflow in {path.name}")
        locations[index * 4:index * 4 + 3] = next_sector.to_bytes(3, "big")
        locations[index * 4 + 3] = sectors
        body.extend(blob)
        body.extend(b"\x00" * (sectors * SECTOR_BYTES - len(blob)))
        next_sector += sectors
    return bytes(locations) + timestamps + bytes(body)


def atomic_replace(path: Path, content: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".approved-r01.tmp")
    with temporary.open("wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def verify_final(save: Path, changes: list[Change], manifests: list[dict]) -> None:
    world = save / DIMENSION
    by_packet: dict[str, list[Change]] = defaultdict(list)
    for change in changes:
        by_packet[change.packet].append(change)
    for manifest in manifests:
        packet = manifest["repair_id"]
        box = manifest.get("box", manifest.get("context_box"))
        if box is None:
            raise RuntimeError(f"packet has no verification box: {packet}")
        volume = survey.Volume(world, tuple(box))
        for change in by_packet[packet]:
            current = volume.state(change.x - volume.x0,
                                   change.y - volume.y0,
                                   change.z - volume.z0)
            if current != change.after:
                raise RuntimeError(
                    f"post-write mismatch at {(change.x, change.y, change.z)}: "
                    f"expected {change.after}, got {current}"
                )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", type=Path, required=True,
                        help="Fresh copied destination save; never the archive")
    parser.add_argument("--packet-root", type=Path,
                        default=ROOT / "artifacts" / "map_previews")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="r01")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    revoked_reason = REVOKED_PROFILES.get(args.profile)
    if revoked_reason is not None:
        raise SystemExit(f"profile {args.profile} is permanently disabled: "
                         f"{revoked_reason}")

    profile = PROFILES[args.profile]
    approved: dict[str, str] = profile["approved"]
    save = args.save.resolve()
    source = profile["source"].resolve()
    if save == source or source in save.parents:
        raise RuntimeError("refusing to write the recovery source archive")
    saves_root = (ROOT / "run" / "saves").resolve()
    if saves_root not in save.parents:
        raise RuntimeError(f"destination is outside {saves_root}")
    if not (save / "level.dat").is_file():
        raise RuntimeError(f"destination is not a Minecraft save: {save}")
    if not (save / MARKER).is_file():
        raise RuntimeError(f"runtime writer freeze marker is missing: {MARKER}")
    receipt_path = save / profile["receipt"]
    if receipt_path.exists():
        raise RuntimeError(f"repair receipt already exists: {receipt_path}")
    for required in profile.get("required_receipts", set()):
        required_path = save / required
        if not required_path.is_file():
            raise RuntimeError(
                f"required prior repair receipt is missing: {required_path}"
            )

    changes, expected_regions, manifests = load_packets(
        args.packet_root.resolve(), approved, source.name,
        profile["approval_hash_mode"], profile.get("accepted_modes")
    )
    region_dir = save / DIMENSION / "region"
    actual_source_regions = {}
    rebased_regions = {}
    for name, expected in expected_regions.items():
        actual = sha256_file(region_dir / name)
        actual_source_regions[name] = actual
        if actual != expected:
            if not profile.get("allow_region_rebase", False):
                raise RuntimeError(
                    f"baseline region hash mismatch for {name}: "
                    f"expected {expected}, got {actual}"
                )
            rebased_regions[name] = {
                "approvedPreview": expected,
                "currentHumanBaseline": actual,
            }

    by_region: dict[str, dict[tuple[int, int], list[Change]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for change in changes:
        chunk_x, chunk_z = change.x // 16, change.z // 16
        region_name = f"r.{chunk_x // 32}.{chunk_z // 32}.mca"
        by_region[region_name][(chunk_x, chunk_z)].append(change)

    rewritten: dict[Path, bytes] = {}
    originals: dict[Path, bytes] = {}
    for name, chunk_changes in sorted(by_region.items()):
        path = region_dir / name
        originals[path] = path.read_bytes()
        rewritten[path] = rewrite_region(path, chunk_changes)

    print(
        f"validated packets={len(approved)} changes={len(changes)} "
        f"regions={len(rewritten)} destination={save.name}"
    )
    if not args.apply:
        print("VERIFY ONLY: no world files written")
        return

    replaced: list[Path] = []
    try:
        for path, content in rewritten.items():
            atomic_replace(path, content)
            replaced.append(path)
        verify_final(save, changes, manifests)
    except Exception:
        for path in replaced:
            atomic_replace(path, originals[path])
        raise

    after_regions = {
        path.name: sha256_file(path) for path in sorted(rewritten)
    }
    receipt = {
        "status": "APPLIED_AND_READ_BACK_VERIFIED",
        "sourceBaseline": str(profile["source"].relative_to(ROOT)),
        "sourceTreeSha256": profile["source_tree_sha256"],
        "destination": save.name,
        "dimension": DIMENSION.as_posix(),
        "packets": [
            {
                "repairId": repair_id,
                "approvedSha256": digest,
                "approvalHashMode": profile["approval_hash_mode"],
            }
            for repair_id, digest in approved.items()
        ],
        "changedBlocks": len(changes),
        "changedRegions": len(rewritten),
        "sourceRegionSha256": actual_source_regions,
        "approvedPreviewRegionSha256": expected_regions,
        "rebasedRegions": rebased_regions,
        "resultRegionSha256": after_regions,
        "runtimeWritersFrozen": True,
        "lighting": "touched chunks marked isLightOn=false for vanilla relight",
        "appliedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=True, indent=2) + "\n",
        encoding="ascii",
    )
    print(json.dumps(receipt, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()

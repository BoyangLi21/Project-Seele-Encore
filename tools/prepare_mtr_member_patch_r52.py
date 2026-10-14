"""Prepare byte-preserving native MessagePack member patches; never install them."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = Path("D:/eva/delivery/Project_SEELE_Encore_R51_20261009_Server.zip")
MARKER = "mtr/projectseele/geofront/"


@dataclass
class Node:
    raw: bytes
    value: object
    children: object = None
    header: bytes = b""


class Parser:
    def __init__(self, data):
        self.data, self.offset = data, 0

    def take(self, count):
        result = self.data[self.offset:self.offset + count]
        assert len(result) == count
        self.offset += count
        return result

    def number(self, fmt):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def node(self):
        start = self.offset
        tag = self.number(">B")
        children, header = None, b""
        if tag <= 0x7f:
            value = tag
        elif tag >= 0xe0:
            value = tag - 256
        elif tag in (0xc0, 0xc2, 0xc3):
            value = {0xc0: None, 0xc2: False, 0xc3: True}[tag]
        elif tag in {0xcc, 0xcd, 0xce, 0xcf, 0xd0, 0xd1, 0xd2, 0xd3, 0xca, 0xcb}:
            value = self.number({0xcc: ">B", 0xcd: ">H", 0xce: ">I", 0xcf: ">Q", 0xd0: ">b", 0xd1: ">h", 0xd2: ">i", 0xd3: ">q", 0xca: ">f", 0xcb: ">d"}[tag])
        elif 0xa0 <= tag <= 0xbf or tag in (0xd9, 0xda, 0xdb):
            length = tag & 31 if 0xa0 <= tag <= 0xbf else self.number({0xd9: ">B", 0xda: ">H", 0xdb: ">I"}[tag])
            value = self.take(length).decode("utf-8")
        elif 0x90 <= tag <= 0x9f or tag in (0xdc, 0xdd):
            count = tag & 15 if 0x90 <= tag <= 0x9f else self.number(">H" if tag == 0xdc else ">I")
            header = self.data[start:self.offset]
            children = [self.node() for _ in range(count)]
            value = [child.value for child in children]
        elif 0x80 <= tag <= 0x8f or tag in (0xde, 0xdf):
            count = tag & 15 if 0x80 <= tag <= 0x8f else self.number(">H" if tag == 0xde else ">I")
            header = self.data[start:self.offset]
            children = [(self.node(), self.node()) for _ in range(count)]
            value = {key.value: child.value for key, child in children}
            assert len(value) == count, "Duplicate map keys require explicit native handling"
        elif tag in (0xc4, 0xc5, 0xc6):
            length = self.number({0xc4: ">B", 0xc5: ">H", 0xc6: ">I"}[tag])
            value = self.take(length)
        elif tag in (0xd4, 0xd5, 0xd6, 0xd7, 0xd8, 0xc7, 0xc8, 0xc9):
            length = {0xd4: 1, 0xd5: 2, 0xd6: 4, 0xd7: 8, 0xd8: 16}.get(tag)
            if length is None:
                length = self.number({0xc7: ">B", 0xc8: ">H", 0xc9: ">I"}[tag])
            value = ("opaque_extension", self.take(1), self.take(length))
        else:
            raise ValueError(f"Unsupported token {tag:02X}")
        return Node(self.data[start:self.offset], value, children, header)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def array_header(old, count):
    tag = old.raw[0]
    if 0x90 <= tag <= 0x9f and count <= 15:
        return bytes([0x90 | count])
    if tag != 0xdd and count <= 65535:
        return b"\xdc" + struct.pack(">H", count)
    return b"\xdd" + struct.pack(">I", count)


def primitive(value, old=None):
    if value is None:
        return b"\xc0"
    if isinstance(value, bool):
        return b"\xc3" if value else b"\xc2"
    if isinstance(value, int):
        tag = old.raw[0] if old else None
        formats = {0xcc: ">B", 0xcd: ">H", 0xce: ">I", 0xcf: ">Q", 0xd0: ">b", 0xd1: ">h", 0xd2: ">i", 0xd3: ">q"}
        if tag in formats:
            try:
                return bytes([tag]) + struct.pack(formats[tag], value)
            except struct.error:
                pass
        if 0 <= value <= 127:
            return bytes([value])
        if -32 <= value < 0:
            return bytes([value & 255])
        return b"\xd3" + struct.pack(">q", value)
    if isinstance(value, float):
        tag = 0xca if old and old.raw[0] == 0xca else 0xcb
        return bytes([tag]) + struct.pack(">f" if tag == 0xca else ">d", value)
    if isinstance(value, str):
        encoded = value.encode("utf-8")
        tag = old.raw[0] if old else None
        if len(encoded) <= 31 and (tag is None or 0xa0 <= tag <= 0xbf):
            header = bytes([0xa0 | len(encoded)])
        elif len(encoded) <= 255 and tag not in (0xda, 0xdb):
            header = b"\xd9" + struct.pack(">B", len(encoded))
        elif len(encoded) <= 65535 and tag != 0xdb:
            header = b"\xda" + struct.pack(">H", len(encoded))
        else:
            header = b"\xdb" + struct.pack(">I", len(encoded))
        return header + encoded
    raise TypeError(type(value))


def patch(node, value, trace, path="", array_overrides=None):
    if array_overrides and path in array_overrides:
        children = array_overrides[path]
        trace.append({"field": path, "operation": "expand native path", "before_count": len(node.children), "after_count": len(children)})
        return array_header(node, len(children)) + b"".join(children)
    if node.value is value or node.value == value:
        return node.raw
    if isinstance(value, dict):
        assert set(value) == set(node.value), (path, "Do not add/remove unidentified fields")
        return node.header + b"".join(key.raw + patch(child, value[key.value], trace,
                     f"{path}.{key.value}".lstrip("."), array_overrides) for key, child in node.children)
    if isinstance(value, list):
        assert len(value) == len(node.children) or path.endswith("signalColors")
        if len(value) != len(node.children):
            trace.append({"field": path, "operation": "replace array values", "before": node.value, "after": value})
        return array_header(node, len(value)) + b"".join(patch(node.children[i], v, trace, f"{path}[{i}]")
                     if i < len(node.children) else primitive(v) for i, v in enumerate(value))
    trace.append({"field": path, "operation": "replace value", "before": node.value, "after": value})
    return primitive(value, node)


def map_child(node, key):
    return next(value for name, value in node.children if name.value == key)


def point(p):
    return tuple(p[k] for k in ("x", "y", "z")) if isinstance(p, dict) else tuple(p)


def edge(a, b):
    return tuple(sorted((point(a), point(b))))


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output-directory", type=Path, default=ROOT / "artifacts/r52_mtr_progress_review/member_patch_v1")
    args = parser.parse_args()
    out = args.output_directory.resolve()
    allowed = (ROOT / "artifacts/r52_mtr_progress_review").resolve()
    assert allowed in out.parents and not out.exists()
    out.mkdir(parents=True)
    base = ROOT / "artifacts/r52_mtr_progress_review/proposal_v3"
    read = lambda p: json.loads(p.read_text(encoding="utf-8"))
    proposal, proposed_records, native = (read(base / p) for p in ("PROPOSAL.json", "IN_MEMORY_NATIVE_RECORDS.json", "NATIVE_CANDIDATE_MEMBER_VERIFICATION.json"))
    candidate = read(ROOT / "artifacts/r52_hq_approach_candidate/CANDIDATE.json")
    ten_rows = read(ROOT / "artifacts/r52_hq_rail_boundary/hq_ten_rails.json")
    ten = [r["data"] for r in ten_rows]
    originals = {edge(d["position1"], d["position2"]): i for i, d in enumerate(ten)}
    segments = {s["id"]: s for s in candidate["segments"]}
    names = {s["segment_id"]: MARKER + s["native_relative_path"] for s in native["candidate_native_rail_member_names"]}
    assert len(names) == 54
    targets = {r["member"]: r["data"] for rows in proposed_records.values() for r in rows}
    blobs, nodes, tails = {}, {}, {}
    with zipfile.ZipFile(ARCHIVE) as archive:
        for entry in archive.infolist():
            if "/" + MARKER not in entry.filename or entry.is_dir():
                continue
            raw = archive.read(entry); reader = Parser(raw); node = reader.node()
            blobs[entry.filename], nodes[entry.filename], tails[entry.filename] = raw, node, raw[reader.offset:]
    operations, protected, path_proofs = [], [], []

    def expand_path_array(array, key, trace):
        children, semantic = [], []
        for i, old in enumerate(array.children):
            d = old.value
            original = originals.get(edge(d["startPosition"], d["endPosition"]))
            if original is None:
                children.append(old.raw); semantic.append(d); continue
            reverse = point(d["startPosition"]) != point(ten[original]["position1"])
            chain = candidate["routes"][f"original_{original}"]
            chain = list(reversed(chain)) if reverse else chain
            for j, name in enumerate(chain):
                s = segments[name]; new = copy.deepcopy(d)
                for field, value in (("startPosition", s["to"] if reverse else s["from"]), ("endPosition", s["from"] if reverse else s["to"])):
                    new[field].update(dict(zip(("x", "y", "z"), value)))
                new.update(startAngle=s["to_angle"] if reverse else s["from_angle"], endAngle=s["from_angle"] if reverse else s["to_angle"],
                           shape=s["shape"], verticalRadius=s["vertical_radius"])
                if j < len(chain) - 1:
                    new.update(savedRailBaseId=0, dwellTime=0)
                piece_trace = []
                encoded = patch(old, new, piece_trace, f"{key}[{len(children)}]")
                parsed = Parser(encoded).node()
                assert parsed.value == new
                allowed_keys = {"startPosition", "endPosition", "startAngle", "endAngle", "shape", "verticalRadius", "savedRailBaseId", "dwellTime"}
                preserved_keys = []
                for field in old.value:
                    if field not in allowed_keys:
                        assert map_child(old, field).raw == map_child(parsed, field).raw
                        preserved_keys.append(field)
                path_proofs.append({"record_field": key, "original_index": i, "new_index": len(children), "candidate_segment_id": name,
                                    "copied_template_map_header_and_keys": True, "all_other_field_token_bytes_identical": preserved_keys,
                                    "precise_changes": piece_trace})
                trace.extend(piece_trace); children.append(encoded); semantic.append(new)
        return children, semantic

    def save_operation(action, member, before, after, trace, template=None, tail=None):
        target = member[member.index(MARKER):] if MARKER in member else member
        row = {"action": action, "target_relative_path": target,
               "source_archive_member": member if before is not None else None,
               "before_sha256": sha(before) if before is not None else None,
               "after_sha256": sha(after) if after is not None else None,
               "precise_changed_fields": trace}
        if template:
            row.update(inherited_template_archive_member=template, inherited_template_sha256=sha(blobs[template]))
        if before is not None:
            p = out / "before" / target; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(before)
        if after is not None:
            p = out / "after" / target; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(after)
            reader = Parser(after); parsed = reader.node()
            if tail is not None:
                assert after[reader.offset:] == tail
                row.update(opaque_tail_preserved_bytes=len(tail), opaque_tail_sha256=sha(tail))
            row.update(after_effective_object_bytes=reader.offset, after_total_bytes=len(after))
        operations.append(row)

    for member, node in nodes.items():
        if member in {r["member"] for r in ten_rows}:
            save_operation("delete", member, blobs[member], None, [{"operation": "replace original boundary rail by explicit candidate chain"}])
            continue
        value = targets[member]
        if value == node.value:
            protected.append({"member": member, "sha256": sha(blobs[member])})
            continue
        kind = member.split(MARKER)[1].split("/")[0]
        assert kind in {"stations", "platforms", "depots", "sidings"}, (member, "Unapproved type")
        trace, overrides = [], {}
        for field in (["path"] if kind == "depots" else ["pathSidingToMainRoute", "pathMainRouteToSiding"] if kind == "sidings" else []):
            old = map_child(node, field)
            children, semantic = expand_path_array(old, field, trace)
            assert semantic == value[field]
            if old.value != semantic:
                overrides[field] = children
        after = patch(node, value, trace, array_overrides=overrides) + tails[member]
        after_node = Parser(after).node()
        assert after_node.value == value
        root_whitelist = {"position1", "position2"} if kind in ("stations", "platforms") else {"path"} if kind == "depots" else {"pathSidingToMainRoute", "pathMainRouteToSiding", "vehicles"}
        for field in node.value:
            if field not in root_whitelist:
                assert map_child(node, field).raw == map_child(after_node, field).raw
        if kind == "sidings":
            for old, new in zip(map_child(node, "vehicles").children, map_child(after_node, "vehicles").children):
                assert old.value["id"] == new.value["id"]
                for field in old.value:
                    if field not in {"railProgress", "nextStoppingIndexAto", "nextStoppingIndexManual"}:
                        assert map_child(old, field).raw == map_child(new, field).raw
        save_operation("modify", member, blobs[member], after, trace, tail=tails[member])
    for row in proposed_records["rails"]:
        if not row["member"].startswith("UNINSTALLED_CANDIDATE"):
            continue
        name = row["member"].split("/")[-1]; source_indices = segments[name]["source_original_indices"]
        template = ten_rows[source_indices[0]]["member"]; node = nodes[template]; trace = []
        before, value = node.value, row["data"]
        approved = {"position1", "position2", "angle1", "angle2", "shape", "verticalRadius", "speedLimit1", "speedLimit2", "signalColors"}
        for source in source_indices:
            other = nodes[ten_rows[source]["member"]]
            for field in before:
                if field not in approved:
                    assert map_child(node, field).raw == map_child(other, field).raw, (name, field, "Ambiguous inherited unknown metadata")
        after = patch(node, value, trace) + tails[template]; parsed = Parser(after).node()
        for field in before:
            if field not in approved:
                assert map_child(node, field).raw == map_child(parsed, field).raw
        assert not any(MARKER + names[name].split(MARKER)[1] in old for old in nodes)
        save_operation("create", names[name], None, after, trace, template, tails[template])
    counts = {a: sum(o["action"] == a for o in operations) for a in ("modify", "delete", "create")}
    assert counts == {"modify": 8, "delete": 10, "create": 54}, counts
    assert len(protected) == len(nodes) - 18
    manifest = {"schema": "projectseele.r52.native-mtr-member-patch.v1", "installed": False,
                "archive": str(ARCHIVE), "world_written": False, "operations": operations,
                "counts": counts, "protected_original_members": protected,
                "actual_original_member_count": len(nodes),
                "path_clone_token_preservation": path_proofs,
                "native_verification_receipt": str(base / "NATIVE_CANDIDATE_MEMBER_VERIFICATION.json"),
                "native_verification_receipt_sha256": sha((base / "NATIVE_CANDIDATE_MEMBER_VERIFICATION.json").read_bytes()),
                "operating_diff": proposal["operating_diff"], "signal_blocks": proposal["blocks"],
                "scope": "1 HQ station + 3 HQ platforms + 2 affected depots + 2 affected sidings; 10 old rails replaced by 54",
                "requires_Root_audit_ledger_review": True}
    (out / "PATCH_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), "counts": counts, "byte_unchanged_protected_members": len(protected),
                      "path_template_proofs": len(path_proofs)}))


if __name__ == "__main__":
    main()

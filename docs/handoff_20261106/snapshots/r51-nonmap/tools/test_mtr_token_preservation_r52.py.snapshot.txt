"""Meaningful unknown-token/opaque-tail checks for the member surgery tool."""
import copy
import json
import struct
import zipfile
from prepare_mtr_member_patch_r52 import ARCHIVE, ROOT, MARKER, Parser, Node, map_child, patch, primitive


def encoded_map(fields):
    return bytes([0x80 | len(fields)]) + b"".join(primitive(k) + v for k, v in fields)


def main():
    vendor = encoded_map([
        ("legacy_wide_int", b"\xcd\x00\x05"),
        ("opaque_binary", b"\xc4\x04\x00\xff\x3d\x50"),
        ("future_extension", b"\xd7\x2a\xde\xad\xbe\xef\x12\x34\x00\x00"),
        ("legacy_nan_payload", b"\xcb\x7f\xf8\x00\x00\x00\x00\x00\x11"),
        ("nonminimal_string", b"\xd9\x03raw"),
    ])
    position = encoded_map([("x", b"\xd3" + struct.pack(">q", 2)), ("y", primitive(-467)), ("z", primitive(522))])
    path = encoded_map([("startPosition", position), ("vendor", vendor)])
    raw = encoded_map([("railProgress", primitive(25.5)), ("vendor", vendor), ("path", b"\x91" + path)])
    tail = b"\x00\xff\x83original opaque tail\x00\x99"
    reader = Parser(raw + tail); node = reader.node(); assert reader.data[reader.offset:] == tail
    changed = copy.deepcopy(node.value); changed["railProgress"] = 40.25
    changed["path"][0]["startPosition"]["x"] = 7
    after = patch(node, changed, []) + tail
    decoded = Parser(after); result = decoded.node()
    assert decoded.data[decoded.offset:] == tail
    assert map_child(node, "vendor").raw == map_child(result, "vendor").raw
    assert map_child(map_child(node, "path").children[0], "vendor").raw == map_child(map_child(result, "path").children[0], "vendor").raw
    old = map_child(node, "path").children[0]; pieces = []
    for coordinate in (100, 101):
        value = copy.deepcopy(old.value); value["startPosition"]["x"] = coordinate
        pieces.append(patch(old, value, []))
    changed = copy.deepcopy(node.value); changed["path"] = [Parser(p).node().value for p in pieces]
    expanded = patch(node, changed, [], array_overrides={"path": pieces})
    for piece in map_child(Parser(expanded).node(), "path").children:
        assert map_child(piece, "vendor").raw == map_child(old, "vendor").raw
    count = 0
    with zipfile.ZipFile(ARCHIVE) as archive:
        for entry in archive.infolist():
            if "/" + MARKER not in entry.filename or entry.is_dir():
                continue
            raw = archive.read(entry); reader = Parser(raw); node = reader.node()
            assert patch(node, copy.deepcopy(node.value), []) + raw[reader.offset:] == raw
            count += 1
    report = {"schema": "projectseele.r52.mtr-token-surgery-regression.v1",
              "actual_original_records_byte_roundtrip": count,
              "synthetic_binary_extension_nan_payload_and_nonminimal_tokens_preserved": True,
              "expanded_path_clones_unknown_tokens_verbatim": True,
              "opaque_tail_exact": True, "world_or_database_written": False}
    p = ROOT / "artifacts/r52_mtr_progress_review/member_patch_v3/TOKEN_SURGERY_REGRESSION.json"
    assert not p.exists(); p.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("PASS unknown tokens + opaque tail + native source byte roundtrip:", count)


if __name__ == "__main__":
    main()

"""Six real contact patches from submitted armour triangles, not body boxes.

Fixed gantry origin uses the actual runtime bed+.04 frame. Pads conform to a
measured upward shoulder face and retract away before horizontal withdrawal.
Only a reviewable geometry contract is written; no game resource/world edits.
"""
from pathlib import Path
import hashlib, json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/rebuild_r44/facility_transit_r44/hangar_shoulder_contact_v2"
SOURCE = ROOT / "artifacts/rebuild_r44/facility_transit_r44/hangar_tv_calibration_v2/actual_render_body_surfaces_triangles.json"


def main():
    data = json.loads(SOURCE.read_text(encoding="utf8"))
    semantics = json.loads((SOURCE.parent / "semantic_frame.json").read_text(encoding="utf8"))
    contacts = []
    for variant in range(3):
        actor = data["actors"][str(variant)]
        body_origin = np.array([actor[k] for k in ("x", "y", "z")])
        bed = semantics["bays"][variant]["bed"]
        gantry_origin = np.array([body_origin[0], bed[1] + .04, body_origin[2]])
        for side, bone in ((-1, "arm_l"), (1, "arm_r")):
            part = actor["parts"][bone]
            choices = []
            seen = set()
            for index, triangle in enumerate(part["top_band_triangles"]):
                points = np.array(triangle["world_vertices"], dtype=float)
                key = tuple(np.round(points, 5).flatten())
                if key in seen:
                    continue
                seen.add(key)
                vector = np.cross(points[1] - points[0], points[2] - points[0])
                area = np.linalg.norm(vector) * .5
                if area < .04:
                    continue
                normal = vector / (area * 2)
                submitted_normal = np.array(triangle["world_outward_normal"], dtype=float)
                if np.dot(normal, submitted_normal) < 0:
                    normal = -normal
                centre = points.mean(axis=0)
                if normal[1] < .55 or side * normal[0] < .02 or np.ptp(points[:, 1]) > 1.5:
                    continue
                if centre[1] < part["world_bounds"][4] - 1.2:
                    continue
                choices.append((area, centre[1], index, points, normal, submitted_normal))
            if not choices:
                raise RuntimeError(("No actual upward shoulder contact face", variant, bone))
            area, _, index, points, normal, submitted_normal = max(choices, key=lambda t: (t[0], t[1]))
            centre = points.mean(axis=0)
            # A compact pad lies wholly inside the actual face; every contact
            # point retains explicit barycentric provenance in its triangle.
            face = centre + .72 * (points - centre)
            contact_face = face + normal * .006
            for point in contact_face:
                if abs(np.dot(point - points[0], normal) - .006) > 1.e-6:
                    raise RuntimeError("Contact face is not on its exact submitted surface plane")
            local = contact_face - gantry_origin
            capsule = semantics["bays"][variant]["capsule_sweep_negative"]
            volume = np.vstack((contact_face, contact_face + normal * .16))
            lo, hi = volume.min(axis=0), volume.max(axis=0)
            if all(hi[i] > capsule[0][i] and lo[i] < capsule[1][i] for i in range(3)):
                raise RuntimeError(("Shoulder pad enters complete capsule motion", variant, bone))
            contacts.append({"variant": variant, "side": side, "bone": bone, "actual_actor_uuid": actor["uuid"],
                "actual_submitted_tick": actor["tick"], "source_triangle_index": index,
                "source_triangle_world": points.tolist(), "source_area_m2": area,
                "actual_render_normal_world": submitted_normal.tolist(), "exact_geometric_outward_normal_world": normal.tolist(),
                "body_origin_world": body_origin.tolist(), "fixed_gantry_origin_world": gantry_origin.tolist(),
                "pad_contact_world": contact_face.tolist(), "pad_contact_fixed_gantry_local": local.tolist(),
                "contact_centre_fixed_gantry_local": (contact_face.mean(axis=0) - gantry_origin).tolist(),
                "offset_from_actual_surface_m": .006, "pad_thickness_outward_m": .16,
                "release": {"first_normal_lift_m": 2.1, "normal_lift_interval": [0, .25],
                    "then_outboard_x_m": side * 5.35, "outboard_interval": [.23, .88],
                    "requirement": "Jaw/pad and pin must lift together. A jaw sliding horizontally on a sloped shoulder face is not a valid release."},
                "reference": "user_tv_1 green shoulder seat with actuators; measured arm surface, not the taller pylon apex",
                "mounting": "Selected a measured upward AND outboard-facing armour facet, so the actuator approaches from its own side rather than from the neck",
                "required_native": "Actual posed contact/gap through standby breathing, release, transfer, recovery, clamp closure and cold reload; static coordinates do not pass motion"})
    OUT.mkdir(parents=True, exist_ok=True)
    result = {"source": str(SOURCE), "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "contacts": contacts, "pylon_top_not_used": True,
        "coordinate_frames": "Submitted world vertices -> actual fixed gantry anchor (EVA x/z, bedY+.04). No assumed external AABB or model-pivot correction.",
        "status": "REAL_SURFACE_GEOMETRY_CONTRACT; original machinery assets/runtime and all native contact workflows remain unverified"}
    (OUT / "contacts.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
    print("Actual conforming shoulder contacts:", len(contacts), "original armour triangles; source/world unchanged", flush=True)


if __name__ == "__main__":
    main()

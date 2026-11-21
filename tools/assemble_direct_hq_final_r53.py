"""Bind the one current direct HQ civil, finite correction and express policy."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument("--candidate-directory",type=Path,required=True);a=ap.parse_args();base=a.candidate_directory.resolve();out=base/"FINAL_CANDIDATE";out.mkdir(exist_ok=False)
    original=base/"COMPLETE_CIVIL_CANDIDATE";mask=np.load(original/"POSITIVE_MASK_EXACT_STATES.npz");states=list(mask["states"]);positions=mask["positions"].tolist();before=mask["before"].tolist();after=mask["after"].tolist();lookup={tuple(q):i for i,q in enumerate(positions)}
    finite=json.loads((base/"FINITE_CLEARANCE_CANDIDATE.json").read_text("utf8"));cube=json.loads((base/"ACTUAL_SOURCE_CUBE_CONTACT_REFINEMENT_AFTER_FINITE_PATCH.json").read_text("utf8"));assert cube["actual_source_cube_contacts"]==0 and cube["finite_patch_sha256"]==sha(base/"FINITE_CLEARANCE_CANDIDATE.json")
    native=json.loads((base/"express_policy/NATIVE_BINARY_VERIFICATION.json").read_text("utf8"));assert native["vehicles_exact_original_identity_and_saved_state"]==40 and native["vehicles_remapped"]==6 and len(native["native_signal_block_tests"])==3
    def code(s):
        if s not in states:states.append(s)
        return states.index(s)
    for r in finite["cells"]:
        q=tuple(r["pos"])
        if q in lookup:
            i=lookup[q];assert states[before[i]]==r["before"];after[i]=code(r["after"])
        else:
            lookup[q]=len(positions);positions.append(list(q));before.append(code(r["before"]));after.append(code(r["after"]))
    before=np.asarray(before,np.uint16);after=np.asarray(after,np.uint16)
    np.savez_compressed(out/"POSITIVE_MASK_EXACT_STATES.npz",positions=np.asarray(positions,np.int32),before=before,after=after,states=np.asarray(states),positive_edit_mask=before!=after)
    geometry=json.loads((base/"COMPLETE_CIVIL_CANDIDATE/REPORT.json").read_text("utf8"));bearings=json.loads((base/"WET_FOUNDED_SUPPORT_CANDIDATE.json").read_text("utf8"));assert not bearings["cells"]
    report=dict(schema="projectseele.direct-hq-final-root-candidate-r53.v1",world_written=False,static_ready_for_Root_apply=True,
                source_geometry_sha256=sha(base/"CANDIDATE.json"),native_curves_sha256=sha(base/"NATIVE_GEOMETRY.json"),
                source_complete_civil_sha256=sha(original/"REPORT.json"),exact_states_mask_sha256=sha(out/"POSITIVE_MASK_EXACT_STATES.npz"),
                complete_selected_cells=len(positions),changed_cells=int(np.count_nonzero(before!=after)),original_loop_full_retirement_cells=geometry["original_loop_cells_reviewed"],
                lake_watertight=geometry["lake_watertight"],lake_positive_owner_cells=geometry["lake_interface_cells"],finite_clearance_cells=len(finite["cells"]),
                actual_source_body_bogie_contact_count=cube["actual_source_cube_contacts"],actual_source_cube_receipt_sha256=sha(base/"ACTUAL_SOURCE_CUBE_CONTACT_REFINEMENT_AFTER_FINITE_PATCH.json"),
                actual_measured_three_layer_bearings=len(bearings["inherited_measured_bearings"]),
                native_member_patch=str(base/"express_policy/member_patch/PATCH_MANIFEST.json"),native_member_patch_sha256=sha(base/"express_policy/member_patch/PATCH_MANIFEST.json"),
                native_binary_verification_sha256=sha(base/"express_policy/NATIVE_BINARY_VERIFICATION.json"),
                all40_original_train_ids_and_other_saved_token_fields_preserved=True,unchanged34_native_heads_exact=True,
                original3_station_platforms_original_U2_siding_depot_and_all_route_ids_preserved=True,
                positive_rail_limits_kph=dict(old_cruise=60,new_cruise=160,old_throat=60,new_throat=40,forbidden_reverse=0),native_original_acceleration_and_deceleration=4e-6,
                original_APG_guard_BEs_not_selected=True,
                pending=["Root atomic World and current MTR member installation", "refresh derived current transit/navigation", "this-round native actual train motion and service timing", "APG actual closed/open and passenger riding", "actual visual review"])
    (out/"REPORT.json").write_text(json.dumps(report,indent=2)+"\n","utf8");print(json.dumps({k:v for k,v in report.items() if k in ("static_ready_for_Root_apply","complete_selected_cells","changed_cells","actual_source_body_bogie_contact_count","actual_measured_three_layer_bearings","finite_clearance_cells")}),flush=True)


if __name__=="__main__":main()

"""Root-only precise ordinary-door use ray correction; Java remains frozen."""
import difflib
import json
from school_hakone_patch_r45 import ROOT,ART,sha


def main():
    source=ROOT/'src/main/java/com/projectseele/client/visual/SchoolPoolLifecycleR45.java';out=ART/'school_control_ray_v1'
    assert not out.exists();out.mkdir()
    before=source.read_text('utf8');after=before
    old='private static long lastUseTick = Long.MIN_VALUE;'
    assert old in after;after=after.replace(old,old+'\n    private static volatile JsonObject nativeUseEvidence;',1)
    old='''        Vec3 start = mc.player.getEyePosition(), centre = Vec3.atCenterOf(target).add(0,.2,0);
        if (start.distanceTo(centre) > 4.25) throw new IllegalStateException("Native use point is outside real reach: "+target);
        var hit = mc.level.clip(new net.minecraft.world.level.ClipContext(start,centre,
            net.minecraft.world.level.ClipContext.Block.OUTLINE,net.minecraft.world.level.ClipContext.Fluid.NONE,mc.player));
        if (hit.getType() != net.minecraft.world.phys.HitResult.Type.BLOCK
            || hit.getBlockPos().getX() != target.getX() || hit.getBlockPos().getZ() != target.getZ()
            || Math.abs(hit.getBlockPos().getY()-target.getY()) > 1)
            throw new IllegalStateException("Actual ray cannot reach the assigned ordinary control: "+target+" hit="+hit);'''
    new='''        Vec3 start = mc.player.getEyePosition();
        net.minecraft.world.phys.BlockHitResult hit=null;double nearest=Double.POSITIVE_INFINITY;
        // An opened native door occupies its hinge-side outline, so a ray to
        // the empty centre cannot close it. Test actual outline-box centres.
        for(var box:state.getShape(mc.level,target).toAabbs())
        {
            Vec3 aimed=box.getCenter().add(target.getX(),target.getY(),target.getZ());
            double distance=start.distanceTo(aimed);if(distance>4.25||distance>=nearest)continue;
            var measured=mc.level.clip(new net.minecraft.world.level.ClipContext(start,aimed,
                net.minecraft.world.level.ClipContext.Block.OUTLINE,net.minecraft.world.level.ClipContext.Fluid.NONE,mc.player));
            if(measured.getType()!=net.minecraft.world.phys.HitResult.Type.BLOCK
                ||measured.getBlockPos().getX()!=target.getX()||measured.getBlockPos().getZ()!=target.getZ()
                ||Math.abs(measured.getBlockPos().getY()-target.getY())>1)continue;
            hit=measured;nearest=distance;
        }
        if(hit==null)throw new IllegalStateException("No actual reachable native outline on the assigned ordinary control: "+target);
        Vec3 aim=hit.getLocation().subtract(start);
        mc.player.setYRot((float)Math.toDegrees(Math.atan2(-aim.x,aim.z)));
        mc.player.setXRot((float)-Math.toDegrees(Math.atan2(aim.y,aim.horizontalDistance())));
        var evidence=new JsonObject();evidence.addProperty("target",target.toShortString());evidence.addProperty("client_game_time",mc.level.getGameTime());
        evidence.addProperty("actual_hit_block",hit.getBlockPos().toShortString());evidence.addProperty("actual_hit_face",hit.getDirection().getName());
        evidence.addProperty("actual_hit_location",hit.getLocation().toString());evidence.addProperty("actual_eye",start.toString());
        evidence.addProperty("actual_state",state.toString());evidence.addProperty("ordinary_native_outline_only",true);nativeUseEvidence=evidence;'''
    assert old in after;after=after.replace(old,new,1)
    old='witness.addProperty("actual_client_position",mc.player.position().toString());row.getAsJsonArray("actions").add(witness);'
    new='witness.addProperty("actual_client_position",mc.player.position().toString());if(nativeUseEvidence!=null)witness.add("last_actual_native_use_ray",nativeUseEvidence.deepCopy());row.getAsJsonArray("actions").add(witness);'
    assert old in after;after=after.replace(old,new,1)
    candidate=out/source.name;candidate.write_bytes(after.encode('utf8'))
    diff=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/src/main/java/com/projectseele/client/visual/SchoolPoolLifecycleR45.java',tofile='b/src/main/java/com/projectseele/client/visual/SchoolPoolLifecycleR45.java'))
    (out/'school_control_ray.patch').write_bytes(diff.encode('utf8'))
    (out/'preconditions.json').write_text(json.dumps(dict(source=str(source.resolve()),before_sha256=sha(source),candidate=str(candidate.resolve()),candidate_sha256=sha(candidate),source_modified=False,
        root_only_merge=True,compatible_with_independent_restore_ack_patch=True,compiled_by_agent=False,native_verified=False),indent=2)+'\n','utf8')
    print('Prepared real outline use-ray candidate, frozen Java unchanged',out,flush=True)


if __name__=='__main__':main()

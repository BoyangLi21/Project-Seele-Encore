package com.projectseele.world;

import net.minecraft.world.phys.Vec3;

/** Isolated geometry experiment; not registered as a production motion law. */
final class CandidateHoistPoseR53
{
    static NervCranePoseR52.Pose stableRoll(NervCranePoseR52.State state,Vec3 suppliedMount)
    {
        if(!state.coupled()||state.plug()==null)throw new IllegalArgumentException("Coupled review sample required");
        var local=state.machine().inverse().compose(state.plug());
        var z=local.transformVector(new Vec3(0,0,1)).normalize();
        var projection=new Vec3(1,0,0).subtract(z.scale(z.x));
        if(projection.length()<.99)throw new IllegalArgumentException("Source insertion plane has changed");
        var x=projection.normalize();var y=z.cross(x).normalize();
        var anchor=local.transformPoint(EntryPlugKinematics.CRANE_ATTACHMENT_P);
        var grip=RigidTransform.fromAxes(anchor,x,y,z);var mount=grip.transformPoint(suppliedMount);
        return new NervCranePoseR52.Pose(state.machine(),grip,mount,mount.add(0,.45,0),0);
    }
}

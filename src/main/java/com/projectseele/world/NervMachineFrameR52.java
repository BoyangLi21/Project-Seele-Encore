package com.projectseele.world;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;
/** One measured machine frame owns both outer render and local coupling. */
public final class NervMachineFrameR52
{
    public static RigidTransform worldToLocal(Vec3 machineOrigin,Quaternionf machineWorldRotation,Vec3 worldAnchor,Quaternionf worldRotation)
    {var frame=RigidTransform.of(machineOrigin,machineWorldRotation);return frame.inverse().compose(RigidTransform.of(worldAnchor,worldRotation));}
    private NervMachineFrameR52(){}
}

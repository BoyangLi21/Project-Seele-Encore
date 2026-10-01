package com.projectseele.fx;

import com.projectseele.network.ClientboundAtFieldRipplePacket;
import com.projectseele.network.SeeleNetwork;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.network.PacketDistributor;

/** Server-side helper: broadcast a sized octagonal A.T. Field cue to nearby players. */
public final class AtFieldFX
{
    private static final double BROADCAST_RANGE = 96.0D;

    private AtFieldFX() {}

    public static void ripple(ServerLevel level, Vec3 point, Vec3 normal)
    {ripple(level,point,normal,10.5F);}

    public static void ripple(ServerLevel level, Vec3 point, Vec3 normal,float radius)
    {
        SeeleNetwork.CHANNEL.send(
                PacketDistributor.NEAR.with(() -> new PacketDistributor.TargetPoint(
                        point.x, point.y, point.z, BROADCAST_RANGE, level.dimension())),
                new ClientboundAtFieldRipplePacket(point.x, point.y, point.z,
                        (float) normal.x, (float) normal.y, (float) normal.z,radius));
    }
}

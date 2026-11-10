package com.projectseele.fx;

import com.projectseele.network.ClientboundAtFieldRipplePacket;
import com.projectseele.network.SeeleNetwork;
import com.projectseele.util.WeakIdentityMap;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.network.PacketDistributor;

/** Server-side helper: broadcast a sized octagonal A.T. Field cue to every player in the dimension. */
public final class AtFieldFX
{
    /** Ticks between two field cues for hits one body's field turns away. */
    private static final int BLOCKED_GAP = 3;
    private static final WeakIdentityMap<Entity, Long> LAST_BLOCKED = new WeakIdentityMap<>();

    private AtFieldFX() {}

    public static void ripple(ServerLevel level, Vec3 point, Vec3 normal)
    {ripple(level,point,normal,10.5F);}

    public static void ripple(ServerLevel level, Vec3 point, Vec3 normal,float radius)
    {
        SeeleNetwork.CHANNEL.send(PacketDistributor.DIMENSION.with(level::dimension),
                new ClientboundAtFieldRipplePacket(point.x, point.y, point.z,
                        (float) normal.x, (float) normal.y, (float) normal.z,radius));
    }

    /**
     * An attack the body's field turned away: the field shows just outside the body, facing where
     * the hit came from. Damage nobody dealt (a wall, a fall, fire) shows nothing, and a burst of
     * fire shows at most one cue every few ticks, which the client reads as one field under strain.
     */
    public static void blocked(ServerLevel level, Entity body, DamageSource source)
    {
        if (source.getEntity() == null && source.getDirectEntity() == null || source.getEntity() == body)
        {
            return;
        }
        long now = level.getGameTime();
        Long last = LAST_BLOCKED.get(body);
        if (last != null && now >= last && now - last < BLOCKED_GAP)
        {
            return;
        }
        LAST_BLOCKED.put(body, now);
        AABB box = body.getBoundingBox();
        Vec3 center = box.getCenter();
        Vec3 origin = origin(source);
        Vec3 dir = origin != null && origin.distanceToSqr(center) > 1.0E-4D
                ? origin.subtract(center).normalize()
                : body.getForward();
        ripple(level, center.add(dir.scale(surface(box, dir) + 1.0D)), dir, Math.max(10.5F, body.getBbHeight() * 0.55F));
    }

    /**
     * Where a hit came from: its stated position, else the middle of the body that dealt it. The feet
     * of a sixty-block attacker tilted the field down toward the ground.
     */
    public static Vec3 origin(DamageSource source)
    {
        if (source.sourcePositionRaw() != null)
        {
            return source.sourcePositionRaw();
        }
        Entity from = source.getDirectEntity() != null ? source.getDirectEntity() : source.getEntity();
        return from == null ? null : from.getBoundingBox().getCenter();
    }

    /** Distance from the box's centre to its surface along a unit direction. */
    private static double surface(AABB box, Vec3 dir)
    {
        double reach = Double.MAX_VALUE;
        double[] half = {box.getXsize() / 2.0D, box.getYsize() / 2.0D, box.getZsize() / 2.0D};
        double[] d = {Math.abs(dir.x), Math.abs(dir.y), Math.abs(dir.z)};
        for (int i = 0; i < 3; i++)
        {
            if (d[i] > 1.0E-4D)
            {
                reach = Math.min(reach, half[i] / d[i]);
            }
        }
        return reach == Double.MAX_VALUE ? 0.0D : reach;
    }
}

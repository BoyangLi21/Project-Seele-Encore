package com.projectseele.world;

import com.projectseele.registry.ModSounds;
import java.util.List;
import java.util.UUID;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.phys.Vec3;

/** Feedback from successfully committed launch motion and measured rail contacts. */
public final class NervLaunchFeedbackR53
{
    private static final String KEY = "LaunchFeedbackR53";

    public record Contact(Vec3 point, Vec3 tangent)
    {
        public Contact
        {
            if (!finite(point) || !finite(tangent) || tangent.lengthSqr() < 1.0e-10)
            {
                throw new IllegalArgumentException("Finite measured rail contact and motion tangent required");
            }
            tangent = tangent.normalize();
        }
    }

    /** Call only after the original carrier and its owner have committed movement.
     *  Resuming an existing launch must pass startsOnThisCommit=false. */
    public static void afterCommittedMotion(ServerLevel level, CompoundTag ownerData, UUID task,
            boolean launchPhase, boolean startsOnThisCommit, double speedMps, List<Contact> contacts)
    {
        if (!launchPhase || !Double.isFinite(speedMps) || speedMps <= 0 || contacts.isEmpty())
        {
            return;
        }
        if (contacts.size() > 16)
        {
            throw new IllegalArgumentException("Bounded actual rail contacts required");
        }
        long now = level.getGameTime();
        CompoundTag feedback = ownerData.getCompound(KEY);
        boolean sameTask = feedback.hasUUID("Task") && feedback.getUUID("Task").equals(task);
        boolean burst = startsOnThisCommit && !sameTask;
        if (!sameTask)
        {
            feedback = new CompoundTag();
            feedback.putUUID("Task", task);
            // Mark resumed tasks too: loading halfway through an ascent must
            // never manufacture a delayed electrical start burst.
            feedback.putLong("LastParticles", now - 2);
            feedback.putLong("LastFriction", now - 5);
            ownerData.put(KEY, feedback);
        }
        Vec3 soundPoint = Vec3.ZERO;
        for (Contact contact : contacts)
        {
            soundPoint = soundPoint.add(contact.point());
        }
        soundPoint = soundPoint.scale(1D / contacts.size());
        com.projectseele.entity.EvaUnit01Entity eva=null;
        var saved=NervRouteRuntimeR52.installationStateR52(level);
        if(saved!=null)for(var job:saved.jobs())if(job.snapshot().task().equals(task)
                &&level.getEntity(job.snapshot().original().eva()) instanceof com.projectseele.entity.EvaUnit01Entity original)
        {eva=original;break;}
        if(burst)
        {
            feedback.putLong("BurstAt",now);
            FacilityRouteAudioR53.mechanical(level,eva,soundPoint,ModSounds.LAUNCH_ELECTRIC_BURST_R53.get(),8F,1.35F,.82F);
            FacilityRouteAudioR53.mechanical(level,eva,soundPoint,ModSounds.FACILITY.get("facility_hydraulic_launch").get(),7F,1.2F,.85F);
        }
        // A single startup cloud remained behind the accelerating 60 m body.
        // Emit a short continuous pressure release at the measured moving heads,
        // then bounded friction jets. The client scales these to guide hardware.
        if(burst||now-feedback.getLong("LastParticles")>=4)
        {
            feedback.putLong("LastParticles",now);
            var packet=new com.projectseele.network.ClientboundLaunchFeedbackR54(level.dimension().location(),
                    eva==null?task.hashCode():eva.getId(),now,burst,(float)speedMps,contacts);
            for(var player:level.players())if(contacts.stream().anyMatch(contact->player.position().distanceToSqr(contact.point())<=192*192))
                com.projectseele.network.SeeleNetwork.CHANNEL.send(net.minecraftforge.network.PacketDistributor.PLAYER.with(()->player),packet);
        }
        if (speedMps < 3)
        {
            return;
        }
        double strength = Math.min(1, speedMps / 100D);
        if(now-feedback.getLong("LastFriction")>=14)
        {
            feedback.putLong("LastFriction",now);
            FacilityRouteAudioR53.mechanical(level,eva,soundPoint,ModSounds.LAUNCH_RAIL_FRICTION_R53.get(),
                    1.4F+(float)strength*3F,.65F+(float)strength*.6F,.85F+(float)strength*.2F);
        }
    }

    private static boolean finite(Vec3 value)
    {
        return value != null && Double.isFinite(value.x) && Double.isFinite(value.y) && Double.isFinite(value.z);
    }

    private NervLaunchFeedbackR53() {}
}

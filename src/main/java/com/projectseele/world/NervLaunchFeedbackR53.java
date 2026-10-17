package com.projectseele.world;

import com.projectseele.registry.ModSounds;
import java.util.List;
import java.util.UUID;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundSource;
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
        if (burst)
        {
            feedback.putLong("BurstAt",now);
            level.playSound(null, soundPoint.x, soundPoint.y, soundPoint.z,
                    ModSounds.LAUNCH_ELECTRIC_BURST_R53.get(), SoundSource.BLOCKS, 4F, .88F);
            level.playSound(null, soundPoint.x, soundPoint.y, soundPoint.z,
                    ModSounds.FACILITY.get("facility_hydraulic_launch").get(), SoundSource.BLOCKS, 3.6F, 1F);
            GiantParticles.send(level, ParticleTypes.FLASH, soundPoint.x, soundPoint.y, soundPoint.z, 1, 0, 0, 0, 0);
            for (int i = 0; i < Math.min(4, contacts.size()); i++)
            {
                Vec3 point = contacts.get(i).point();
                GiantParticles.send(level, ParticleTypes.ELECTRIC_SPARK, point.x, point.y, point.z, 64, 1.2, 1.2, 1.2, 1.1);
                GiantParticles.send(level, ParticleTypes.FIREWORK, point.x, point.y, point.z, 36, .8, .8, .8, .65);
            }
        }
        if(burst)
        {
            for(int i=0;i<Math.min(4,contacts.size());i++)
            {
                var contact=contacts.get(i);var point=contact.point();var away=point.subtract(soundPoint).normalize();
                var jet=contact.tangent().scale(-3.2).add(away.scale(1.2));
                GiantParticles.send(level,ParticleTypes.CLOUD,point.x,point.y,point.z,32,1.6,.8,1.6,.4);
                for(int n=0;n<8;n++)GiantParticles.send(level,new net.minecraft.core.particles.DustParticleOptions(new org.joml.Vector3f(.84F,.90F,.92F),4F),point.x,point.y,point.z,0,jet.x,jet.y,jet.z,1);
            }
        }
        if (speedMps < 3)
        {
            return;
        }
        double strength = Math.min(1, speedMps / 100D);
        if(now-feedback.getLong("LastFriction")>=12)
        {
            feedback.putLong("LastFriction",now);
            level.playSound(null,soundPoint.x,soundPoint.y,soundPoint.z,
                    ModSounds.LAUNCH_RAIL_FRICTION_R53.get(),SoundSource.BLOCKS,2.8F,.9F+(float)strength*.2F);
        }
        if (now - feedback.getLong("LastParticles") >= 2)
        {
            feedback.putLong("LastParticles", now);
            int sparks = 10;
            for (int i = 0; i < Math.min(4, contacts.size()); i++)
            {
                Contact contact = contacts.get(i);
                Vec3 p = contact.point();
                Vec3 trailing = contact.tangent().scale(-(.6 + 2.0 * strength));
                for (int n = 0; n < sparks; n++)
                {
                    Vec3 velocity = trailing.add((level.random.nextDouble() - .5) * .18,
                            (level.random.nextDouble() - .5) * .18, (level.random.nextDouble() - .5) * .18);
                    GiantParticles.send(level, n%3==0?ParticleTypes.FIREWORK:n%3==1?ParticleTypes.ELECTRIC_SPARK:ParticleTypes.CRIT, p.x, p.y, p.z,
                            0, velocity.x, velocity.y, velocity.z, 1);
                }
            }
        }
    }

    private static boolean finite(Vec3 value)
    {
        return value != null && Double.isFinite(value.x) && Double.isFinite(value.y) && Double.isFinite(value.z);
    }

    private NervLaunchFeedbackR53() {}
}

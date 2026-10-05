package com.projectseele.physics;

import com.projectseele.entity.AngelGrappleSurfaceR31;
import com.projectseele.entity.CombatFeelR31;
import com.projectseele.entity.CombatMotionR29;
import com.projectseele.entity.EvaImpactResponse;
import com.projectseele.entity.ShamshelEntity;
import com.projectseele.entity.ShamshelWhipMotion;
import org.joml.Vector3f;

/** Read-only extraction of the shipped whip, impact and Angel reaction angle layers. */
public final class ShamshelContactPoseR48
{
    private ShamshelContactPoseR48() {}

    private static boolean whip(String name)
    { return name.length() == 8 && (name.startsWith("whip_l_") || name.startsWith("whip_r_")) && name.charAt(7) >= '0' && name.charAt(7) <= '3'; }

    public static Vector3f base(ShamshelEntity actor, String name, Vector3f initial, float partial)
    {
        Vector3f result = new Vector3f(initial);
        double clock = actor.level().getGameTime() + (double)partial;
        float age = actor.isSweeping() ? actor.sweepAge(partial) : -1;
        if (name.equals("body"))
            return result.set(ShamshelWhipMotion.bodyPitch(actor.sweepMode(), age),
                    ShamshelWhipMotion.bodyYaw(actor.sweepSide(), actor.sweepMode(), age), result.z);
        if (whip(name))
        {
            int side = name.startsWith("whip_l_") ? 1 : -1;
            int segment = Integer.parseInt(name.substring(name.lastIndexOf('_') + 1));
            return ShamshelWhipMotion.rotation(side, segment, actor.sweepSide(), actor.sweepMode(), age, clock);
        }
        if (name.length() == 6 && name.startsWith("tail_") && name.charAt(5) >= '0' && name.charAt(5) <= '3')
            result.x = (float) Math.sin(clock * .038 - Integer.parseInt(name.substring(5)) * .6) * .025F;
        return result;
    }

    public static Vector3f impact(ShamshelEntity actor, String name, Vector3f current, float partial)
    {
        Vector3f result = new Vector3f(current);
        var pose = EvaImpactResponse.sample(actor, partial);
        if (pose.energy() < .001F) return result;
        float weight = name.equals("head") ? .35F : .75F;
        if (name.equals("body") || name.equals("head"))
        {
            result.x += pose.pitch() * weight; result.z += pose.roll() * weight;
            if (name.equals("head")) result.x += pose.head();
        }
        return result;
    }

    /** Takes the already base/impact-layered angle; it does not author a new pose or motion clock. */
    public static Vector3f reaction(ShamshelEntity actor, String name, Vector3f current, float partial)
    {
        Vector3f result = new Vector3f(current);
        float held = AngelGrappleSurfaceR31.heldWeight(actor, partial);
        if (held > 0)
        {
            if (name.equals("body")) result.x -= .18F * held;
            if (name.equals("head")) result.x -= .12F * held;
            if (whip(name))
            {
                int segment = Integer.parseInt(name.substring(name.lastIndexOf('_') + 1));
                result.x += (segment == 0 ? .4F : .12F) * held;
                result.z += (name.startsWith("whip_l_") ? .1F : -.1F) * held;
            }
            return result;
        }
        var beat = CombatFeelR31.beat(actor);
        if (beat == null || beat.kind() == CombatFeelR31.CONTACT) return result;
        float age = CombatFeelR31.age(actor, partial);
        Vector3f direction = beat.direction().toVector3f().rotateY((float) -Math.toRadians(180 - actor.yBodyRot));
        float length = (float) Math.sqrt(direction.x * direction.x + direction.z * direction.z);
        float dx = length < .001F ? 0 : direction.x / length, dz = length < .001F ? 1 : direction.z / length;
        if (beat.kind() == CombatFeelR31.DOWN || beat.kind() == CombatFeelR31.THROWN)
        {
            float falling = (float) CombatMotionR29.ease(age / (beat.kind() == CombatFeelR31.THROWN ? 7 : 12));
            float rise = beat.kind() == CombatFeelR31.THROWN ? 0 : (float) CombatMotionR29.ease((age - (beat.duration() - 20)) / 20);
            float weight = falling * (1 - rise), angle = weight * (beat.kind() == CombatFeelR31.THROWN ? 1.12F : 1.42F);
            if (name.equals("root")) { result.x += angle * dz; result.z -= angle * dx; }
            if (name.equals("head")) result.x -= .20F * weight;
            if (name.equals("whip_l_0") || name.equals("whip_r_0"))
            {
                float side = name.startsWith("whip_l_") ? 1 : -1;
                result.x += (-.48F - result.x) * weight;
                result.y *= 1 - weight; result.z += (side * .28F - result.z) * weight;
            }
        }
        else
        {
            float accent = (float) CombatMotionR29.recoil(age) * beat.strength() * (beat.kind() == CombatFeelR31.STAGGER ? .28F : .12F);
            if (name.equals("body")) { result.x += accent * dz; result.z -= accent * dx; }
            if (name.equals("head")) { result.x -= accent * .45F; result.z += accent * dx * .25F; }
        }
        return result;
    }

    public static boolean groundSupport(ShamshelEntity actor)
    {
        if (CombatBodyDynamics.active(actor)) return false;
        var beat = CombatFeelR31.beat(actor);
        if (beat == null || beat.kind() != CombatFeelR31.DOWN) return false;
        if (actor.onGround()) return true;
        var box = actor.getBoundingBox();
        return actor.level().getBlockCollisions(actor, new net.minecraft.world.phys.AABB(box.minX + .1, box.minY - .15,
                box.minZ + .1, box.maxX - .1, box.minY + .01, box.maxZ - .1)).iterator().hasNext();
    }
}

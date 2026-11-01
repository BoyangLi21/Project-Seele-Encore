package com.projectseele.client.render;

import java.util.LinkedHashSet;
import java.util.Set;

import com.projectseele.anim.EvaAnimator;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.util.Mth;
import org.joml.Quaternionf;
import software.bernie.geckolib.cache.object.BakedGeoModel;

/** Writes the {@link EvaAnimator} body onto the shared Gecko skeleton. */
final class EvaAnimatorGecko
{
    static final String OWNER = "SEELE_ANIM3";

    private EvaAnimatorGecko() {}

    static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity e, BakedGeoModel model, float partial)
    {
        var body = EvaAnimator.sample(e, partial);
        Set<String> rotations = new LinkedHashSet<>();
        Set<String> positions = new LinkedHashSet<>();
        for (String name : body.rig.keySet())
        {
            if (name.startsWith("finger_"))
            {
                continue;
            }
            model.getBone(name).ifPresent(b ->
            {
                Quaternionf q = body.rotations.get(name);
                if ("head".equals(name) && e.getPilotEntity() != null)
                {
                    // Pilot look on top of the clip's head motion.
                    q = new Quaternionf(q).rotateY(-e.pilotHeadYawForRender(partial) * Mth.DEG_TO_RAD)
                            .rotateX(-e.pilotHeadPitchForRender(partial) * Mth.DEG_TO_RAD);
                }
                EvaRigTransforms.rotate(b, q);
                var p = body.positions.get(name);
                b.setPosX(-p.x * 16);
                b.setPosY(p.y * 16);
                b.setPosZ(p.z * 16);
                rotations.add(name);
                positions.add(name);
            });
        }
        var fingers = EvaHandPoseR28.apply(e, model, partial);
        rotations.addAll(fingers.rotationBones());
        positions.addAll(fingers.positionBones());
        return new EvaMotionEngineV2.BoneWrites(Set.copyOf(rotations), Set.copyOf(positions), OWNER);
    }
}

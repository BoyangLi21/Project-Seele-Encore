package com.projectseele.client.render;

import com.projectseele.entity.*;
import net.minecraft.util.Mth;
import org.joml.Quaternionf;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.util.*;

/**
 * Operating the fixed Yashima emplacement. The server already solves the
 * prone body and both hands onto the gun's grips inside EvaBodyPose (the same
 * pose that places the shot's optical origin); this owner draws exactly that
 * sample instead of the hand-held cannon's prone clip.
 */
final class EvaFixedCannonBodyR55
{
    static final String OWNER="FIXED_CANNON_R55";
    static boolean applies(EvaUnit01Entity e)
    {
        return e.fixedCannonOperatingR52()&&e.getWeapon()==EvaUnit01Entity.WEAPON_CANNON&&e.isPilotProne()
                &&e.isPoweredOn()&&!e.isBerserk()&&!e.isExperimentalUnit()&&!e.isNervLogisticsLocked()
                &&!e.isFirstBattleActive()&&!EvaShutdownR30.disabled(e);
    }
    static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity e,BakedGeoModel m,float partial)
    {
        var body=EvaBodyPose.sample(e,partial);
        PhysicalBodyRenderer.pivots(body,m);
        Set<String> written=new HashSet<>();
        for(String name:body.rig.keySet())if(!name.startsWith("finger_"))m.getBone(name).ifPresent(b->
        {
            EvaRigTransforms.rotate(b,body.rotations.get(name));var p=body.positions.get(name);
            b.setPosX(-p.x*16);b.setPosY(p.y*16);b.setPosZ(p.z*16);written.add(name);
        });
        // The helmet follows the pilot's sight relative to the solved neck,
        // as the other full-body owners do; absolute look would undo the
        // prone neck counter-rotation and point the visor at the ground.
        m.getBone("head").ifPresent(b->EvaRigTransforms.rotate(b,new Quaternionf(body.rotations.get("head"))
                .rotateY(-e.pilotHeadYawForRender(partial)*Mth.DEG_TO_RAD).rotateX(-e.pilotHeadPitchForRender(partial)*Mth.DEG_TO_RAD)));
        return new EvaMotionEngineV2.BoneWrites(Set.copyOf(written),Set.copyOf(written),OWNER);
    }
    private EvaFixedCannonBodyR55(){}
}

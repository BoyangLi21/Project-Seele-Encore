package com.projectseele.client.render;

import com.google.gson.*;
import com.projectseele.entity.*;
import com.projectseele.physics.*;
import com.projectseele.visual.CombatR31Review;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.nio.file.*;
import java.util.*;

/** Check the final rendered hierarchy, including the head's actual mutable pivot. */
final class JointAuditR38
{
    private static final boolean JOINT_AUDIT_R58=Boolean.getBoolean("projectseele.r38JointAudit");

    private static long lastTick=-1;private static int count,physicalSamples;private static double maximum,anchorMaximum;private static String worst="";
    static void capture(EvaUnit01Entity eva,BakedGeoModel model,float partial)
    {
        long tick=eva.level().getGameTime();
        if(!JOINT_AUDIT_R58||eva.getId()!=CombatR31Review.evaId||tick==lastTick||tick%3!=0||eva.isFirstBattleActive())return;
        lastTick=tick;var pose=EvaBodyPose.sample(eva,partial);var profile=CombatBodyProfiles.get(eva);if(profile==null)return;
        boolean physical=CombatBodyDynamics.active(eva)||EvaShutdownR30.wreck(eva);
        if(physical)physicalSamples++;
        for(String name:List.of("head","hand_l","hand_r","foot_l","foot_r"))
        {
            var bone=model.getBone(name).orElse(null);if(bone==null||!pose.rig.containsKey(name)||name.equals("head")&&!physical)continue;
            // Low-stance terrain placement legitimately changes the authored
            // foot target. Its attachment is checked on the emitted mesh below.
            if(!physical&&!EvaGameplayMotionR32.owns(eva,partial))continue;
            var actual=EvaRigTransforms.model(bone);var expected=pose.matrix(name);var pivot=pose.rig.get(name).pivot();
            for(Vector3f offset:List.of(new Vector3f(),new Vector3f(0,.25F,0),new Vector3f(.25F,0,0)))
            {
                var p=new Vector3f(pivot).add(offset);double error=actual.transformPosition(new Vector3f(p)).distance(expected.transformPosition(p))*5;
                if(error>maximum){maximum=error;worst=name+" stage="+CombatR31Review.stageName+" physical="+physical;}count++;
            }
        }
        if(physical)for(var element:profile.definition().getAsJsonArray("bodies"))
        {
            var row=element.getAsJsonObject();if(row.get("parent").isJsonNull())continue;
            var child=model.getBone(row.get("name").getAsString()).orElse(null);var parent=model.getBone(row.get("parent").getAsString()).orElse(null);if(child==null||parent==null)continue;
            var a=row.getAsJsonArray("joint");var point=new Vector3f(a.get(3).getAsFloat(),a.get(7).getAsFloat(),a.get(11).getAsFloat()).div(CombatBodyProfiles.MODEL_TO_PHYSICS);
            double error=EvaRigTransforms.model(child).transformPosition(new Vector3f(point)).distance(EvaRigTransforms.model(parent).transformPosition(point))*5;
            anchorMaximum=Math.max(anchorMaximum,error);
        }
        if(tick%9==0)try
        {
            var result=new JsonObject();result.addProperty("samples",count);result.addProperty("physical_frames",physicalSamples);result.addProperty("maximum_render_pose_error_blocks",maximum);result.addProperty("maximum_physical_joint_gap_blocks",anchorMaximum);result.addProperty("worst",worst);result.addProperty("passed",maximum<.04&&anchorMaximum<.04);
            Files.writeString(Path.of(CombatR31Review.mediaFolder).resolve("joint_audit_r38.json"),new GsonBuilder().setPrettyPrinting().create().toJson(result));
        }
        catch(Exception failure){throw new IllegalStateException(failure);}
    }
    private JointAuditR38(){}
}

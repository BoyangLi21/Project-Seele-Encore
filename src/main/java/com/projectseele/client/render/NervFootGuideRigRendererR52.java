package com.projectseele.client.render;
import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.entity.*;
import com.projectseele.world.*;
import com.google.gson.JsonArray;
import java.util.*;
/** Same declared foot-guide triangles/actual frames as the source collision. */
final class NervFootGuideRigRendererR52 {
 private static final Map<String,RigidMachineryPartR44> PARTS=new HashMap<>();
 static void clear(){PARTS.clear();}
 static void render(PoseStack poses,int light,EvaUnit01Entity e,float partial){if(!EvaMechanicalFrameR52.groundGuidesDeclaredR52(e))return;try{var root=EvaMechanicalFrameR52.carrierFrameR52(e,partial);for(var d:NervFootGuideRigR52.draws(e,partial)){var mesh=PARTS.computeIfAbsent(d.part().name(),key->{var a=new JsonArray();for(double v:d.part().rgb())a.add(v);return RigidMachineryPartR44.triangles(a);});var local=root.inverse().compose(d.frame());poses.pushPose();poses.translate(local.translation().x,local.translation().y,local.translation().z);poses.mulPose(local.rotation());mesh.draw(poses,TvFacilityMeshes.currentBuffers(),light);poses.popPose();}}catch(java.io.IOException unavailable){throw new IllegalStateException("Declared actual guide source unavailable",unavailable);}}
 private NervFootGuideRigRendererR52(){}
}

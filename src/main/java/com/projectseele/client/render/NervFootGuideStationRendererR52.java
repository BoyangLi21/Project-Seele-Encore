package com.projectseele.client.render;
import com.google.gson.JsonArray;
import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.world.NervFootGuideStationR52;
import java.util.*;
import net.minecraft.client.renderer.MultiBufferSource;
/** Fixed station pieces use their accepted canonical sample and world frame. */
final class NervFootGuideStationRendererR52 {
 private static final Map<String,RigidMachineryPartR44> PARTS=new HashMap<>();
 static void render(NervCarrierPlatformEntity entity,float partial,PoseStack poses,MultiBufferSource buffers,int light){try{for(var p:NervFootGuideStationR52.actualPartsR52(entity,partial)){String key=entity.getUUID()+"/"+p.name()+"/"+Arrays.hashCode(p.rgb());var part=PARTS.computeIfAbsent(key,id->{var data=new JsonArray();for(double value:p.rgb())data.add(value);return RigidMachineryPartR44.triangles(data);});var relative=p.frame().translation().subtract(entity.getPosition(partial));poses.pushPose();poses.translate(relative.x,relative.y,relative.z);poses.mulPose(p.frame().rotation());part.draw(poses,buffers,light);poses.popPose();}}catch(java.io.IOException unavailable){throw new IllegalStateException("Actual fixed station source unavailable",unavailable);}}
 private NervFootGuideStationRendererR52(){}
}

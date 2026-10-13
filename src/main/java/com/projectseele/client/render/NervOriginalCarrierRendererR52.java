package com.projectseele.client.render;
import com.google.gson.JsonArray;
import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.world.*;
import java.util.*;
import net.minecraft.client.renderer.MultiBufferSource;
/** Exactly one rendering of each original imported carrier controller. */
final class NervOriginalCarrierRendererR52 {
 private static final Map<String,RigidMachineryPartR44> GUIDES=new HashMap<>();
 static void render(NervCarrierPlatformEntity e,float partial,PoseStack poses,MultiBufferSource buffers,int light){try{var root=NervOriginalCarrierR52.actualRoot(e,partial);var relative=root.translation().subtract(e.getPosition(partial));poses.pushPose();poses.translate(relative.x,relative.y,relative.z);poses.mulPose(root.rotation());if(!TripoMachineryR48.originalCarrier(poses,buffers,light,e.getUnitVariant(),NervOriginalCarrierR52.progress(e,partial)))throw new IllegalStateException("Original imported carrier source unavailable");if(TripoMachineryR48.selectedRunningDeckR52())NervLegacyCarrierRideRendererR52.draw(e,partial,root,poses,buffers,light);for(var d:NervOuterCarrierGuideR52.partsAt(root,NervOriginalCarrierR52.progress(e,partial),NervOriginalCarrierR52.uprightDirectionR52(e,partial))){var mesh=GUIDES.computeIfAbsent(NervOuterCarrierGuideR52.SOURCE_SHA+"/"+d.name(),key->{return RigidMachineryPartR44.trianglesNormalizedR52(d.rgb());});var frame=root.inverse().compose(d.frame());poses.pushPose();poses.translate(frame.translation().x,frame.translation().y,frame.translation().z);poses.mulPose(frame.rotation());mesh.draw(poses,buffers,light);poses.popPose();}poses.popPose();}catch(java.io.IOException missing){throw new IllegalStateException("Actual original carrier source unavailable",missing);}}
 private NervOriginalCarrierRendererR52(){}
}

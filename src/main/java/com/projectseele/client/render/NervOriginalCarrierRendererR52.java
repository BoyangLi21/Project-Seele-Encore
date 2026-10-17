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
 static void render(NervCarrierPlatformEntity e,float partial,PoseStack poses,MultiBufferSource buffers,int light)
 {
  var root=NervOriginalCarrierR52.actualRoot(e,partial);float rise=NervOriginalCarrierR52.progress(e,partial);
  boolean parked=NervR50CarrierModeR53.enabled()&&root.translation().y< -1000&&rise==0&&!e.originalCarrierStateR52().getBoolean("Attached");
  var relative=root.translation().subtract(e.getPosition(partial));poses.pushPose();poses.translate(relative.x,relative.y,relative.z);poses.mulPose(root.rotation());
  if(parked)
  {
   // Keep the original reel module at the imported rack's measured cable datum.
   poses.translate(-9.883578028,44.292063155-47,4.967775196-9.3);
   TvFacilityMeshes.draw("carrier_power_reel",poses,light);
  }
  else
  {
   poses.translate(0,NervR50CarrierModeR53.launchDeckDropR53(root,rise),0);
   if(!TripoMachineryR48.originalCarrier(poses,buffers,light,e.getUnitVariant(),NervR50CarrierModeR53.enabled()&&NervR50CarrierModeR53.launchDeckDropR53(root,0)!=0?1:rise))throw new IllegalStateException("Original imported carrier source unavailable");
   poses.translate(-9.883578028,44.292063155-47+(NervR50CarrierModeR53.launchDeckDropR53(root,0)!=0?0:-64D*(1-rise)),4.967775196-9.3);
   TvFacilityMeshes.draw("carrier_power_reel",poses,light);
  }
  poses.popPose();
 }
 private NervOriginalCarrierRendererR52(){}
}

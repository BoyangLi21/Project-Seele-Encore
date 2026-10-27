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
  var root=NervOriginalCarrierR52.actualRoot(e,partial);float rise=NervOriginalCarrierR52.progress(e,partial);var mounting=CarrierMountProfileR53.read(e,partial);
  boolean parked=!mounting.aboveFloor()&&NervR50CarrierModeR53.enabled()&&root.translation().y< -1000&&rise==0&&!e.originalCarrierStateR52().getBoolean("Attached");
  var dispatcher=new net.minecraft.world.phys.Vec3(net.minecraft.util.Mth.lerp((double)partial,e.xOld,e.getX()),net.minecraft.util.Mth.lerp((double)partial,e.yOld,e.getY()),net.minecraft.util.Mth.lerp((double)partial,e.zOld,e.getZ()));
  var relative=root.translation().subtract(dispatcher);poses.pushPose();poses.translate(relative.x,relative.y,relative.z);poses.mulPose(root.rotation());
  if(CarrierAssemblyR53.selected()!=null)
  {
   if(!parked)
   {
    boolean outlet=NervR50CarrierModeR53.launchDeckDropR53(root,0)!=0;
    poses.translate(0,NervR50CarrierModeR53.launchDeckDropR53(root,rise),0);
    CarrierAssemblyRendererR53.draw(poses,buffers,light,outlet?1:rise,outlet?NervR50CarrierModeR53.launchJawReleaseR53(rise):0,0,e.getUnitVariant(),mounting);
   }
   poses.popPose();if(!parked&&!mounting.supportOnly())CarrierRearGuideRendererR53.drawMoving(e,partial,poses,buffers,light,root,rise);return;
  }
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

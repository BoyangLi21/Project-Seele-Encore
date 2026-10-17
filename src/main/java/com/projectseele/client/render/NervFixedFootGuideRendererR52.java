package com.projectseele.client.render;
import com.google.gson.JsonArray;
import com.projectseele.world.*;
import java.util.*;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.LevelRenderer;
import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.*;
import net.minecraftforge.client.event.RenderLevelStageEvent;

/** Installed Root guide parts share the common actual triangle inventory. */
final class NervFixedFootGuideRendererR52 {
 private record Draw(RigidMachineryPartR44 mesh,RigidTransform frame,AABB bounds,NervFixedFootGuidesR52.Anchor anchor){}
 private static NervStaticSpatialIndexR52<Draw> index;
 private static List<Draw> nearby=List.of();
 private static BlockPos cameraCell;
 static void clear(){index=null;nearby=List.of();cameraCell=null;}
 private static double worldBound(double value){return Math.max(-30_000_000,Math.min(30_000_000,value));}

 static NervFixedFootGuidesR52.Anchor nearestAnchor(Vec3 centre,NervStaticSpatialIndexR52<NervFixedFootGuidesR52.Anchor> anchors)
 {
  for(double radius=16;radius<=65536;radius*=2)
  {
   var candidates=anchors.query(new AABB(centre,centre).inflate(radius));
   if(candidates.isEmpty())continue;
   var nearest=candidates.stream().min(Comparator.comparingDouble(a->a.actualBearing().distanceToSqr(centre))).orElseThrow();
   double distance=nearest.actualBearing().distanceTo(centre);
   // A cube corner may be farther than its radius. Include the complete
   // Euclidean ball before making the final nearest-anchor selection.
   if(distance>=radius)candidates=anchors.query(new AABB(centre,centre).inflate(distance+.000001));
   return candidates.stream().min(Comparator.comparingDouble(a->a.actualBearing().distanceToSqr(centre))).orElseThrow();
  }
  throw new IllegalStateException("Actual guide anchor unavailable");
 }

 private static void load()throws java.io.IOException
 {
  var anchors=new NervStaticSpatialIndexR52<>(NervFixedFootGuidesR52.anchors(),a->new AABB(a.actualBearing(),a.actualBearing()));
  var result=new ArrayList<Draw>();
  for(var p:NervFixedFootGuidesR52.pieces())
  {
   var rgb=new JsonArray();for(double v:p.rgb())rgb.add(v);
   var bounds=p.mesh().envelope(p.frame(),p.frame());var closest=nearestAnchor(bounds.getCenter(),anchors);
   result.add(new Draw(RigidMachineryPartR44.triangles(rgb),p.frame(),bounds,closest));
  }
  index=new NervStaticSpatialIndexR52<>(result,Draw::bounds);
 }

 static void draw(RenderLevelStageEvent event,ClientLevel level)
 {
  if(com.projectseele.world.NervR50CarrierModeR53.enabled())return;
  if(!com.projectseele.client.FacilityFrameClientR52.claimed(level))return;
  try
  {
   if(index==null)load();
   var camera=event.getCamera().getPosition();var cell=new BlockPos((int)Math.floor(camera.x/32),(int)Math.floor(camera.y/32),(int)Math.floor(camera.z/32));
   if(!cell.equals(cameraCell))
   {
    // Covers all 180 m view cubes in this camera cell. Exact original
    // per-part bounds and live anchor checks still run below.
    nearby=index.query(new AABB(worldBound(cell.getX()*32.-180),worldBound(cell.getY()*32.-180),worldBound(cell.getZ()*32.-180),
      worldBound((cell.getX()+1)*32.+180),worldBound((cell.getY()+1)*32.+180),worldBound((cell.getZ()+1)*32.+180)));cameraCell=cell;
   }
   var view=new AABB(camera,camera).inflate(180);var poses=event.getPoseStack();
   for(var d:nearby)
   {
    if(!view.intersects(d.bounds()))continue;
    var at=BlockPos.containing(d.bounds().getCenter());var anchor=d.anchor();
    if(!level.hasChunkAt(at)||!level.hasChunkAt(anchor.at())||!level.getBlockState(anchor.at()).getBlock().builtInRegistryHolder().key().location().toString().equals(anchor.state()))continue;
    poses.pushPose();var p=d.frame().translation().subtract(camera);poses.translate(p.x,p.y,p.z);poses.mulPose(d.frame().rotation());
    d.mesh().draw(poses,TvFacilityMeshes.currentBuffers(),LevelRenderer.getLightColor(level,at));poses.popPose();
   }
  }
  catch(java.io.IOException missing){throw new IllegalStateException("Actual Root foot-guide source unavailable",missing);}
 }
 private NervFixedFootGuideRendererR52(){}
}

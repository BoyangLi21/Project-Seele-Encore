package com.projectseele.client.render;

import com.google.gson.JsonArray;
import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.world.*;
import java.io.IOException;
import java.util.*;
import net.minecraft.client.renderer.MultiBufferSource;

/** The accepted four-slide pose and every visible steel member come from
 * the same source used by the private native sweep proof. */
final class NervLegacyCarrierRideRendererR52 {
 private static final Map<double[],RigidMachineryPartR44> CACHE=new IdentityHashMap<>();
 static void clear(){CACHE.clear();}
 private static RigidMachineryPartR44 mesh(NervLegacyCarrierRideR52.Piece part){return CACHE.computeIfAbsent(part.rgb(),values->{var a=new JsonArray();for(double value:values)a.add(value);return RigidMachineryPartR44.triangles(a);});}
 /** Called with the original carrier's actual root already on the stack. */
 static void draw(NervCarrierPlatformEntity e,float partial,RigidTransform root,PoseStack poses,MultiBufferSource buffers,int light)throws IOException {for(var part:NervLegacyCarrierRideR52.partsAtR52(e.getUnitVariant(),root,NervOriginalCarrierR52.progress(e,partial),NervOriginalCarrierR52.actualRidePoseR52(e,partial))){var local=root.inverse().compose(part.frame());poses.pushPose();poses.translate(local.translation().x,local.translation().y,local.translation().z);poses.mulPose(local.rotation());mesh(part).draw(poses,buffers,light);poses.popPose();}}
 static void drawFixed(NervLegacyCarrierRideR52.Piece part,net.minecraft.world.phys.Vec3 camera,PoseStack poses,MultiBufferSource buffers,int light){var f=part.frame();var p=f.translation().subtract(camera);poses.pushPose();poses.translate(p.x,p.y,p.z);poses.mulPose(f.rotation());mesh(part).draw(poses,buffers,light);poses.popPose();}
 private NervLegacyCarrierRideRendererR52(){}
}

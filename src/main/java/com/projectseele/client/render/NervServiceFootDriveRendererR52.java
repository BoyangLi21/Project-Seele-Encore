package com.projectseele.client.render;
import com.google.gson.JsonArray;
import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.world.*;
import java.util.*;

/** The independent lift/bridge uses exactly the common accepted source. */
final class NervServiceFootDriveRendererR52 {
 private static final Map<String,RigidMachineryPartR44> PARTS=new HashMap<>();
 static void render(PoseStack poses,int light,NervCarrierPlatformEntity e,float partial){if(e.declaredServiceFootDriveR52()==null)return;try{var root=RigidTransform.of(e.position(),e.declaredMachineRotationR52());for(var p:NervServiceFootDriveR52.pieces(e,partial)){String key=p.name()+":"+p.mesh().bounds();var mesh=PARTS.computeIfAbsent(key,k->{var rgb=new JsonArray();for(double c:p.rgb())rgb.add(c);return RigidMachineryPartR44.triangles(rgb);});var f=root.inverse().compose(p.frame());poses.pushPose();poses.translate(f.translation().x,f.translation().y,f.translation().z);poses.mulPose(f.rotation());mesh.draw(poses,TvFacilityMeshes.currentBuffers(),light);poses.popPose();}NervLegacyCarrierRideRendererR52.drawLead(e,partial,poses,TvFacilityMeshes.currentBuffers(),light);}catch(java.io.IOException missing){throw new IllegalStateException("Declared actual service lift source unavailable",missing);}}
 private NervServiceFootDriveRendererR52(){}
}

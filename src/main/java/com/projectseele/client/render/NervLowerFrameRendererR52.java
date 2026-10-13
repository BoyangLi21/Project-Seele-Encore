package com.projectseele.client.render;
import com.google.gson.JsonArray;
import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.world.NervLowerFrameR52;
import java.util.*;

/** Draw the same RGB triangles and actual actuator/rope geometry as physics. */
final class NervLowerFrameRendererR52 {
    private static final Map<String,RigidMachineryPartR44> STATIC=new HashMap<>();
    static void render(PoseStack poses,int light,float progress){try{for(var piece:NervLowerFrameR52.pieces(progress)){RigidMachineryPartR44 mesh;if(piece.kind().equals("rope")){var a=new JsonArray();for(double v:piece.rgb())a.add(v);mesh=RigidMachineryPartR44.triangles(a);}else mesh=STATIC.computeIfAbsent(piece.name(),name->{var a=new JsonArray();for(double v:piece.rgb())a.add(v);return RigidMachineryPartR44.triangles(a);});poses.pushPose();var p=piece.local().translation();poses.translate(p.x,p.y,p.z);mesh.draw(poses,TvFacilityMeshes.currentBuffers(),light);poses.popPose();}}catch(java.io.IOException e){throw new IllegalStateException("Actual engineered lower frame source missing",e);}}
    private NervLowerFrameRendererR52(){}
}

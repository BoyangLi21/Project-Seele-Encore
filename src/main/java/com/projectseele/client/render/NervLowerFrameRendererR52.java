package com.projectseele.client.render;
import com.google.gson.JsonArray;
import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.world.NervLowerFrameR52;
import java.util.*;

/** Draw the same RGB triangles and actual actuator/rope geometry as physics. */
final class NervLowerFrameRendererR52 {
    private static final Map<String,RigidMachineryPartR44> STATIC=new HashMap<>();
    private static final String ROPE_MATERIAL_R60="projectseele:textures/entity/machinery_paint_r44.png/byte-rgb-quads";
    private record RopeKeyR60(String source,String name,String material,long[] bits){
        RopeKeyR60{bits=bits.clone();}
        @Override public long[] bits(){return bits.clone();}
        @Override public boolean equals(Object other){return other instanceof RopeKeyR60 key&&source.equals(key.source)&&name.equals(key.name)&&material.equals(key.material)&&Arrays.equals(bits,key.bits);}
        @Override public int hashCode(){return Objects.hash(source,name,material,Arrays.hashCode(bits));}
    }
    private static final LinkedHashMap<RopeKeyR60,RigidMachineryPartR44> ROPES_R60=new LinkedHashMap<>(64,.75F,true);
    /** Idle ropes still have real short steel spans. Reuse exact source bits, never quantize their motion. */
    static RigidMachineryPartR44 ropeMeshR60(String name,double[] rgb){
        var bits=new long[rgb.length];for(int i=0;i<bits.length;i++)bits[i]=Double.doubleToRawLongBits(rgb[i]);var key=new RopeKeyR60(NervLowerFrameR52.SOURCE_SHA,name,ROPE_MATERIAL_R60,bits);var mesh=ROPES_R60.get(key);if(mesh!=null)return mesh;
        var a=new JsonArray();for(double v:rgb)a.add(v);mesh=RigidMachineryPartR44.triangles(a);ROPES_R60.put(key,mesh);if(ROPES_R60.size()>64){var iterator=ROPES_R60.entrySet().iterator();var oldest=iterator.next();iterator.remove();RigidMachineryGpuR44.releaseR52(oldest.getValue());}return mesh;
    }
    static void render(PoseStack poses,int light,float progress){try{for(var piece:NervLowerFrameR52.pieces(progress)){RigidMachineryPartR44 mesh;if(piece.kind().equals("rope")){mesh=ropeMeshR60(piece.name(),piece.rgb());}else mesh=STATIC.computeIfAbsent(piece.name(),name->{var a=new JsonArray();for(double v:piece.rgb())a.add(v);return RigidMachineryPartR44.triangles(a);});poses.pushPose();var p=piece.local().translation();poses.translate(p.x,p.y,p.z);mesh.draw(poses,TvFacilityMeshes.currentBuffers(),light);poses.popPose();}}catch(java.io.IOException e){throw new IllegalStateException("Actual engineered lower frame source missing",e);}}
    private NervLowerFrameRendererR52(){}
}

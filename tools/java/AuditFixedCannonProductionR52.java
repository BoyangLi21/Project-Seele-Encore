package com.projectseele.world;
import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;
/** Read-only production geometry audit against the accepted original skin and hatch. */
public final class AuditFixedCannonProductionR52
{
    public static void main(String[] args)throws Exception
    {
        var root=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();var g=com.projectseele.entity.YashimaCannonGeometryR52.parse(root);var at=AuditFixedCannonCradleR52.vec(root.getAsJsonArray("raised_position"));var closed=at.add(0,-16.5,0);var spec=new FixedCannonCradleR52.Spec(160,157.5,174);var skin=AuditFixedCannonCradleR52.read(Path.of(args[1]));var body=RigidTransform.of(AuditFixedCannonCradleR52.vec(root.getAsJsonArray("prone_position")),new Quaternionf().rotationY((180-root.get("prone_yaw").getAsFloat())*(float)Math.PI/180));
        var hatch=AuditFixedCannonCradleR52.read(Path.of(args[2]));var hatchFrame=RigidTransform.of(at,new Quaternionf());var report=new LinkedHashMap<String,Object>();var skinCuts=new ArrayList<String>();var hatchCuts=new ArrayList<String>();var liftSkinCuts=new ArrayList<String>();var liftHatchCuts=new ArrayList<String>();var parts=new LinkedHashMap<String,double[]>();int count=0;
        var actual=FixedCannonCradleR52.pieces(g,spec,at,new Quaternionf());var gunMethod=YashimaCannonMeshR52.class.getDeclaredMethod("gun",float.class);gunMethod.setAccessible(true);var gun=(NervRigidMeshSweepR52)gunMethod.invoke(null,g.scale());var matrix=g.matrix(at,new Quaternionf());var gunFrame=RigidTransform.of(new Vec3(matrix.getTranslation(new org.joml.Vector3f())),matrix.getUnnormalizedRotation(new Quaternionf()).normalize());var gunCuts=new ArrayList<String>();var contactProbes=new ArrayList<Object>();
        for(var p:actual)
        {
            String name=p.part().name()+"/"+(count++);for(var limb:skin.entrySet())if(p.mesh().intersects(p.frame(),p.frame(),limb.getValue(),body,body,.001,Vec3.ZERO))skinCuts.add(name+":"+limb.getKey());
            if(p.mesh().intersects(p.frame(),p.frame(),gun,gunFrame,gunFrame,.001,Vec3.ZERO))gunCuts.add(name);
            if(p.part().name().startsWith("saddle_")){int index=p.part().name().equals("saddle_0")?9023:986;var n=new Vec3(g.rotation().transform(YashimaCannonMeshR52.sourceNormalR52(index).toVector3f())).normalize();var shifted=RigidTransform.of(p.frame().translation().add(n.scale(.0002)),p.frame().rotation());contactProbes.add(Map.of("part",name,"outside_shift_m",.0002,"intersects_gun_after_outward_shift",p.mesh().intersects(shifted,shifted,gun,gunFrame,gunFrame,.001,Vec3.ZERO)));}
            for(var door:hatch.entrySet())if(p.mesh().intersects(p.frame(),p.frame(),door.getValue(),hatchFrame,hatchFrame,.001,Vec3.ZERO))hatchCuts.add(name+":"+door.getKey());
            var v=p.mesh().triangles();for(int n=0;n<v.length;n+=3){var point=p.frame().transformPoint(new Vec3(v[n],v[n+1],v[n+2])).subtract(at);v[n]=point.x;v[n+1]=point.y;v[n+2]=point.z;}parts.put(name,v);
        }
        var lift=FixedCannonCradleR52.sweep(g,spec,closed,at,new Quaternionf(),new Quaternionf());for(var limb:skin.entrySet())if(lift.intersects(limb.getValue(),body))liftSkinCuts.add(limb.getKey());for(var door:hatch.entrySet())if(lift.intersects(door.getValue(),hatchFrame))liftHatchCuts.add(door.getKey());
        var b=FixedCannonCradleR52.bounds(g,spec,closed,new Quaternionf());report.put("closed_bounds_world",List.of(b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ));report.put("closed_margin_below_hatch_plane_m",174.02-b.maxY);b=FixedCannonCradleR52.bounds(g,spec,at,new Quaternionf());report.put("raised_bounds_world",List.of(b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ));report.put("actual_piece_count",actual.size());report.put("actual_body_parts_including_hands",skin.size());report.put("raised_body_intersections",skinCuts);report.put("raised_hatch_intersections",hatchCuts);report.put("whole_lift_body_intersections",liftSkinCuts);report.put("whole_lift_hatch_intersections",liftHatchCuts);
        report.put("gun_surface_intersections_including_intended_support",gunCuts);report.put("saddle_surface_contact_probes",contactProbes);report.put("same_server_client_spec_roundtrip",spec.equals(FixedCannonCradleR52.Spec.decode(spec.encode())));var aimRows=new ArrayList<Object>();
        for(int axis=0;axis<3;axis++)for(float degrees:new float[]{-2,2}){var q=new Quaternionf().rotationAxis(degrees*(float)Math.PI/180,axis==0?1:0,axis==1?1:0,axis==2?1:0);try{var sweep=FixedCannonCradleR52.sweep(g,spec,at,at,new Quaternionf(),q);var blocked=new ArrayList<String>();for(var door:hatch.entrySet())if(sweep.intersects(door.getValue(),hatchFrame))blocked.add(door.getKey());aimRows.add(Map.of("axis",axis,"degrees",degrees,"real_strut_overlap_admitted",true,"hatch_sweep_intersections",blocked));}catch(IllegalArgumentException e){aimRows.add(Map.of("axis",axis,"degrees",degrees,"real_strut_overlap_admitted",false,"reason",e.getMessage()));}}
        report.put("same_aim_curve_samples",aimRows);report.put("world_written",false);report.put("native_acceptance",false);report.put("scope","Compiled production draw/proof source; complete approved same-frame actual skin and exact open source hatch. Does not certify a native button/campaign run.");
        AuditFixedCannonCradleR52.write(Path.of(args[3]).resolveSibling("cradle_production_raised.bin.gz"),parts);Files.writeString(Path.of(args[3]),new GsonBuilder().setPrettyPrinting().create().toJson(report));System.out.println(new Gson().toJson(report));
    }
}

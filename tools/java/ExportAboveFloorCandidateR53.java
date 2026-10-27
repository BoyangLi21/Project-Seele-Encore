package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Isolated rear hardware candidate with unchanged real track-head world frames. */
public final class ExportAboveFloorCandidateR53
{
    private static double[] frame(RigidTransform f)
    {var p=f.translation();return new double[]{p.x,p.y,p.z,f.qx(),f.qy(),f.qz(),f.qw()};}
    private static String sha(byte[] b)throws Exception
    {return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(b));}
    public static void main(String[] args)throws Exception
    {
        var bytes=Files.readAllBytes(Path.of(args[0]));var h=CarrierRearGuideR53.readHardware(bytes,"uninstalled-floor-candidate");
        var candidate=new CandidateAboveFloorCarrierProfileR53(h);var source=JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject();
        var parts=new ArrayList<Object>();var names=new ArrayList<Object>();
        for(var p:candidate.templates())
        {
            parts.add(Map.of("name",p.name().substring("rear/".length()),"frame",p.frame(),"role",p.role(),"triangles_rgb",p.rgb()));
            names.add(Map.of("name",p.name(),"frame",p.frame(),"role",p.role()));
        }
        var document=new Gson().toJson(Map.of("schema","projectseele.r53.above-floor-rear-diagnostic.v1","parts",parts,
            "baseline_sha256",sha(bytes),"source_heads_unchanged",true,"static_rails_changed",false,"installed",false,
            "load_y",CandidateAboveFloorCarrierProfileR53.LOAD_Y,"bay_stroke",CandidateAboveFloorCarrierProfileR53.BAY_STROKE));
        var hw=document.getBytes(java.nio.charset.StandardCharsets.UTF_8);Files.write(Path.of(args[2]),hw);
        var poses=new ArrayList<Object>();int equalityChecks=0;
        for(var raw:source.getAsJsonArray("legs"))
        {
            var leg=raw.getAsJsonObject();String id=leg.get("leg").getAsString();var rows=leg.getAsJsonArray("samples");
            for(var sample:rows)
            {
                var row=sample.getAsJsonObject();var v=row.getAsJsonArray("root");var q=row.getAsJsonArray("rotation");var d=row.getAsJsonArray("tangent");
                var root=new RigidTransform(new Vec3(v.get(0).getAsDouble(),v.get(1).getAsDouble(),v.get(2).getAsDouble()),q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat());
                var direction=new Vec3(d.get(0).getAsDouble(),d.get(1).getAsDouble(),d.get(2).getAsDouble());double lift=id.contains("/exit")?0:CarrierRearGuideR53.STOW_LIFT;
                var a=h.partsAt(root,1,direction,0,lift);var b=candidate.rearPartsAt(root,1,direction,0,lift);
                for(int i=0;i<a.size();i++)if(!h.parts().get(i).frame().equals("ROOT")&&!a.get(i).name().endsWith("/lift_rod"))
                {
                    if(!a.get(i).frame().equals(b.get(i).frame())||a.get(i).mesh()!=b.get(i).mesh())throw new IllegalStateException("Original world head or moving arm changed");
                    equalityChecks++;
                }
            }
            if(!id.endsWith("/original_incline"))continue;
            var row=rows.get(0).getAsJsonObject();var v=row.getAsJsonArray("root");var q=row.getAsJsonArray("rotation");
            var root=new RigidTransform(new Vec3(v.get(0).getAsDouble(),v.get(1).getAsDouble(),v.get(2).getAsDouble()),q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat());
            for(int n=0;n<=40;n++)
            {
                float rise=n/40F;var frames=new ArrayList<double[]>();
                for(var p:candidate.rearPartsAt(root,rise,root.transformVector(new Vec3(0,0,1)),0,CarrierRearGuideR53.STOW_LIFT))frames.add(frame(p.frame()));
                poses.add(Map.of("leg",id.replace("original_incline","above_floor_rebased_rear"),"metres",rise,"rise",rise,"root",frame(root),"frames",frames));
            }
        }
        Files.writeString(Path.of(args[3]),new Gson().toJson(Map.of("installed",false,"world_written",false,"continuous_proof",false,
            "kinematics","CandidateAboveFloorCarrierProfileR53.rearPartsAt (uninstalled candidate)","parts",names,"poses",poses,"hardware_sha256",sha(hw),
            "unchanged_world_head_pose_and_mesh_checks",equalityChecks)));
        System.out.println("rise_poses="+poses.size()+" exact_original_head_frame_checks="+equalityChecks);
    }
    private ExportAboveFloorCandidateR53(){}
}

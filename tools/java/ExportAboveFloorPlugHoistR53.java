package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Uninstalled candidate, using original source geometry and the production hoist evaluator. */
public final class ExportAboveFloorPlugHoistR53
{
    private static Vec3 vector(JsonArray a){return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
    private static RigidTransform frame(JsonObject o)
    {var q=o.getAsJsonArray("quaternion");return new RigidTransform(vector(o.getAsJsonArray("position")),q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat());}
    private static double[] values(RigidTransform f){var p=f.translation();return new double[]{p.x,p.y,p.z,f.qx(),f.qy(),f.qz(),f.qw()};}
    private static String sha(byte[] b)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(b));}
    private static double smooth(double t){t=Math.max(0,Math.min(1,t));return t*t*(3-2*t);}
    // Same original three-phase insertion law; the lead-in distance is an explicit candidate input.
    private static RigidTransform plug(RigidTransform socket,RigidTransform dock,double progress,double approach)
    {
        var lead=new RigidTransform(new Vec3(0,0,approach),0,0,0,1);RigidTransform local;
        if(progress<=EntryPlugKinematics.DOCK_PHASE_END)local=socket.inverse().compose(dock).interpolate(lead,smooth(progress/EntryPlugKinematics.DOCK_PHASE_END));
        else if(progress<=EntryPlugKinematics.ALIGN_PHASE_END)local=lead.interpolate(RigidTransform.identity(),smooth((progress-EntryPlugKinematics.DOCK_PHASE_END)/(EntryPlugKinematics.ALIGN_PHASE_END-EntryPlugKinematics.DOCK_PHASE_END)));
        else{double s=smooth((progress-EntryPlugKinematics.ALIGN_PHASE_END)/(1-EntryPlugKinematics.ALIGN_PHASE_END));double turn=smooth((progress-NervAssemblyClocksR52.CRANE_HANDOFF_PROGRESS)/(1-NervAssemblyClocksR52.CRANE_HANDOFF_PROGRESS));local=new RigidTransform(new Vec3(0,0,-EntryPlugKinematics.LOCK_DEPTH_BLOCKS*s),0,0,(float)Math.sin(Math.PI*turn),(float)Math.cos(Math.PI*turn));}
        return socket.compose(local);
    }
    public static void main(String[] args)throws Exception
    {
        Path ownerFile=Path.of(args[0]),profileFile=Path.of(args[1]),out=Path.of(args[2]);double load=Double.parseDouble(args[3]),approach=Double.parseDouble(args[4]);Files.createDirectories(out);
        System.setProperty("projectseele.dorsalPoseReview",profileFile.toAbsolutePath().toString());FullAssemblyGeometryR52.installClasspath();
        var field=FullAssemblyGeometryR52.class.getDeclaredField("installed");field.setAccessible(true);var full=(FullAssemblyGeometryR52.Provider)field.get(null);
        byte[] candidate=args.length>5?Files.readAllBytes(Path.of(args[5])):null;
        byte[] gripCandidate=args.length>7?Files.readAllBytes(Path.of(args[7])):null;
        var crane=candidate==null?NervCraneGeometryR52.loadClasspath():NervCraneGeometryR52.load(path->path.equals("eva/actual_crane_procedural_triangles_r52.json")?candidate:gripCandidate!=null&&path.equals("mesh/tripo_gripper_r48.json")?gripCandidate:EvaOriginalMeshGeometryR52.classpathBytes(path),sha(candidate),gripCandidate==null?"af16832dc6c143d3c6a23eb38811021b75c13860436682e8071b9990fc83067f":sha(gripCandidate));
        boolean stableRoll=args.length>6&&Boolean.parseBoolean(args[6]);
        boolean sleeves=Boolean.getBoolean("projectseele.hoistReviewSleeves");
        double eyeZ=Double.parseDouble(System.getProperty("projectseele.hoistReviewEye","9.7"));
        var vertical=EntryPlugKinematics.class.getDeclaredMethod("verticalSocketOrientation",Vec3.class,EvaDorsalProfile.Profile.class);vertical.setAccessible(true);
        var owner=JsonParser.parseString(Files.readString(ownerFile)).getAsJsonObject();var summaries=new ArrayList<Object>();
        for(var raw:owner.getAsJsonArray("units"))
        {
            var unit=raw.getAsJsonObject();int v=unit.get("variant").getAsInt();var bay=frame(unit.getAsJsonObject("bay_frame"));var dock=frame(unit.getAsJsonObject("dock_frame"));
            var c=unit.getAsJsonObject("crane");var base=frame(c.getAsJsonObject("visual").getAsJsonObject("frame"));var rail=vector(c.getAsJsonArray("rail_axis_local"));
            var profile=EvaDorsalProfile.byVariant(v);var rear=new Vec3(0,0,-1);var orientation=(RigidTransform)vertical.invoke(null,rear,profile);var marker=profile.centreBlocks();
            var socket=new RigidTransform(bay.translation().add(rear.scale(marker.z)).add(0,marker.y+load,0),orientation.qx(),orientation.qy(),orientation.qz(),orientation.qw());
            var parts=new ArrayList<Object>();var names=new ArrayList<Object>();var source=new LinkedHashMap<String,double[]>();full.closedPlugParts(v).forEach((n,p)->source.put("capsule/"+n,p));
            var rawCrane=crane.transforms(new NervCranePoseR52.State(base,-10,dock,true,null,null).pose(crane.mount()),sleeves);for(String n:new TreeSet<>(rawCrane.keySet()))source.put("hoist/"+n,crane.sourceFor(n));
            for(var row:source.entrySet()){double[] xyz=row.getValue(),rgb=new double[xyz.length*2];for(int i=0;i<xyz.length/3;i++){System.arraycopy(xyz,i*3,rgb,i*6,3);Arrays.fill(rgb,i*6+3,i*6+6,.5);}parts.add(Map.of("name",row.getKey(),"frame",row.getKey(),"role","full_original_source","triangles_rgb",rgb));names.add(Map.of("name",row.getKey(),"frame",row.getKey(),"role","full_original_source"));}
            byte[] geometry=new Gson().toJson(Map.of("source_name_prefix","","parts",parts)).getBytes(java.nio.charset.StandardCharsets.UTF_8);
            Files.write(out.resolve("unit"+v+".mesh.json"),geometry);var poses=new ArrayList<Object>();var rejected=new ArrayList<Object>();var states=new ArrayList<Object>();double minimumHeadroom=Double.POSITIVE_INFINITY;
            int steps=Integer.getInteger("projectseele.hoistReviewSteps",40);boolean stow=Boolean.getBoolean("projectseele.hoistReviewStow");boolean handoff=Boolean.getBoolean("projectseele.hoistReviewHandoff");
            for(int step=0;step<=(stow?steps*2+1:steps);step++)
            {
                boolean coupled=step<=steps;double p=coupled?step/(double)steps:(step-steps-1)/(double)steps;var plug=plug(socket,dock,handoff?(coupled?p*NervAssemblyClocksR52.CRANE_HANDOFF_PROGRESS:NervAssemblyClocksR52.CRANE_HANDOFF_PROGRESS):coupled?p:1,approach);var eye=plug.transformPoint(new Vec3(0,0,eyeZ));var localEye=base.inverse().transformPoint(eye);double along=localEye.dot(rail)-(handoff?NervCranePoseR52.TROLLEY_TRAILING_R53:0);minimumHeadroom=Math.min(minimumHeadroom,-localEye.y);
                if(localEye.y>=0||along<c.get("rail_min").getAsDouble()||along>c.get("rail_max").getAsDouble()){rejected.add(Map.of("progress",p,"local_eye",localEye,"along",along));continue;}
                var machine=Boolean.getBoolean("projectseele.hoistReviewFixedTrolley")?frame(c.getAsJsonObject("stow_frame")):new RigidTransform(base.transformPoint(rail.scale(along)),base.qx(),base.qy(),base.qz(),base.qw());
                double bottom=Math.rint(localEye.y*1000)/1000;if(!coupled)bottom+=(Double.parseDouble(System.getProperty("projectseele.hoistReviewRest",handoff?Double.toString(NervCranePoseR52.STOW_BOTTOM_R53):"-2"))-bottom)*p;
                var state=new NervCranePoseR52.State(machine,bottom,coupled?plug:null,coupled,coupled?null:eye,coupled?null:plug.rotation());var pose=stableRoll?NervCraneBearingR53.pose(state,crane.mount()):state.pose(crane.mount());
                if(coupled&&eyeZ!=9.7){var delta=machine.inverse().transformVector(plug.transformVector(new Vec3(0,0,eyeZ-9.7)));var g=pose.grip();pose=new NervCranePoseR52.Pose(pose.machine(),new RigidTransform(g.translation().add(delta),g.qx(),g.qy(),g.qz(),g.qw()),pose.mount().add(delta),pose.yoke().add(delta),pose.released());}
                var transforms=crane.transforms(pose,sleeves);var frames=new ArrayList<double[]>();var scales=new ArrayList<double[]>();
                for(String n:source.keySet()){var t=n.startsWith("capsule/")?null:transforms.get(n.substring(6));frames.add(values(t==null?plug:t.frame()));var scale=t==null?new Vec3(1,1,1):t.scale();scales.add(new double[]{scale.x,scale.y,scale.z});}
                String leg="unit"+v+(coupled?"/candidate_insertion":"/candidate_stow");
                poses.add(Map.of("leg",leg,"metres",p,"root",values(bay),"frames",frames,"scales",scales));
                states.add(Map.of("leg",leg,"progress",p,"machine",values(machine),"bottom",bottom,"capsule",values(plug),"coupled",coupled,"reference_eye",new double[]{eye.x,eye.y,eye.z}));
            }
            Files.writeString(out.resolve("unit"+v+".frames.json"),new Gson().toJson(Map.of("parts",names,"poses",poses,"continuous_proof",false,"installed",false)));
            Files.writeString(out.resolve("unit"+v+".states.json"),new Gson().toJson(Map.of("states",states,"bearing",sleeves,"world_written",false,"installed",false)));
            summaries.add(Map.of("variant",v,"poses",poses.size(),"rail_range_rejections",rejected,"minimum_eye_headroom_m",minimumHeadroom));
        }
        var metadata=new LinkedHashMap<String,Object>();metadata.put("load_y",load);metadata.put("approach_m",approach);metadata.put("world_written",false);metadata.put("installed",false);metadata.put("original_rail_range_unchanged",true);metadata.put("variants",summaries);metadata.put("stable_gripper_roll_candidate",stableRoll);metadata.put("split_bearing",sleeves);metadata.put("eye_z",eyeZ);metadata.put("sample_steps",Integer.getInteger("projectseele.hoistReviewSteps",40));metadata.put("include_stow",Boolean.getBoolean("projectseele.hoistReviewStow"));metadata.put("fixed_declared_stow_trolley",Boolean.getBoolean("projectseele.hoistReviewFixedTrolley"));metadata.put("stow_bottom",Double.parseDouble(System.getProperty("projectseele.hoistReviewRest",Boolean.getBoolean("projectseele.hoistReviewHandoff")?Double.toString(NervCranePoseR52.STOW_BOTTOM_R53):"-2")));metadata.put("refitted_source",crane.refitted());metadata.put("continuous_proof",false);
        Files.writeString(out.resolve("summary.json"),new GsonBuilder().setPrettyPrinting().create().toJson(metadata));
        System.out.println(new Gson().toJson(summaries));
    }
}

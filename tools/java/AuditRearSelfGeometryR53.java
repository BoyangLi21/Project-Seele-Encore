package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.phys.*;

/** Full-stroke new-part self-clearance; preserves unchanged source contacts as evidence. */
public final class AuditRearSelfGeometryR53
{
    private static String suffix(String name){return name.substring(name.indexOf('/',5)+1);}
    private static String mount(String name){return name.split("/")[1];}
    private static String pair(String a,String b){return a.compareTo(b)<0?a+" | "+b:b+" | "+a;}
    private static boolean legacy(String name)
    {var s=suffix(name);return !s.equals("source_pad")&&!s.startsWith("mount/")&&!s.startsWith("lift_");}
    private static final Set<String> WELDS=Set.of(
        pair("source_pad","mount/0"),pair("mount/0","mount/1"),pair("mount/1","mount/2"),
        pair("mount/2","lift_bracket/vertical"),pair("lift_bracket/vertical","lift_bracket/weld"),
        pair("mount/4","mount/5"),pair("mount/4","lift_rod"),pair("mount/5","ball"));
    private static boolean weld(NervLegacyCarrierRideR52.Piece a,NervLegacyCarrierRideR52.Piece b,
                                NervLegacyCarrierRideR52.Piece endA,NervLegacyCarrierRideR52.Piece endB)
    {
        if(!mount(a.name()).equals(mount(b.name())))return false;
        String x=suffix(a.name()),y=suffix(b.name());
        boolean named=WELDS.contains(pair(x,y))||pair(x,y).equals(pair("lift_bracket/weld",
            mount(a.name()).equals("rear_l")?"lift_sleeve/0":"lift_sleeve/1"));
        for(int i=0;i<4;i++)named|=pair(x,y).equals(pair("lift_sleeve/"+i,"lift_tie/"+i));
        for(int i=0;i<2;i++)for(int j=2;j<4;j++)named|=pair(x,y).equals(pair("lift_tie/"+i,"lift_tie/"+j));
        // These are fixed finite joints, never permissions for a moving member.
        return named&&a.frame().equals(b.frame())&&endA.frame().equals(endB.frame())
            &&a.mesh().intersects(a.frame(),a.frame(),b.mesh(),b.frame(),b.frame(),.003,Vec3.ZERO);
    }
    private static boolean sleeve(NervLegacyCarrierRideR52.Piece a,NervLegacyCarrierRideR52.Piece b)
    {
        if(!mount(a.name()).equals(mount(b.name())))return false;
        return suffix(a.name()).equals("lift_rod")&&suffix(b.name()).startsWith("lift_sleeve/")
            ||suffix(b.name()).equals("lift_rod")&&suffix(a.name()).startsWith("lift_sleeve/");
    }
    private static boolean spherical(NervLegacyCarrierRideR52.Piece a,NervLegacyCarrierRideR52.Piece b)
    {return mount(a.name()).equals(mount(b.name()))&&pair(suffix(a.name()),suffix(b.name())).equals(pair("ball","ball_socket"));}
    private static boolean unchangedLegacy(CarrierRearGuideR53.Hardware hardware,CarrierRearGuideR53.Hardware baseline)
    {
        for(var p:hardware.parts())if(legacy(p.name()))
        {
            var old=baseline.parts().stream().filter(q->q.name().equals(p.name())).findFirst().orElse(null);
            if(old==null||!old.frame().equals(p.frame())||!old.role().equals(p.role())
                ||!Arrays.equals(old.mesh().triangles(),p.mesh().triangles()))return false;
        }
        return hardware.mounts().equals(baseline.mounts());
    }
    private static List<NervLegacyCarrierRideR52.Piece> at(CarrierRearGuideR53.Hardware h,boolean returning,int clock)
    {
        var state=new CompoundTag();state.putBoolean("RearToTransferR53",returning);
        var a=returning?new Vec3(0,1,0):new Vec3(0,0,1);var b=returning?new Vec3(0,0,1):new Vec3(0,1,0);
        var pose=NervBankHeadTransferR53.sample(a,b,clock);
        return h.partsAt(RigidTransform.identity(),1,pose.direction(),pose.slide(),CarrierRearGuideR53.bankLift(state,clock));
    }
    public static void main(String[] args)throws Exception
    {
        byte[] bytes=Files.readAllBytes(Path.of(args[0]));
        var metadata=JsonParser.parseString(new String(bytes,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
        if(metadata.get("transfer_stow_lift_m").getAsDouble()!=CarrierRearGuideR53.STOW_LIFT)
            throw new IllegalStateException("Audit runtime stroke differs from candidate hardware");
        String carrierSha=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(EvaOriginalMeshGeometryR52.classpathBytes(CarrierAssemblyR53.MESH)));
        if(!metadata.get("carrier_sha256").getAsString().equals(carrierSha))
            throw new IllegalStateException("Attachment audit uses a different imported carrier source");
        var h=CarrierRearGuideR53.readHardware(bytes,"uninstalled-self-audit");
        byte[] baselineBytes=Files.readAllBytes(Path.of(args[1]));
        var baseline=CarrierRearGuideR53.readHardware(baselineBytes,"unchanged-head-comparison");
        if(!unchangedLegacy(h,baseline))throw new IllegalStateException("Legacy ball, socket, capture or slider geometry changed");
        boolean bearings=NervBankHeadTransferR53.internalBearings();
        boolean liftBearings=CarrierRearGuideR53.liftBearings(h);
        var failures=new ArrayList<Object>();var contacts=new TreeMap<String,Integer>();
        var legacyOverlaps=new TreeMap<String,Integer>();var welded=new TreeSet<String>();
        if(!bearings)failures.add(Map.of("reason","source spherical/slider finite bearing proof failed"));
        if(!liftBearings)failures.add(Map.of("reason","new lift finite face proof failed"));
        var body=new LinkedHashMap<String,NervRigidMeshSweepR52>();
        CarrierAssemblyR53.selected().posed(1,0,0).forEach((name,xyz)->body.put(name,new NervRigidMeshSweepR52(xyz)));
        var attachmentFailures=new ArrayList<Object>();int attachmentTests=0;
        int intervals=0,tests=0;
        for(boolean returning:new boolean[]{false,true})for(int clock=0;clock<120;clock++)
        {
            intervals++;var A=at(h,returning,clock);var B=at(h,returning,clock+1);
            var state=new CompoundTag();state.putBoolean("RearToTransferR53",returning);
            var da=returning?new Vec3(0,1,0):new Vec3(0,0,1);var db=returning?new Vec3(0,0,1):new Vec3(0,1,0);
            var pa=NervBankHeadTransferR53.sample(da,db,clock);var pb=NervBankHeadTransferR53.sample(da,db,clock+1);
            double angle=Math.acos(Math.max(-1,Math.min(1,pa.direction().dot(pb.direction()))));
            double error=angle==0?0:(.35+Math.abs(pa.slide()))*angle*angle/8+2e-6;
            for(int i=0;i<A.size();i++)
            {
                var a=A.get(i);var b=B.get(i);if(a.role().equals("source_weld"))continue;
                if((returning||clock>0)&&a.frame().equals(RigidTransform.identity())&&b.frame().equals(a.frame()))continue;
                for(var original:body.entrySet())
                {
                    var root=RigidTransform.identity();var mesh=original.getValue();
                    if(!a.mesh().envelope(a.frame(),b.frame()).inflate(error).intersects(mesh.envelope(root,root)))continue;
                    attachmentTests++;
                    if(a.mesh().intersects(a.frame(),b.frame(),mesh,root,root,.003,new Vec3(error,error,error)))
                        attachmentFailures.add(Map.of("returning",returning,"clock",clock,"rear",a.name(),"body",original.getKey()));
                }
            }
            for(int i=0;i<A.size();i++)for(int j=i+1;j<A.size();j++)
            {
                var a=A.get(i);var b=A.get(j);var endA=B.get(i);var endB=B.get(j);
                if(!a.mesh().envelope(a.frame(),endA.frame()).inflate(error)
                    .intersects(b.mesh().envelope(b.frame(),endB.frame()).inflate(error)))continue;
                String names=pair(a.name(),b.name());
                if(weld(a,b,endA,endB)){welded.add(names);continue;}
                if(liftBearings&&sleeve(a,b)){contacts.merge("finite lift: "+names,1,Integer::sum);continue;}
                if(bearings&&spherical(a,b)){contacts.merge("source sphere: "+names,1,Integer::sum);continue;}
                tests++;
                if(!a.mesh().intersects(a.frame(),endA.frame(),b.mesh(),b.frame(),endB.frame(),.003,new Vec3(error*2,error*2,error*2)))continue;
                if(legacy(a.name())&&legacy(b.name()))
                {
                    // These are not blanket exemptions: exact source arrays,
                    // frames and original ball datums were matched above.
                    // Report every overlap for separate legacy-head review.
                    legacyOverlaps.merge(names,1,Integer::sum);continue;
                }
                failures.add(Map.of("returning",returning,"clock",clock,"pair",names,"deviation",error));
            }
        }
        var report=new LinkedHashMap<String,Object>();
        for(String side:List.of("rear_l","rear_r"))
        {
            var reached=new HashSet<String>();reached.add("rear/"+side+"/source_pad");
            boolean changed=true;while(changed){changed=false;for(String edge:welded){var ends=edge.split(" \\| ");if(reached.contains(ends[0]))changed|=reached.add(ends[1]);if(reached.contains(ends[1]))changed|=reached.add(ends[0]);}}
            for(var p:h.parts())if(mount(p.name()).equals(side)&&p.frame().equals("ROOT")&&!reached.contains(p.name()))
                failures.add(Map.of("reason","fixed part lacks a finite welded path to original facet","part",p.name()));
        }
        int routePoses=0,routeDirections=0,routeTests=0;var routeFailures=new ArrayList<Object>();
        if(args.length>3)
        {
            var routes=JsonParser.parseString(Files.readString(Path.of(args[3]))).getAsJsonObject();
            var seen=new HashSet<String>();
            for(var raw:routes.getAsJsonArray("legs"))
            {
                var leg=raw.getAsJsonObject();String id=leg.get("leg").getAsString();
                double lift=id.contains("/exit")?0:CarrierRearGuideR53.STOW_LIFT,last=-100;
                var rows=leg.getAsJsonArray("samples");
                for(int n=0;n<rows.size();n++)
                {
                    var row=rows.get(n).getAsJsonObject();double metres=row.get("metres").getAsDouble();
                    if(metres-last<2&&n!=rows.size()-1)continue;last=metres;routePoses++;
                    var v=row.getAsJsonArray("tangent");var direction=new Vec3(v.get(0).getAsDouble(),v.get(1).getAsDouble(),v.get(2).getAsDouble());
                    if(!seen.add(direction+"/"+lift))continue;routeDirections++;
                    // Self intersections are translation invariant. Preserve
                    // the actual source rotation and guide direction exactly.
                    var root=new RigidTransform(Vec3.ZERO,0,1,0,0);var p=h.partsAt(root,1,direction,0,lift);
                    for(int i=0;i<p.size();i++)for(int j=i+1;j<p.size();j++)
                    {
                        var a=p.get(i);var b=p.get(j);if(legacy(a.name())&&legacy(b.name()))continue;
                        if(!a.mesh().envelope(a.frame(),a.frame()).intersects(b.mesh().envelope(b.frame(),b.frame())))continue;
                        if(weld(a,b,a,b)||liftBearings&&sleeve(a,b))continue;
                        routeTests++;
                        if(a.mesh().intersects(a.frame(),a.frame(),b.mesh(),b.frame(),b.frame(),.003,Vec3.ZERO))
                            routeFailures.add(Map.of("leg",id,"metres",metres,"pair",pair(a.name(),b.name())));
                    }
                }
            }
        }
        report.put("world_written",false);report.put("hardware_sha256",HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)));
        report.put("unchanged_head_baseline_sha256",HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(baselineBytes)));
        report.put("full_stroke_metres",CarrierRearGuideR53.STOW_LIFT);report.put("intervals",intervals);report.put("mesh_pair_tests",tests);
        report.put("source_spherical_and_slider_bearings",bearings);report.put("lift_bearings",liftBearings);
        report.put("rigid_named_welds",welded);report.put("verified_sliding_or_spherical_contacts",contacts);
        report.put("unchanged_legacy_head_overlaps_require_separate_review",legacyOverlaps);report.put("new_part_failures",failures);
        report.put("continuous_attachment_tests",attachmentTests);report.put("continuous_attachment_failures",attachmentFailures);
        report.put("route_sample_poses",routePoses);report.put("unique_route_directions",routeDirections);report.put("route_sample_pair_tests",routeTests);
        report.put("route_sample_failures",routeFailures);report.put("route_sampling_is_continuous_proof",false);
        Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(report));
        System.out.println("intervals="+intervals+" tests="+tests+" newPartFailures="+failures.size()+" legacyContactPairs="+legacyOverlaps.size()+" routePoses="+routePoses+" routeFailures="+routeFailures.size());
    }
    private AuditRearSelfGeometryR53(){}
}

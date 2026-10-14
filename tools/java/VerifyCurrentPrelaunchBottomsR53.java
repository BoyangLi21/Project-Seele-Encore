package com.projectseele.world;

import com.google.gson.*;
import java.io.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import java.util.zip.GZIPInputStream;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;

/** Read-only actual prepared body, plug and current complete carrier on Root's prelaunch legs. */
public final class VerifyCurrentPrelaunchBottomsR53
{
    private static final Gson G=new GsonBuilder().setPrettyPrinting().create();
    private record Body(String name,String family,NervRigidMeshSweepR52 mesh){}
    private record Piece(String name,String family,NervRigidMeshSweepR52 mesh,RigidTransform frame){}
    private record Window(double from,double to,double rootError,double headError,RigidTransform a,RigidTransform b,
                          Vec3 da,Vec3 db,NervLegacyCarrierRideR52.RidePose pa,NervLegacyCarrierRideR52.RidePose pb){}
    private record Cell(int x,int y,int z,String state,List<AABB> boxes){String key(){return x+","+y+","+z;}}
    private record Timeline(List<Double> times,List<NervLegacyCarrierRideR52.RidePose> poses){}
    private static String sha(Path p)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(p)));}
    private static double[] values(AABB b){return new double[]{b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ};}
    private static double[] values(RigidTransform f){return new double[]{f.translation().x,f.translation().y,f.translation().z,f.qx(),f.qy(),f.qz(),f.qw()};}
    private static double[] values(Vec3 p){return new double[]{p.x,p.y,p.z};}
    private static Vec3 point(JsonArray a){return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
    private static AABB box(JsonArray a){return new AABB(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble(),a.get(3).getAsDouble(),a.get(4).getAsDouble(),a.get(5).getAsDouble());}
    private static RigidTransform frame(JsonArray a){return new RigidTransform(point(a),a.get(3).getAsFloat(),a.get(4).getAsFloat(),a.get(5).getAsFloat(),a.get(6).getAsFloat());}
    private static List<Body> body(Path p)throws Exception
    {
        var out=new ArrayList<Body>();
        try(var in=new DataInputStream(new GZIPInputStream(Files.newInputStream(p))))
        {int count=in.readInt();for(int i=0;i<count;i++){String name=in.readUTF(),family=in.readUTF();int n=in.readInt();double[] a=new double[n];for(int k=0;k<n;k++)a[k]=in.readDouble();if(family.equals("EVA")||family.equals("PLUG"))out.add(new Body(name,family,new NervRigidMeshSweepR52(a)));}if(in.read()!=-1)throw new AssertionError("Trailing original mesh bytes");}
        if(out.stream().noneMatch(p0->p0.family().equals("EVA"))||out.stream().noneMatch(p0->p0.family().equals("PLUG")))throw new AssertionError("Original full body and closed plug required");
        return List.copyOf(out);
    }
    private static List<Piece> pieces(int v,List<Body> bodies,FootSupportFrameR52.Binding binding,RigidTransform root,Vec3 direction,NervLegacyCarrierRideR52.RidePose ride)throws Exception
    {
        var out=new ArrayList<Piece>();var foot=RigidTransform.of(root.transformPoint(binding.contactCentre()),new Quaternionf());
        for(var p:bodies)out.add(new Piece(p.name(),p.family(),p.mesh(),foot));
        for(var p:NervOriginalCarrierR52.partsAtR53(v,root,1,new Vec3(0,1,0),ride,direction,0))out.add(new Piece("carrier/"+p.name(),p.role().name(),p.mesh(),p.frame()));
        return out;
    }
    private static NervLegacyCarrierRideR52.RidePose interpolate(Timeline ride,double t)
    {
        for(int i=0;i<ride.times().size()-1;i++)if(t<=ride.times().get(i+1))return NervLegacyCarrierRideR52.interpolate(ride.poses().get(i),ride.poses().get(i+1),(t-ride.times().get(i))/(ride.times().get(i+1)-ride.times().get(i)));
        return ride.poses().get(ride.poses().size()-1);
    }
    private static Object joints(NervLegacyCarrierRideR52.RidePose pose){return pose.joints().stream().map(j->new double[]{j.drop(),j.pitch(),j.yaw()}).toList();}
    private static NervLegacyCarrierRideR52.RidePose pose(JsonArray a){var rows=new ArrayList<NervLegacyCarrierRideR52.Joint>();for(var raw:a){var j=raw.getAsJsonArray();rows.add(new NervLegacyCarrierRideR52.Joint(j.get(0).getAsDouble(),j.get(1).getAsDouble(),j.get(2).getAsDouble()));}return new NervLegacyCarrierRideR52.RidePose(rows);}
    private static List<Window> windows(NervRouteDirectoryR52 d,NervRouteDirectoryR52.Leg leg,FootSupportFrameR52.Binding binding)throws Exception
    {
        var curve=new DirectoryTrajectoryR52(d,leg,binding,0,1);
        if(!curve.pureTranslation()||leg.centreCurve()!=null)throw new AssertionError("Only original fixed-attitude prelaunch allowed");
        System.out.println("MEASURE original shoe timeline "+leg.id());
        // The native solver admits bounded movement windows; its 257-key limit is
        // deliberately not asked to solve an entire 204m ramp in one server step.
        var rideTimes=new ArrayList<Double>();var rideRoots=new ArrayList<RigidTransform>();var ridePoses=new ArrayList<NervLegacyCarrierRideR52.RidePose>();
        int chunks=(int)Math.ceil(d.legLength(leg)/4);
        for(int i=0;i<chunks;i++)
        {
            final double left=i/(double)chunks,right=(i+1D)/chunks;
            var local=NervLegacyCarrierRideR52.readOnlySamplesR52(t->curve.sample(left+(right-left)*t).evaRoot());
            if(local==null)
            {
                for(double t:new double[]{left,(left+right)*.5,right}){var rr=curve.sample(t).evaRoot();var pp=NervLegacyCarrierRideR52.targetFromActualHeadsR52(rr);System.out.println("FAILED_SUPPORT "+leg.id()+" t="+t+" root="+G.toJson(rr)+" pose="+G.toJson(pp)+" bearings="+(pp==null?"null":G.toJson(NervLegacyCarrierRideR52.finitePadBearingsR52(rr,pp))));}
                throw new AssertionError("Actual original pad support 4m window unavailable "+leg.id()+" "+left+".."+right);
            }
            for(int k=i==0?0:1;k<local.times().size();k++){rideTimes.add(left+(right-left)*local.times().get(k));rideRoots.add(local.roots().get(k));ridePoses.add(local.poses().get(k));}
        }
        var ride=new Timeline(rideTimes,ridePoses);
        var grid=new TreeSet<Double>(ride.times());
        int n=Math.max(16,curve.divisions(80,.001));n=Math.max(n,(int)Math.ceil(d.legLength(leg)/.5));
        for(int i=0;i<=n;i++)grid.add(i/(double)n);
        var times=new ArrayList<>(grid);var out=new ArrayList<Window>();
        for(int i=0;i<times.size()-1;i++)
        {
            double a=times.get(i),b=times.get(i+1),fa=d.intervalFraction(leg,0,1,a),fb=d.intervalFraction(leg,0,1,b);
            var sub=new DirectoryTrajectoryR52(d,leg,binding,fa,fb);double error=sub.error(80,1);double head=0;
            if(leg.rampProfile()!=null)
            {
                // Along this planar ramp theta=atan(k*(1-cos(pi*d/blend))/2).
                // These bounds include both angular reparameterisation and the .35m rotating head offset.
                var r=leg.rampProfile();double k=Math.abs(d.node(leg.to()).footFrame().translation().y-d.node(leg.from()).footFrame().translation().y)/(r.slopeRun()-r.blend());
                double w=Math.PI/r.blend(),first=k*w*.5,second=k*w*w*.5+2*first*first;
                double horizontal=d.node(leg.to()).footFrame().translation().subtract(d.node(leg.from()).footFrame().translation()).horizontalDistance();
                double length=horizontal*(fb-fa);head=40*(second+first*first)*length*length/8+2e-6;
            }
            out.add(new Window(a,b,error,head,curve.sample(a).evaRoot(),curve.sample(b).evaRoot(),NervOuterCarrierGuideR52.direction(curve,a),NervOuterCarrierGuideR52.direction(curve,b),interpolate(ride,a),interpolate(ride,b)));
        }
        return out;
    }
    private static Object row(Window w)
    {
        var m=new LinkedHashMap<String,Object>();m.put("from",w.from());m.put("to",w.to());m.put("root_error_m",w.rootError());m.put("head_extra_error_m",w.headError());m.put("root_from",values(w.a()));m.put("root_to",values(w.b()));m.put("direction_from",values(w.da()));m.put("direction_to",values(w.db()));m.put("ride_from",joints(w.pa()));m.put("ride_to",joints(w.pb()));return m;
    }
    private static Window window(JsonObject j){return new Window(j.get("from").getAsDouble(),j.get("to").getAsDouble(),j.get("root_error_m").getAsDouble(),j.get("head_extra_error_m").getAsDouble(),frame(j.getAsJsonArray("root_from")),frame(j.getAsJsonArray("root_to")),point(j.getAsJsonArray("direction_from")),point(j.getAsJsonArray("direction_to")),pose(j.getAsJsonArray("ride_from")),pose(j.getAsJsonArray("ride_to")));}
    private static final class Hit
    {
        final Cell cell;final Piece piece;int intervals;double lo=1,hi=0,error;
        Hit(Cell c,Piece p){cell=c;piece=p;}
        void add(Window w,double e){intervals++;lo=Math.min(lo,w.from());hi=Math.max(hi,w.to());error=Math.max(error,e);}
        Object row(){return Map.of("position",new int[]{cell.x(),cell.y(),cell.z()},"state",cell.state(),"native_boxes",cell.boxes().stream().map(VerifyCurrentPrelaunchBottomsR53::values).toList(),"part",piece.name(),"family",piece.family(),"interval_count",intervals,"first_path_fraction",lo,"last_path_fraction",hi,"maximum_extra_error_m",error);}
    }
    private static long test(Piece a,Piece b,Window w,Map<String,Cell> cells,double[] offsets,Map<String,Hit> hits)
    {
        double error=w.rootError()+(a.name().startsWith("carrier/outer/")?w.headError():0)+(a.name().startsWith("carrier/ride/")?.0002:0);
        var bounds=a.mesh().envelope(a.frame(),b.frame()).inflate(error);long count=0;
        int x0=(int)Math.floor(bounds.minX-offsets[3]),x1=(int)Math.floor(bounds.maxX-offsets[0]);int y0=(int)Math.floor(bounds.minY-offsets[4]),y1=(int)Math.floor(bounds.maxY-offsets[1]);int z0=(int)Math.floor(bounds.minZ-offsets[5]),z1=(int)Math.floor(bounds.maxZ-offsets[2]);
        for(int y=y0;y<=y1;y++)for(int z=z0;z<=z1;z++)for(int x=x0;x<=x1;x++)
        {
            var c=cells.get(x+","+y+","+z);if(c==null)continue;
            for(var obstacle:c.boxes()){if(!bounds.intersects(obstacle))continue;count++;if(a.mesh().intersects(a.frame(),b.frame(),obstacle.inflate(error),.003)){hits.computeIfAbsent(c.key()+"/"+a.name(),q->new Hit(c,a)).add(w,error);break;}}
        }
        return count;
    }
    private record Check(Window window,boolean ridesOnly,boolean rigidOnly,String certificate){}
    private static List<Check> fixedChecks(NervRouteDirectoryR52 d,NervRouteDirectoryR52.Leg leg,FootSupportFrameR52.Binding binding,List<Window> original)throws Exception
    {
        var checks=new ArrayList<Check>();for(var w:original)checks.add(new Check(w,true,false,"unchanged_actual_adaptive_shoe_window"));
        double horizontal=d.node(leg.to()).footFrame().translation().subtract(d.node(leg.from()).footFrame().translation()).horizontalDistance();
        var bands=new ArrayList<double[]>();var profile=leg.rampProfile();
        if(profile==null)bands.add(new double[]{0,horizontal});
        else
        {
            double f=profile.flatBefore(),b=profile.blend(),run=profile.slopeRun();bands.add(new double[]{0,f});bands.add(new double[]{f+b,f+run-b});bands.add(new double[]{f+run,horizontal});
            var start=d.node(leg.from()).footFrame().translation();
            for(var w:original){double a=w.a().translation().subtract(original.get(0).a().translation()).horizontalDistance(),z=w.b().translation().subtract(original.get(0).a().translation()).horizontalDistance();if(z>f&&a<f+b||z>f+run-b&&a<f+run)checks.add(new Check(w,false,true,"unchanged_real_rounding_curve_certificate"));}
        }
        for(var band:bands)
        {
            if(band[1]<=band[0])continue;int n=(int)Math.ceil((band[1]-band[0])/8);
            for(int i=0;i<n;i++)
            {
                double fa=(band[0]+(band[1]-band[0])*i/n)/horizontal,fb=(band[0]+(band[1]-band[0])*(i+1D)/n)/horizontal;
                var a=d.sample(leg,fa,binding).evaRoot();var z=d.sample(leg,fb,binding).evaRoot();var da=d.tangent(leg,fa);var db=d.tangent(leg,fb);
                if(a.rotationErrorDegrees(z)>1e-6||a.transformVector(new Vec3(0,1,0)).distanceTo(new Vec3(0,1,0))>1e-8||da.distanceTo(db)>1e-10)throw new AssertionError("Analytical linear-band fixed root and tangent contract changed");
                double start=d.legDistance(leg,fa)/d.legLength(leg),end=d.legDistance(leg,fb)/d.legLength(leg);checks.add(new Check(new Window(start,end,2e-7,0,a,z,da,db,NervLegacyCarrierRideR52.rest(),NervLegacyCarrierRideR52.rest()),false,true,"exact_source_affine_band_max8m_constant_local_members"));
            }
        }
        return checks;
    }
    private static void fixed(Path design,Path cloud,Path out)throws Exception
    {
        var prepared=JsonParser.parseString(Files.readString(out.resolve("CURRENT_PRELAUNCH_WINDOWS.json"))).getAsJsonObject();
        for(var e:prepared.getAsJsonObject("source_files_sha256").entrySet())if(!sha(Path.of(e.getKey())).equals(e.getValue().getAsString()))throw new AssertionError("Prepared source changed before steel proof");
        var declaration=JsonParser.parseString(Files.readString(design)).getAsJsonObject();declaration.addProperty("status","installed");declaration.addProperty("installation_receipt_sha256","0".repeat(64));var directory=NervRouteDirectoryR52.parse(declaration);
        var steel=NervLegacyCarrierRideR52.fixedPartsR52();var index=new NervStaticSpatialIndexR52<>(steel,p->p.mesh().envelope(p.frame(),p.frame()));var results=new ArrayList<Object>();
        List<Body> bodies=List.of();int active=-1;
        for(var item:prepared.getAsJsonArray("legs"))
        {
            var leg=item.getAsJsonObject();int v=leg.get("variant").getAsInt();String id=leg.get("leg").getAsString();if(active!=v){active=v;bodies=body(Path.of(cloud+".variant"+v+".actual_mesh.bin.gz"));}
            var binding=NervOriginalCarrierR52.nominalBinding(v);var hits=new LinkedHashMap<String,JsonObject>();var contacts=new LinkedHashMap<String,JsonObject>();long tests=0;int count=0;
            var original=new ArrayList<Window>();for(var raw:leg.getAsJsonArray("windows"))original.add(window(raw.getAsJsonObject()));var checked=fixedChecks(directory,directory.leg(id),binding,original);
            for(var check:checked)
            {
                var w=check.window();var A=pieces(v,bodies,binding,w.a(),w.da(),w.pa());var B=pieces(v,bodies,binding,w.b(),w.db(),w.pb());
                for(int i=0;i<A.size();i++)
                {
                    var a=A.get(i);var b=B.get(i);boolean ride=a.name().startsWith("carrier/ride/");if(check.ridesOnly()!=ride)continue;
                    if(check.certificate().startsWith("exact_source")){var la=w.a().inverse().compose(a.frame());var lb=w.b().inverse().compose(b.frame());if(la.translation().distanceTo(lb.translation())>1e-8||la.rotationErrorDegrees(lb)>1e-5)throw new AssertionError("A supposedly rigid local member moved inside a linear source band: "+a.name());}
                    double error=w.rootError()+(a.name().startsWith("carrier/outer/")?w.headError():0)+(ride?.0002:0);var bounds=a.mesh().envelope(a.frame(),b.frame()).inflate(error);
                    for(var f:index.query(bounds))
                    {
                        String contact=null;NervOriginalCarrierR52.Part p=null,q=null;
                        if(a.name().startsWith("carrier/"))
                        {
                            p=new NervOriginalCarrierR52.Part(a.name().substring(8),NervOriginalCarrierR52.Role.valueOf(a.family()),a.mesh(),a.frame());q=new NervOriginalCarrierR52.Part(b.name().substring(8),NervOriginalCarrierR52.Role.valueOf(b.family()),b.mesh(),b.frame());
                            if(NervLegacyCarrierRideR52.namedHeadContactR52(p,q,f))contact="actual_four_sliding_pad_exterior_and_finite_bearing";
                            else if(NervLegacyCarrierRideR52.namedDeckHeadContactR52(p,q,f))contact="actual_deck_finite_coplanar_upper_head_faces";
                            else if(NervLegacyCarrierRideR52.namedSoleHeadContactR52(p,q,f))contact="actual_sole_finite_coplanar_upper_head_faces";
                        }
                        String key=a.name()+" vs "+f.name();
                        if(contact!=null)
                        {
                            var row=contacts.get(key);if(row==null){row=new JsonObject();row.addProperty("moving_part",a.name());row.addProperty("fixed_part",f.name());row.addProperty("fixed_role",f.role());row.addProperty("exact_production_contact_predicate",contact);row.addProperty("first_fraction",w.from());row.addProperty("last_fraction",w.to());row.addProperty("interval_count",0);if(contact.startsWith("actual_four"))row.add("finite_nine_point_pad_bearings_at_first_endpoints",G.toJsonTree(List.of(NervLegacyCarrierRideR52.finitePadBearingsR52(w.a(),w.pa()),NervLegacyCarrierRideR52.finitePadBearingsR52(w.b(),w.pb()))));if(contact.startsWith("actual_sole"))row.add("first_endpoint_facet_area_proofs",G.toJsonTree(NervLegacyCarrierRideR52.finiteSoleHeadFacesR52(p,q,f)));contacts.put(key,row);}row.addProperty("last_fraction",w.to());row.addProperty("interval_count",row.get("interval_count").getAsInt()+1);continue;
                        }
                        if(hits.containsKey(key))continue;
                        tests++;if(!a.mesh().intersects(a.frame(),b.frame(),f.mesh(),f.frame(),f.frame(),.003,new Vec3(error,error,error)))continue;
                        var row=hits.get(key);if(row==null){row=new JsonObject();row.addProperty("moving_part",a.name());row.addProperty("moving_family",a.family());row.addProperty("fixed_part",f.name());row.addProperty("fixed_role",f.role());row.addProperty("first_fraction",w.from());row.addProperty("last_fraction",w.to());row.addProperty("witness_semantics","First actually tested intersecting continuous interval only; repeated known pair is not rescanned or asserted clear elsewhere");row.addProperty("curve_certificate",check.certificate());row.addProperty("interval_count",0);row.addProperty("maximum_extra_error_m",0);row.add("first_moving_from",G.toJsonTree(values(a.frame())));row.add("first_moving_to",G.toJsonTree(values(b.frame())));row.add("fixed_frame",G.toJsonTree(values(f.frame())));row.add("fixed_actual_bounds",G.toJsonTree(values(f.mesh().envelope(f.frame(),f.frame()))));hits.put(key,row);}row.addProperty("last_fraction",w.to());row.addProperty("interval_count",row.get("interval_count").getAsInt()+1);row.addProperty("maximum_extra_error_m",Math.max(row.get("maximum_extra_error_m").getAsDouble(),error));
                    }
                }
                if(++count%200==0)System.out.println("STEEL "+id+" windows="+count+" tests="+tests+" hits="+hits.size()+" contacts="+contacts.size());
            }
            results.add(Map.of("leg",id,"variant",v,"actual_fixed_members",steel.size(),"continuous_narrow_phase_tests",tests,"unresolved_mesh_pairs",hits.values(),"actual_finite_bearing_contact_pairs",contacts.values(),"actual_checked_windows",checked.size(),"batching_rule","Only analytical source flat/constant-grade bands are batched at <=8m, exact boundary cuts, constant tangent and per-member local frame verified. Curved head/body intervals and every dynamic shoe window retain their original certificates."));
            Files.writeString(out.resolve("ACTUAL_PRELAUNCH_FIXED_STEEL_PARTIAL.json"),G.toJson(results));System.out.println("STEEL DONE "+id+" hits="+hits.size()+" contacts="+contacts.size());
        }
        Files.writeString(out.resolve("ACTUAL_PRELAUNCH_FIXED_STEEL.json"),G.toJson(Map.of("world_written",false,"game_started",false,"windows_sha256",sha(out.resolve("CURRENT_PRELAUNCH_WINDOWS.json")),"original_source",NervLegacyCarrierRideR52.SOURCE_SHA,"deep_frame_source",NervLegacyDeepFrameR53.SOURCE_SHA,"legs",results,"scope","All current actual fixed source members including the Root service bypass and compact level overlays. Full body/plug/current carrier continuous mesh pairing; only existing actual finite pad/deck/sole exterior-facet predicates identify bearing contacts. Other pairs remain unresolved collisions; no new exemptions or World changes.")));
    }
    public static void main(String[] args)throws Exception
    {
        Path design=Path.of(args[0]),cloud=Path.of(args[1]),windowsFile=Path.of(args[2]),candidateFile=Path.of(args[3]),output=Path.of(args[4]);
        var json=JsonParser.parseString(Files.readString(design)).getAsJsonObject();json.addProperty("status","installed");json.addProperty("installation_receipt_sha256","0".repeat(64));var d=NervRouteDirectoryR52.parse(json);
        if(!sha(design).equals("68ccfa1d5b762755adfaef13b34878103f411ea277797545dc63a2c5bb0f45a1"))throw new AssertionError("Actual final directory required");
        var input=JsonParser.parseString(Files.readString(candidateFile)).getAsJsonObject();if(!input.getAsJsonArray("unknown_shapes").isEmpty())throw new AssertionError("Unknown native shapes");
        var cells=new HashMap<String,Cell>();for(var raw:input.getAsJsonArray("cells")){var c=raw.getAsJsonObject();var p=c.getAsJsonArray("position");var boxes=new ArrayList<AABB>();for(var b:c.getAsJsonArray("native_boxes"))boxes.add(box(b.getAsJsonArray()));var cell=new Cell(p.get(0).getAsInt(),p.get(1).getAsInt(),p.get(2).getAsInt(),c.get("state").getAsString(),boxes);cells.put(cell.key(),cell);}
        var prepared=JsonParser.parseString(Files.readString(windowsFile)).getAsJsonObject();var results=new ArrayList<Object>();var hashes=new LinkedHashMap<String,String>();hashes.put(design.toString(),sha(design));hashes.put(windowsFile.toString(),sha(windowsFile));hashes.put(candidateFile.toString(),sha(candidateFile));
        int active=-1;List<Body>bodies=List.of();
        for(var raw:prepared.getAsJsonArray("legs"))
        {
            var item=raw.getAsJsonObject();int v=item.get("variant").getAsInt();String id=item.get("leg").getAsString();if(active!=v){active=v;Path source=cloud.resolve("ACTUAL_FIXED_ASSEMBLY.variant"+v+".bin.gz");hashes.put(source.toString(),sha(source));bodies=body(source);}
            var binding=NervOriginalCarrierR52.nominalBinding(v);var ws=new ArrayList<Window>();for(var w:item.getAsJsonArray("windows"))ws.add(window(w.getAsJsonObject()));var checks=fixedChecks(d,d.leg(id),binding,ws);var hits=new LinkedHashMap<String,Hit>();long tests=0;int count=0;
            for(var check:checks)
            {
                var w=check.window();var aa=pieces(v,bodies,binding,w.a(),w.da(),w.pa());var bb=pieces(v,bodies,binding,w.b(),w.db(),w.pb());
                for(int i=0;i<aa.size();i++)
                {
                    var a=aa.get(i);var b=bb.get(i);boolean ride=a.name().startsWith("carrier/ride/");if(check.ridesOnly()!=ride)continue;
                    if(check.certificate().startsWith("exact_source")){var la=w.a().inverse().compose(a.frame());var lb=w.b().inverse().compose(b.frame());if(la.translation().distanceTo(lb.translation())>1e-8||la.rotationErrorDegrees(lb)>1e-5)throw new AssertionError("Nonrigid affine member "+a.name());}
                    tests+=test(a,b,w,cells,new double[]{0,0,0,1,1,1},hits);
                }
                if(++count%400==0)System.out.println(id+" checked="+count+" tests="+tests+" hits="+hits.size());
            }
            results.add(Map.of("leg",id,"variant",v,"checks",checks.size(),"narrow_phase_tests",tests,"part_cell_hits",hits.values().stream().map(Hit::row).toList()));System.out.println("DONE "+id+" tests="+tests+" hits="+hits.size());Files.writeString(output.resolveSibling("BOTTOM_CURRENT_BODY_PARTIAL.json"),G.toJson(results));
        }
        Files.writeString(output,G.toJson(Map.of("world_written",false,"game_started",false,"source_sha256",hashes,"legs",results,"scope","Only proposed 3240 exact new floor cubes versus all current carrier/head/actual seated plug and EVA. Original adaptive shoes and curve windows; exact affine bands use source-constant local transforms/root yaw/tangent. True seated body binding from v2. No World modification or native admission.")));
    }
}

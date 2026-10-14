package com.projectseele.world;
import com.google.gson.*;import com.projectseele.entity.SiloHatchMechanism;
import java.nio.file.*;import java.util.*;import java.security.*;import net.minecraft.world.phys.*;

/** Read-only complete48 production heads through the actual9 open upper gates. */
public final class VerifyCurrentUpperGateHeadsR53
{
    private static final Gson G=new GsonBuilder().setPrettyPrinting().create();
    private record Obstacle(String name,NervRigidMeshSweepR52 mesh,RigidTransform frame){}
    private record Bounds(double acceleration,double tx2,double xx2,double yy2,double projectionLower,double maxError){}
    private static List<NervOuterCarrierGuideR52.Template> templates;
    private static Map<String,NervOuterCarrierGuideR52.Template> named;
    private static final List<Object> hits=new ArrayList<>(),routes=new ArrayList<>();
    private static long windows,pairs,broad,pruned;private static double maximumPad,lowestOffset,highestOffset;
    private static RigidTransform gateFrame(JsonObject gate){var f=gate.getAsJsonObject("frame");var p=f.getAsJsonArray("position");var q=f.getAsJsonArray("quaternion");return new RigidTransform(new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble()),q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat());}
    private static Vec3[] derivative(Vec3[] c){if(c.length<2)return new Vec3[]{Vec3.ZERO};var d=new Vec3[c.length-1];for(int i=0;i<d.length;i++)d[i]=c[i+1].subtract(c[i]).scale(c.length-1);return d;}
    private static Vec3 eval(Vec3[] c,double t){var a=c.clone();for(int n=a.length-1;n>0;n--)for(int j=0;j<n;j++)a[j]=a[j].lerp(a[j+1],t);return a[0];}
    private static Vec3 unit(Vec3 v){return v.scale(1/v.length());}
    private static Vec3[][] split(Vec3[] c){var a=c.clone();var left=new Vec3[c.length];var right=new Vec3[c.length];left[0]=a[0];right[c.length-1]=a[c.length-1];for(int n=1;n<c.length;n++){for(int j=0;j<c.length-n;j++)a[j]=a[j].lerp(a[j+1],.5);left[n]=a[0];right[c.length-1-n]=a[c.length-1-n];}return new Vec3[][]{left,right};}
    private static Bounds bound(Vec3[] c)
    {
        var v=derivative(c);var a=derivative(v);var j=derivative(a);var axis=unit(c[c.length-1].subtract(c[0]));double min=Arrays.stream(v).mapToDouble(p->p.dot(axis)).min().orElseThrow()-1e-10;
        if(min<=0)return null;double A=Arrays.stream(a).mapToDouble(Vec3::length).max().orElse(0),J=Arrays.stream(j).mapToDouble(Vec3::length).max().orElse(0);if(A==0&&J==0)return new Bounds(0,0,0,0,1,0);
        double k1=A/min,k2=J/min+3*k1*k1,maxDot=Math.abs(unit(eval(v,.5)).x)+k1*.5;if(maxDot>=.9949)return null;double s=Math.sqrt(1-maxDot*maxDot);
        double x2=(2*k2+2*k1*k1)/s+12*k1*k1/(s*s),y2=k2+4*k1*k1/s+x2,maximum=0;var result=new Bounds(A,k2,x2,y2,s,0);for(var t:templates)maximum=Math.max(maximum,pad(t,result));return new Bounds(A,k2,x2,y2,s,maximum);
    }
    private static double pad(NervOuterCarrierGuideR52.Template t,Bounds b)
    {
        if(b.acceleration()==0&&b.tx2()==0)return 0;
        if(t.frame().equals("ROOT"))return b.acceleration()/8+2e-7;
        var vertices=t.mesh().triangles();double max=0,radius=0;for(int i=0;i<vertices.length;i+=3){max=Math.max(max,Math.abs(vertices[i])*b.xx2()+Math.abs(vertices[i+1]-.35)*b.yy2()+Math.abs(vertices[i+2])*b.tx2());radius=Math.max(radius,new Vec3(vertices[i],vertices[i+1],vertices[i+2]).length());}
        // Normalized float matrix/quaternion chains are bounded separately;
        // the head's actual analytic vertex chord error is M2/8 on this window.
        double floatPad=128*Math.scalb(1D,-23)*(radius+.35)*(1+1/b.projectionLower());return(b.acceleration()+max)/8+floatPad+2e-7;
    }
    private static void window(String route,int segment,Vec3[] c,double u0,double u1,int depth,RigidTransform pose,Vec3 offset,List<Obstacle> obstacles,AABB gateBounds)throws Exception
    {
        double low=Arrays.stream(c).mapToDouble(p->p.y).min().orElseThrow()+offset.y+lowestOffset,high=Arrays.stream(c).mapToDouble(p->p.y).max().orElseThrow()+offset.y+highestOffset;
        if(low>gateBounds.maxY+.001||high<gateBounds.minY-.001){pruned++;return;}
        var certificate=bound(c);if(certificate==null||certificate.maxError()>.0005){if(depth>=22)throw new AssertionError("Current head derivative/source error could not be bounded");var h=split(c);double mid=(u0+u1)/2;window(route,segment,h[0],u0,mid,depth+1,pose,offset,obstacles,gateBounds);window(route,segment,h[1],mid,u1,depth+1,pose,offset,obstacles,gateBounds);return;}
        var derivative=derivative(c);var ra=RigidTransform.of(c[0].add(offset),pose.rotation());var rb=RigidTransform.of(c[c.length-1].add(offset),pose.rotation());var A=NervOuterCarrierGuideR52.partsAt(ra,1,unit(derivative[0]),0);var B=NervOuterCarrierGuideR52.partsAt(rb,1,unit(derivative[derivative.length-1]),0);if(A.size()!=48||B.size()!=48)throw new AssertionError("All48 current head parts required");windows++;maximumPad=Math.max(maximumPad,certificate.maxError());
        for(int i=0;i<A.size();i++){var p=A.get(i);var q=B.get(i);if(!p.name().equals(q.name()))throw new AssertionError("Head part identity changed");double extra=pad(named.get(p.name()),certificate);var envelope=p.mesh().envelope(p.frame(),q.frame()).inflate(extra);for(var obstacle:obstacles){pairs++;if(!envelope.intersects(obstacle.mesh().envelope(obstacle.frame(),obstacle.frame())))continue;broad++;if(p.mesh().intersects(p.frame(),q.frame(),obstacle.mesh(),obstacle.frame(),obstacle.frame(),.003,new Vec3(extra,extra,extra)))hits.add(Map.of("leg",route,"segment",segment,"control_parameter",new double[]{u0,u1},"head_part",p.name(),"gate_part",obstacle.name(),"actual_vertex_chord_error_m",extra,"root_from",new double[]{ra.translation().x,ra.translation().y,ra.translation().z},"root_to",new double[]{rb.translation().x,rb.translation().y,rb.translation().z}));}}
    }
    private static String sha(Path p)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(p)));}
    public static void main(String[] args)throws Exception
    {
        var directoryPath=Path.of(args[0]);var candidatePath=Path.of(args[1]);var out=Path.of(args[2]);var doc=JsonParser.parseString(Files.readString(directoryPath)).getAsJsonObject();var directory=NervRouteDirectoryR52.parse(doc);directory.validateCompactLaunchContractR52();var source=JsonParser.parseString(Files.readString(candidatePath)).getAsJsonObject();if(!sha(directoryPath).equals(source.get("directory_sha256").getAsString()))throw new AssertionError("Gate candidate/current directory changed");var gates=new HashMap<String,JsonObject>();for(var g:source.getAsJsonArray("gates"))gates.put(g.getAsJsonObject().get("resource").getAsString(),g.getAsJsonObject());
        templates=NervOuterCarrierGuideR52.templates();if(templates.size()!=48)throw new AssertionError("Actual current48 captured parts required");named=new HashMap<>();lowestOffset=Double.POSITIVE_INFINITY;highestOffset=Double.NEGATIVE_INFINITY;
        for(var t:templates){named.put(t.name(),t);var v=t.mesh().triangles();for(int i=0;i<v.length;i+=3){if(t.frame().equals("ROOT")){lowestOffset=Math.min(lowestOffset,v[i+1]);highestOffset=Math.max(highestOffset,v[i+1]);}else{double r=new Vec3(v[i],v[i+1],v[i+2]).length()+.35;lowestOffset=Math.min(lowestOffset,-3.42-r);highestOffset=Math.max(highestOffset,-3.42+r);}}}
        for(var rawLeg:doc.getAsJsonArray("legs"))
        {
            var leg=directory.leg(rawLeg.getAsJsonObject().get("id").getAsString());
            var from=directory.node(leg.from());if(leg.centreCurve()==null||from.role()!=NervRouteDirectoryR52.Role.BANK)continue;String gateName="bank_"+from.bank()+"_upper_lane_"+from.lane();var gate=gates.get(gateName);if(gate==null)throw new AssertionError("Explicit actual upper gate missing");var h=gate.getAsJsonObject("silo_hatch");if(h.get("opening_x").getAsInt()!=31||h.get("opening_z").getAsInt()!=31||!h.get("upright_guide_ports").getAsBoolean())throw new AssertionError("Actual31 upright source required");var geo=NervSiloHatchGeometryR52.loadClasspath(new SiloHatchMechanism.Spec(31,31,h.get("open_ticks").getAsInt(),h.get("close_ticks").getAsInt(),1,h.get("beam_bottom").getAsDouble(),false,true));var gf=gateFrame(gate);var obstacles=new ArrayList<Obstacle>();AABB all=null;for(var p:geo.pieces(1)){var m=new NervRigidMeshSweepR52(p.part().xyz());var f=gf.compose(p.local());obstacles.add(new Obstacle(p.part().name(),m,f));var b=m.envelope(f,f);all=all==null?b:all.minmax(b);}
            int variant=2-from.lane();var pose=directory.sample(leg,0,NervOriginalCarrierR52.nominalBinding(variant)).evaRoot();if(pose.rotationErrorDegrees(new RigidTransform(Vec3.ZERO,0,1,0,0))>1e-6)throw new AssertionError("Actual body yaw180 must remain fixed");var curve=leg.centreCurve();var offset=pose.translation().subtract(curve.segments().get(0).controls().get(0));long before=windows,tested=pairs;int hitBefore=hits.size();int index=0;for(var segment:curve.segments())window(leg.id(),index++,segment.controls().toArray(Vec3[]::new),0,1,0,pose,offset,obstacles,all);routes.add(Map.of("leg",leg.id(),"gate",gateName,"variant",variant,"parts",48,"all_open_gate_parts",obstacles.size(),"certified_windows",windows-before,"pair_windows",pairs-tested,"hits",hits.size()-hitBefore));System.out.println("upper="+gateName+" windows="+(windows-before)+" hits="+(hits.size()-hitBefore));
        }
        if(routes.size()!=9)throw new AssertionError("Actual9 upper gates required");var result=new LinkedHashMap<String,Object>();result.put("schema","projectseele.r53.current48-head-nine-upper-gate-crossing.v1");result.put("directory_sha256",sha(directoryPath));result.put("gate_candidate_sha256",sha(candidatePath));result.put("head_transfer_source_sha256",NervBankHeadTransferR53.SOURCE_SHA);result.put("outer_capture_source_sha256",NervOuterCarrierGuideR52.SOURCE_SHA);result.put("routes",routes);result.put("hits",hits);result.put("passed",hits.isEmpty());result.put("certified_windows",windows);result.put("pair_windows",pairs);result.put("broadphase_pairs",broad);result.put("height_hull_pruned_windows",pruned);result.put("maximum_actual_vertex_chord_error_m",maximumPad);result.put("conservative_all_orientation_head_y_offsets",new double[]{lowestOffset,highestOffset});result.put("certificate","Each exact Bezier subcurve: derivative control hull bounds speed m>0, acceleration A, jerk J; T'=A/m, T''<=J/m+3(A/m)^2; projected-X normalized frame derivatives bounded using explicit projection lower norm. Actual head vertex second derivative gives chord error M2/8 plus separate float frame allowance. Full production triangles + SLERP kernel tested with this extra allowance. Root/EVA yaw remains180; all p1 gate pieces remain present.");result.put("world_written",false);result.put("game_started",false);result.put("whole_assembly_or_native_acceptance",false);Files.writeString(out,G.toJson(result));System.out.println("HEAD48_UPPER9 passed="+hits.isEmpty()+" windows="+windows+" pairs="+pairs+" hits="+hits.size());
    }
}

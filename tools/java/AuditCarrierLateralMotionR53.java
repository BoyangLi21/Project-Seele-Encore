package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.phys.*;

/** Complete source geometry: distinct source revision, bank motion and transverse motion evidence. */
public final class AuditCarrierLateralMotionR53
{
    private static String tail(String n){return n.substring(n.indexOf('/',5)+1);}
    private static String side(String n){return n.split("/")[1];}
    private static String pair(String a,String b){return a.compareTo(b)<0?a+" | "+b:b+" | "+a;}
    private static boolean sourceHead(String name)
    {String s=tail(name);return !s.equals("source_pad")&&!s.startsWith("mount/")&&!s.startsWith("lift_")&&!s.startsWith("lateral/");}
    private static boolean hit(NervLegacyCarrierRideR52.Piece a,NervLegacyCarrierRideR52.Piece b)
    {return a.mesh().intersects(a.frame(),a.frame(),b.mesh(),b.frame(),b.frame(),.003,Vec3.ZERO);}
    private static final Set<String> WELDS=new HashSet<>();
    static
    {
        for(String[] p:new String[][]{{"source_pad","mount/0"},{"mount/0","mount/1"},{"mount/1","mount/2"},
                {"mount/2","lift_bracket/vertical"},{"lift_bracket/vertical","lift_bracket/weld"},{"mount/4","lift_rod"},
                {"mount/4","lateral/support/0"},{"lateral/support/0","lateral/support/1"},{"lateral/support/1","lateral/support/2"},{"ball","lateral/rod"}})WELDS.add(pair(p[0],p[1]));
        for(String prefix:List.of("lift_","lateral/"))
        {
            for(int i=0;i<4;i++)WELDS.add(pair(prefix+"sleeve/"+i,prefix+"tie/"+i));
            for(int i=0;i<2;i++)for(int j=2;j<4;j++)WELDS.add(pair(prefix+"tie/"+i,prefix+"tie/"+j));
        }
    }
    private static boolean welded(NervLegacyCarrierRideR52.Piece a,NervLegacyCarrierRideR52.Piece b,NervLegacyCarrierRideR52.Piece A,NervLegacyCarrierRideR52.Piece B)
    {
        if(!side(a.name()).equals(side(b.name()))||!a.frame().equals(b.frame())||!A.frame().equals(B.frame()))return false;
        String p=pair(tail(a.name()),tail(b.name()));boolean named=WELDS.contains(p)||p.equals(pair("lift_bracket/weld",side(a.name()).equals("rear_l")?"lift_sleeve/0":"lift_sleeve/1"));
        return named&&hit(a,b)&&hit(A,B);
    }
    private static boolean fullBox(NervRigidMeshSweepR52 mesh)
    {
        if(mesh.triangleCount()!=12)return false;var b=mesh.bounds();double[] lo={b.minX,b.minY,b.minZ},hi={b.maxX,b.maxY,b.maxZ};var t=mesh.triangles();
        for(int i=0;i<t.length;i++)if(Math.min(Math.abs(t[i]-lo[i%3]),Math.abs(t[i]-hi[i%3]))>1e-8)return false;
        for(int axis=0;axis<3;axis++)for(double plane:new double[]{lo[axis],hi[axis]})
        {
            double area=0;int count=0;for(int i=0;i<t.length;i+=9)if(Math.abs(t[i+axis]-plane)<1e-8&&Math.abs(t[i+3+axis]-plane)<1e-8&&Math.abs(t[i+6+axis]-plane)<1e-8)
            {var a=new Vec3(t[i],t[i+1],t[i+2]);var c=new Vec3(t[i+3],t[i+4],t[i+5]);var d=new Vec3(t[i+6],t[i+7],t[i+8]);area+=c.subtract(a).cross(d.subtract(a)).length()/2;count++;}
            if(count!=2||Math.abs(area-(hi[(axis+1)%3]-lo[(axis+1)%3])*(hi[(axis+2)%3]-lo[(axis+2)%3]))>1e-8)return false;
        }
        return true;
    }
    private static double finiteFace(NervLegacyCarrierRideR52.Piece a,NervLegacyCarrierRideR52.Piece b,int axis)
    {
        if(!fullBox(a.mesh())||!fullBox(b.mesh())||a.frame().rotationErrorDegrees(RigidTransform.identity())>.0001||b.frame().rotationErrorDegrees(RigidTransform.identity())>.0001)return 0;
        var A=a.mesh().envelope(a.frame(),a.frame());var B=b.mesh().envelope(b.frame(),b.frame());double[] lo={A.minX,A.minY,A.minZ},hi={A.maxX,A.maxY,A.maxZ},l={B.minX,B.minY,B.minZ},h={B.maxX,B.maxY,B.maxZ};
        if(Math.min(Math.abs(hi[axis]-l[axis]),Math.abs(h[axis]-lo[axis]))>1e-7)return 0;double area=1;
        for(int k=0;k<3;k++)if(k!=axis)area*=Math.max(0,Math.min(hi[k],h[k])-Math.max(lo[k],l[k]));return area;
    }
    private static int bearingAxis(NervLegacyCarrierRideR52.Piece a,NervLegacyCarrierRideR52.Piece b)
    {
        if(!side(a.name()).equals(side(b.name())))return -1;String x=tail(a.name()),y=tail(b.name());if(x.endsWith("rod")){String t=x;x=y;y=t;}
        if(y.equals("lift_rod")&&x.startsWith("lift_sleeve/"))return Integer.parseInt(x.substring(x.lastIndexOf('/')+1))<2?0:2;
        if(y.equals("lateral/rod")&&(x.startsWith("lateral/sleeve/")||x.startsWith("lateral/tie/")))return Integer.parseInt(x.substring(x.lastIndexOf('/')+1))<2?1:2;
        if(pair(x,y).equals(pair("lateral/support/2","lateral/sleeve/0")))return 1;
        return -1;
    }
    private record Pose(Vec3 direction,double slide,double lift,CarrierMountProfileR53.State mounting){}
    private static Pose pose(boolean bank,boolean returning,int clock,boolean raised)
    {
        if(!bank)return new Pose(new Vec3(0,0,1),0,7,new CarrierMountProfileR53.State(raised,raised?4.25:0,returning?1-clock/120D:clock/120D));
        var state=new CompoundTag();state.putBoolean("RearToTransferR53",returning);var from=returning?new Vec3(0,1,0):new Vec3(0,0,1);var to=returning?new Vec3(0,0,1):new Vec3(0,1,0);var p=NervBankHeadTransferR53.sample(from,to,clock);
        return new Pose(p.direction(),p.slide(),CarrierRearGuideR53.bankLift(state,clock),new CarrierMountProfileR53.State(raised,raised?4.25:0,0));
    }
    public static void main(String[] args)throws Exception
    {
        byte[] bytes=Files.readAllBytes(Path.of(args[0])),oldBytes=Files.readAllBytes(Path.of(args[1]));var h=CarrierRearGuideR53.readHardware(bytes,"uninstalled-lateral-motion");var old=CarrierRearGuideR53.readHardware(oldBytes,"retained-installed-hardware");boolean raised=args.length>3&&args[3].equals("above");var id=RigidTransform.identity();
        var unchanged=new ArrayList<Object>();var changed=new ArrayList<String>();var added=new ArrayList<Object>();var removed=new ArrayList<String>();
        var before=old.partsAt(id,1,new Vec3(0,0,1),0,7);var after=h.partsAt(id,1,new Vec3(0,0,1),0,7,CarrierMountProfileR53.LEGACY);
        for(var a:before){var b=after.stream().filter(p->p.name().equals(a.name())).findFirst().orElse(null);if(b==null){removed.add(a.name());continue;}boolean same=Arrays.equals(a.mesh().triangles(),b.mesh().triangles())&&a.frame().equals(b.frame());if(same)unchanged.add(Map.of("name",a.name(),"triangles",a.mesh().triangleCount()));else changed.add(a.name());if(sourceHead(a.name())&&!same)throw new IllegalStateException("Original complete head/ball source changed: "+a.name());}
        for(var b:after)if(before.stream().noneMatch(a->a.name().equals(b.name())))added.add(Map.of("name",b.name(),"role",b.role(),"triangles",b.mesh().triangleCount(),"frame",b.frame()));
        if(!old.mounts().equals(h.mounts())||!changed.isEmpty())throw new IllegalStateException("Existing retained geometry/frame changed");
        var source=Objects.requireNonNull(CarrierAssemblyR53.selected());var body=new ArrayList<NervLegacyCarrierRideR52.Piece>();var mounting=new CarrierMountProfileR53.State(raised,raised?4.25:0,0);source.parts().forEach((n,p)->body.add(new NervLegacyCarrierRideR52.Piece(n,new NervRigidMeshSweepR52(p.positions()),new double[0],source.frame(n,1,0,0,mounting),"original")));
        boolean sourceBearings=NervBankHeadTransferR53.internalBearings();if(!sourceBearings)throw new IllegalStateException("Original finite spherical/slider contact missing");
        int tests=0,intervals=0,attachmentTests=0;var failures=new ArrayList<Object>();var attachment=new ArrayList<Object>();var legacy=new TreeMap<String,Integer>();var welds=new TreeSet<String>();var finite=new TreeMap<String,Double>();
        for(boolean bank:new boolean[]{false,true})for(boolean returning:new boolean[]{false,true})for(int clock=0;clock<120;clock++)
        {
            intervals++;var pa=pose(bank,returning,clock,raised);var pb=pose(bank,returning,clock+1,raised);var A=h.partsAt(id,1,pa.direction(),pa.slide(),pa.lift(),pa.mounting());var B=h.partsAt(id,1,pb.direction(),pb.slide(),pb.lift(),pb.mounting());double angle=Math.acos(Math.max(-1,Math.min(1,pa.direction().dot(pb.direction()))));double error=angle==0?0:(.35+Math.abs(pa.slide()))*angle*angle/8+2e-6;String kind=bank?"bank":"transverse";
            for(int i=0;i<A.size();i++)
            {
                var a=A.get(i);var end=B.get(i);if(a.role().equals("source_weld"))continue;if(clock>0&&a.frame().equals(end.frame()))continue;
                for(var b:body){if(!a.mesh().envelope(a.frame(),end.frame()).inflate(error).intersects(b.mesh().envelope(b.frame(),b.frame())))continue;attachmentTests++;if(a.mesh().intersects(a.frame(),end.frame(),b.mesh(),b.frame(),b.frame(),.003,new Vec3(error,error,error)))attachment.add(Map.of("kind",kind,"returning",returning,"clock",clock,"rear",a.name(),"carrier",b.name()));}
            }
            for(int i=0;i<A.size();i++)for(int j=i+1;j<A.size();j++)
            {
                var a=A.get(i);var b=A.get(j);var aa=B.get(i);var bb=B.get(j);int axis=bearingAxis(a,b);String names=pair(a.name(),b.name());
                if(axis>=0){double area=Math.min(finiteFace(a,b,axis),finiteFace(aa,bb,axis));if(area<=.00001)failures.add(Map.of("kind",kind,"returning",returning,"clock",clock,"pair",names,"lost_finite_face",area));else finite.merge(names,area,Math::min);continue;}
                if(!a.mesh().envelope(a.frame(),aa.frame()).inflate(error).intersects(b.mesh().envelope(b.frame(),bb.frame()).inflate(error)))continue;
                if(welded(a,b,aa,bb)){welds.add(names);continue;}
                if(side(a.name()).equals(side(b.name()))&&pair(tail(a.name()),tail(b.name())).equals(pair("ball","ball_socket")))continue;
                tests++;if(!a.mesh().intersects(a.frame(),aa.frame(),b.mesh(),b.frame(),bb.frame(),.003,new Vec3(error*2,error*2,error*2)))continue;
                if(sourceHead(a.name())&&sourceHead(b.name())){legacy.merge(names,1,Integer::sum);continue;}
                failures.add(Map.of("kind",kind,"returning",returning,"clock",clock,"pair",names,"error",error));
            }
        }
        var result=new LinkedHashMap<String,Object>();result.put("installed",false);result.put("world_written",false);result.put("above_floor",raised);result.put("load_elevation",raised?4.25:0);result.put("intervals",intervals);result.put("self_pair_tests",tests);result.put("attachment_pair_tests",attachmentTests);result.put("source_revision",Map.of("unchanged_existing_parts",unchanged,"changed_existing_parts",changed,"removed_engineering_parts",removed,"added_engineering_parts",added,"original_18_carrier_parts_unchanged",!raised));result.put("named_rigid_welds",welds);result.put("finite_contact_min_m2",finite);result.put("unchanged_original_head_overlaps_reported",legacy);result.put("new_part_failures",failures);result.put("attachment_failures",attachment);result.put("continuous_scope","Affine source motion and bounded bank curvature per 120-step interval. No native blocks or other actors admitted by this tool.");Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(result));System.out.println("intervals="+intervals+" self="+failures.size()+" attachment="+attachment.size()+" finite="+finite.size());
    }
}

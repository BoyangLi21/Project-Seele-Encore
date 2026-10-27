package com.projectseele.world;

import com.projectseele.entity.NervCarrierPlatformEntity;
import java.io.IOException;
import java.util.*;
import java.util.function.BooleanSupplier;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.phys.*;

/** Owner-controlled lateral slide. It cannot write a route clock or a load frame. */
public final class CarrierRearLateralR53
{
    public static final double STEP = .05;
    private static final Map<UUID,String> REJECTIONS=new LinkedHashMap<>();
    public static String lastRejection(NervCarrierPlatformEntity carrier)
    {return REJECTIONS.getOrDefault(carrier.getUUID(),"source_custody_or_actuator_changed");}

    public record Prepared(CarrierMountProfileR53.PreparedUpdate token,List<AABB> envelopes)
    {
        public Prepared { envelopes=List.copyOf(envelopes); }
    }

    public static boolean supported()
    {
        var hardware=CarrierRearGuideR53.selected();
        return hardware!=null&&hardware.parts().stream().filter(p->p.role().equals("lateral_rod")).count()==2;
    }

    public static Prepared prepare(ServerLevel level,NervCarrierPlatformEntity carrier,double target,
                                   Set<UUID> own,BooleanSupplier ownershipCurrent)throws IOException
    {
        if(!supported()||(target!=0&&target!=1)||!NervOriginalCarrierR52.declared(carrier)
            ||!own.contains(carrier.getUUID())||!ownershipCurrent.getAsBoolean())return null;
        var hardware=CarrierRearGuideR53.selected();
        var original=carrier.originalCarrierStateR52();
        var profile=carrier.carrierMountProfileR53();
        var from=CarrierMountProfileR53.read(carrier,1);
        if(from.aboveFloor()||from.elevation()!=0)return null;
        // Commission the selected source at zero before its first physical step.
        double next=profile.isEmpty()?0:advance(from.transverse(),target);
        var to=new CarrierMountProfileR53.State(false,0,next,from.shallowBay());
        var proof=CarrierRearGuideMotionR53.transverse(level,carrier,from,to,own);
        if(!proof.clear())
        {
            if(REJECTIONS.size()>=32)REJECTIONS.remove(REJECTIONS.keySet().iterator().next());
            REJECTIONS.put(carrier.getUUID(),proof.rejection());return null;
        }
        REJECTIONS.remove(carrier.getUUID());
        long at=level.getGameTime();
        BooleanSupplier current=()->
        {
            if(level.getGameTime()!=at||!ownershipCurrent.getAsBoolean()
                ||CarrierRearGuideR53.selected()!=hardware||!carrier.originalCarrierStateR52().equals(original)
                ||!carrier.carrierMountProfileR53().equals(profile))return false;
            try{return CarrierRearGuideMotionR53.transverse(level,carrier,from,to,own).clear();}
            catch(IOException missing){return false;}
        };
        var token=new CarrierMountProfileR53.PreparedUpdate(carrier,hardware.fingerprint(),original.getLong("Epoch"),from,to,current);
        return new Prepared(token,proof.envelopes());
    }

    static double advance(double from,double target)
    {
        if(!Double.isFinite(from)||from<0||from>1||(target!=0&&target!=1))throw new IllegalArgumentException("Bounded lateral stroke required");
        return Math.abs(target-from)<=STEP?target:from+Math.copySign(STEP,target-from);
    }

    /** Rectangular source faces, not their bounding boxes, must provide support. */
    static boolean rectangular(NervRigidMeshSweepR52 mesh)
    {
        if(mesh.triangleCount()!=12)return false;
        var b=mesh.bounds();double[] lo={b.minX,b.minY,b.minZ},hi={b.maxX,b.maxY,b.maxZ};var xyz=mesh.triangles();
        for(int i=0;i<xyz.length;i++)if(Math.min(Math.abs(xyz[i]-lo[i%3]),Math.abs(xyz[i]-hi[i%3]))>1e-8)return false;
        for(int axis=0;axis<3;axis++)for(double plane:new double[]{lo[axis],hi[axis]})
        {
            int count=0;double area=0;int union=0,shared=15;
            for(int i=0;i<xyz.length;i+=9)if(Math.abs(xyz[i+axis]-plane)<1e-8&&Math.abs(xyz[i+3+axis]-plane)<1e-8&&Math.abs(xyz[i+6+axis]-plane)<1e-8)
            {
                var a=new Vec3(xyz[i],xyz[i+1],xyz[i+2]);var c=new Vec3(xyz[i+3],xyz[i+4],xyz[i+5]);var d=new Vec3(xyz[i+6],xyz[i+7],xyz[i+8]);
                area+=c.subtract(a).cross(d.subtract(a)).length()/2;count++;
                int mask=0;for(int vertex=0;vertex<3;vertex++)
                {
                    int u=(axis+1)%3,v=(axis+2)%3;
                    int corner=(Math.abs(xyz[i+vertex*3+u]-hi[u])<1e-8?1:0)
                        |(Math.abs(xyz[i+vertex*3+v]-hi[v])<1e-8?2:0);
                    mask|=1<<corner;
                }
                if(Integer.bitCount(mask)!=3)return false;union|=mask;shared&=mask;
            }
            if(count!=2||union!=15||(shared!=6&&shared!=9)
                ||Math.abs(area-(hi[(axis+1)%3]-lo[(axis+1)%3])*(hi[(axis+2)%3]-lo[(axis+2)%3]))>1e-8)return false;
        }
        return true;
    }

    static boolean bearings(CarrierRearGuideR53.Hardware hardware,double from,double to)
    {
        if(!CarrierRearGuideR53.liftBearings(hardware))return false;
        for(var mount:hardware.mounts())
        {
            String prefix="rear/"+mount.name()+"/lateral/";
            var rod=hardware.parts().stream().filter(p->p.name().equals(prefix+"rod")&&p.role().equals("lateral_rod")).findFirst().orElse(null);
            if(rod==null||!rectangular(rod.mesh()))return false;
            int side=mount.name().equals("rear_l")?-1:1;
            for(int i=0;i<4;i++)
            {
                final int face=i;
                var sleeve=hardware.parts().stream().filter(p->p.name().equals(prefix+"sleeve/"+face)&&p.frame().equals(rod.frame())).findFirst().orElse(null);
                if(sleeve==null||!rectangular(sleeve.mesh()))return false;
                // The overlap of translated intervals is concave. Checking both
                // ends bounds the whole affine stroke without time sampling.
                for(double amount:new double[]{from,to})
                {
                    var a=rod.mesh().bounds().move(-side*CarrierMountProfileR53.TRANSVERSE_TRAVEL*amount,0,0);
                    if(faceArea(a,sleeve.mesh().bounds(),i<2?1:2)<=.00001)return false;
                }
            }
        }
        return true;
    }

    static double faceArea(AABB a,AABB b,int axis)
    {
        double[] lo={a.minX,a.minY,a.minZ},hi={a.maxX,a.maxY,a.maxZ};
        double[] l={b.minX,b.minY,b.minZ},h={b.maxX,b.maxY,b.maxZ};
        if(Math.min(Math.abs(hi[axis]-l[axis]),Math.abs(h[axis]-lo[axis]))>1e-7)return 0;
        double area=1;for(int k=0;k<3;k++)if(k!=axis)area*=Math.max(0,Math.min(hi[k],h[k])-Math.max(lo[k],l[k]));return area;
    }

    static String selfRejection(List<NervLegacyCarrierRideR52.Piece> from,List<NervLegacyCarrierRideR52.Piece> to)
    {
        if(from.size()!=to.size())return "rear_lateral_topology_changed";
        for(int i=0;i<from.size();i++)for(int j=i+1;j<from.size();j++)
        {
            var a=from.get(i);var b=from.get(j);var aa=to.get(i);var bb=to.get(j);
            if(!a.name().equals(aa.name())||!b.name().equals(bb.name())||a.mesh()!=aa.mesh()||b.mesh()!=bb.mesh())return "rear_lateral_topology_changed";
            // A rigid group retains all of its existing finite joints. Only
            // pairs with changing relative transforms can acquire contact.
            var da=aa.frame().translation().subtract(a.frame().translation());
            var db=bb.frame().translation().subtract(b.frame().translation());
            if(da.distanceToSqr(db)<1e-20&&a.frame().rotationErrorDegrees(aa.frame())<1e-6&&b.frame().rotationErrorDegrees(bb.frame())<1e-6)continue;
            if(!a.mesh().envelope(a.frame(),aa.frame()).intersects(b.mesh().envelope(b.frame(),bb.frame())))continue;
            if(lateralContact(a,b,aa,bb))continue;
            if(a.mesh().intersects(a.frame(),aa.frame(),b.mesh(),b.frame(),bb.frame(),.003,Vec3.ZERO))return a.name()+" / lateral self / "+b.name();
        }
        return null;
    }

    private static boolean lateralContact(NervLegacyCarrierRideR52.Piece a,NervLegacyCarrierRideR52.Piece b,
                                          NervLegacyCarrierRideR52.Piece aa,NervLegacyCarrierRideR52.Piece bb)
    {
        if(!a.role().equals("lateral_rod"))return b.role().equals("lateral_rod")&&lateralContact(b,a,bb,aa);
        String prefix=a.name().substring(0,a.name().lastIndexOf('/')+1);
        if(!b.name().startsWith(prefix+"sleeve/")&&!b.name().startsWith(prefix+"tie/"))return false;
        int index=Integer.parseInt(b.name().substring(b.name().lastIndexOf('/')+1));int axis=index<2?1:2;
        if(!rectangular(a.mesh())||!rectangular(b.mesh())||!b.frame().equals(bb.frame()))return false;
        var relative=b.frame().inverse().compose(a.frame());var relativeEnd=bb.frame().inverse().compose(aa.frame());
        if(relative.rotationErrorDegrees(RigidTransform.identity())>.0001||relativeEnd.rotationErrorDegrees(RigidTransform.identity())>.0001)return false;
        return faceArea(a.mesh().bounds().move(relative.translation()),b.mesh().bounds(),axis)>.00001
            &&faceArea(aa.mesh().bounds().move(relativeEnd.translation()),bb.mesh().bounds(),axis)>.00001;
    }

    private CarrierRearLateralR53(){}
}

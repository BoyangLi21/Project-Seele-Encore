package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.*;

/** Complete continuous lead travel, using the same source and error certificate
 * as native admission. Occupied cells are measurements, not an excavation mask. */
public final class ServiceLeadPitClearanceR53
{
    private static RigidTransform frame(JsonObject value)
    {
        var p=value.getAsJsonArray("position");var q=value.getAsJsonArray("quaternion");
        return new RigidTransform(new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble()),
                q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat());
    }

    public static void main(String[] args)throws Exception
    {
        var input=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        var rows=new ArrayList<Object>();
        for(var raw:input.getAsJsonArray("units"))
        {
            var u=raw.getAsJsonObject();int variant=u.get("variant").getAsInt();
            var spec=new NervServiceFootDriveR52.Spec(variant,frame(u.getAsJsonObject("bay")),
                    frame(u.getAsJsonObject("hatch")),u.get("first_tier").getAsDouble(),u.get("foundation_top").getAsDouble());
            var cells=new LinkedHashMap<Long,Object>();int slices=0;
            for(float[] interval:new float[][]{{0,.9F},{.9F,1}})
            {
                var start=new NervLegacyCarrierRideR52.LeadSampleR52(spec,1,interval[0],0);
                var end=new NervLegacyCarrierRideR52.LeadSampleR52(spec,1,interval[1],0);
                int count=NervLegacyCarrierRideR52.leadSweepDivisionsR52(start,end);
                double error=NervLegacyCarrierRideR52.leadSweepErrorR52(start,end,count);
                var first=NervLegacyCarrierRideR52.actualLeadPartsR52(start);
                for(int k=0;k<count;k++)
                {
                    var last=NervLegacyCarrierRideR52.actualLeadPartsR52(NervLegacyCarrierRideR52.interpolateLeadR52(start,end,(k+1D)/count));
                    if(first.size()!=last.size())throw new IllegalStateException("Lead topology changed");
                    for(int i=0;i<first.size();i++)
                    {
                        var a=first.get(i);var b=last.get(i);
                        if(!a.name().equals(b.name())||a.mesh()!=b.mesh())throw new IllegalStateException("Lead topology changed: "+a.name());
                        var box=a.mesh().envelope(a.frame(),b.frame()).inflate(error);
                        for(int x=(int)Math.floor(box.minX);x<=Math.floor(box.maxX);x++)
                            for(int y=(int)Math.floor(box.minY);y<=Math.floor(box.maxY);y++)
                                for(int z=(int)Math.floor(box.minZ);z<=Math.floor(box.maxZ);z++)
                                {
                                    long key=BlockPos.asLong(x,y,z);if(cells.containsKey(key))continue;
                                    if(a.role().equals("lead_fixed_support")&&y+1<=spec.foundationTop()+NervLegacyCarrierRideR52.FIT
                                            &&a.mesh().envelope(a.frame(),a.frame()).minY>=y+1-NervLegacyCarrierRideR52.FIT)continue;
                                    if(a.mesh().intersects(a.frame(),b.frame(),new AABB(x,y,z,x+1,y+1,z+1).inflate(error),.003))
                                        cells.put(key,Map.of("position",new int[]{x,y,z},"part",a.name(),"rise_interval",new double[]{interval[0]+(interval[1]-interval[0])*k/count,interval[0]+(interval[1]-interval[0])*(k+1)/count}));
                                }
                    }
                    first=last;slices++;
                }
            }
            rows.add(Map.of("variant",variant,"continuous_slices",slices,"occupied_cells",cells.values()));
            System.out.println("variant="+variant+" continuous_slices="+slices+" occupied_cells="+cells.size());
        }
        Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of(
                "world_written",false,"native_admission",false,"source","current production lead geometry and continuous certificate",
                "scope","full rise 0..1 and the same reverse travel; source contacts are not excavation permission","units",rows)));
    }
}

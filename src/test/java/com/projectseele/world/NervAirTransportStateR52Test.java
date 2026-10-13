package com.projectseele.world;

import java.util.*;
import net.minecraft.nbt.*;
import com.projectseele.world.NervAirTransportStateR52.*;
import com.projectseele.world.NervRouteReservationsR52.Original;
import com.projectseele.world.TransportMembershipR52.Kind;

public final class NervAirTransportStateR52Test
{
    private static int checks;
    private static UUID id(int n){return new UUID(0,n);}
    private static void check(boolean value,String message){checks++;if(!value)throw new AssertionError(message);}
    private static void rejects(Runnable op,String why){boolean failed=false;try{op.run();}catch(RuntimeException expected){failed=true;}check(failed,why);}
    private static Job job(int v,int plane)
    {return new Job(id(200+v),id(plane),new Original(52,v,id(10+v),id(20+v),id(30+v),id(100),"same_original_mission","test:flight"),Kind.HULL_ONLY_RECOVERY,"a".repeat(64),"explicit_air_route","actual_receiver",3,17,Phase.CRUISE,Phase.CRUISE,true,false,false,Set.of("same_shared_space"),Set.of(),new CompoundTag(),"");}
    public static void main(String[] args)
    {
        var state=new NervAirTransportStateR52();state.bind(52,"b".repeat(64),"a".repeat(64));state.put(job(0,301));state.put(job(1,302));
        check(state.jobs().size()==2,"Separate original aircraft tasks coexist");
        rejects(()->state.put(job(2,301)),"Aircraft identity cannot be duplicated");
        rejects(()->state.bind(53,"c".repeat(64),"d".repeat(64)),"Active jobs cannot silently adopt another world manifest");
        var cancelled=state.job(id(200)).requestCancel().hold("actual obstacle");state.put(cancelled);
        var nbt=state.save(new CompoundTag());nbt.putString("FutureRootField","verbatim");
        nbt.getList("Jobs",Tag.TAG_COMPOUND).getCompound(0).putByteArray("FutureJobField",new byte[]{0,1,-1,5});
        var restored=NervAirTransportStateR52.load(nbt);check(restored.fault().isEmpty(),"Valid reload accepted in place");
        var j=restored.job(id(200));check(j.aircraft().equals(id(301))&&j.original().eva().equals(id(10)),"Exact original IDs retained");
        check(j.phase()==Phase.HOLD&&j.heldPhase()==Phase.CRUISE&&j.leg()==3&&j.age()==17,"Clock remains at actual stopped leg/fraction");
        check(j.carrying()&&j.cancelRequested()&&!j.payloadTransferred(),"Carried cancellation does not fake release/return");
        check(j.kind()==Kind.HULL_ONLY_RECOVERY&&j.original().plug().equals(id(20))&&j.original().pilot().equals(id(30)),"Original field capsule/pilot provenance retained");
        var round=restored.save(new CompoundTag());check(round.getString("FutureRootField").equals("verbatim")&&Arrays.equals(round.getList("Jobs",Tag.TAG_COMPOUND).getCompound(0).getByteArray("FutureJobField"),new byte[]{0,1,-1,5}),"Unknown NBT root/job fields retained");
        var changed=j.ownerData();changed.putString("Alias","bad");check(!j.ownerData().contains("Alias"),"Caller cannot mutate stored owner state by alias");
        var bad=nbt.copy();bad.getList("Jobs",Tag.TAG_COMPOUND).getCompound(1).putUUID("Aircraft",id(301));
        var fault=NervAirTransportStateR52.load(bad);check(!fault.fault().isEmpty()&&fault.save(new CompoundTag()).equals(bad),"Incompatible reload holds and preserves original raw save");
        var frame=new NervAirTransportManifestR52.Frame(RigidTransform.identity(),RigidTransform.identity(),new NervAirTransportManifestR52.Rig(112,0,1));var sample=NervAircraftFrameCodecR52.encode(frame);sample.putString("FutureFrame","kept");sample.getCompound("Plane").putByteArray("FuturePlane",new byte[]{3,8});sample.getCompound("Cargo").putString("FutureCargo","original");var written=NervAircraftFrameCodecR52.encode(frame,sample);check(written.getString("FutureFrame").equals("kept")&&Arrays.equals(written.getCompound("Plane").getByteArray("FuturePlane"),new byte[]{3,8})&&written.getCompound("Cargo").getString("FutureCargo").equals("original"),"Verified frame updates retain unknown nested original plane/cargo NBT");var detached=NervAircraftFrameCodecR52.encode(new NervAirTransportManifestR52.Frame(frame.plane(),null,frame.rig()),written);check(!detached.contains("Cargo")&&detached.getCompound("DetachedCargoReferenceR52").getString("FutureCargo").equals("original"),"Actual empty stand clears active cargo reference while preserving its original future metadata");
        System.out.println("PASS R52 multi-aircraft saved/reload/cancel state: "+checks);
    }
}

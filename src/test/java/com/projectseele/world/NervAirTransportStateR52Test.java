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
        var poseData=j.ownerData();poseData.putString("FlightStage","ALIGN");poseData.putInt("RescueAlignResumeLegR53",1);
        poseData.putBoolean("RescueLiftBeforeAlignR53",true);poseData.putInt("RescuePoseAgeR53",23);
        var blockedPose=j.update(1,0,Phase.CLAMP,true,false,j.spaces(),j.mechanisms(),poseData,"").hold("pose obstacle");
        restored.put(blockedPose);var poseReload=NervAirTransportStateR52.load(restored.save(new CompoundTag())).job(blockedPose.task());
        check(poseReload.phase()==Phase.HOLD&&poseReload.leg()==1&&poseReload.age()==0
                &&poseReload.ownerData().getInt("RescuePoseAgeR53")==23,"Blocked airborne alignment reload retains its exact lift completion and pose clock");
        check(poseReload.ownerData().getInt("RescueAlignResumeLegR53")==1&&poseReload.carrying()
                &&!poseReload.payloadTransferred(),"Alignment resumes the next loaded corridor without releasing the original payload");
        var departure=new NervAirTransportManifestR52.Frame(
                RigidTransform.of(new net.minecraft.world.phys.Vec3(-314.55,229.84,-464.79),new org.joml.Quaternionf()),
                RigidTransform.of(new net.minecraft.world.phys.Vec3(-314.55,145.84,-464.79),new org.joml.Quaternionf()),new NervAirTransportManifestR52.Rig(84,1,0));
        var destination=new NervAirTransportManifestR52.Frame(
                RigidTransform.of(new net.minecraft.world.phys.Vec3(120.5,200,-35.5),new org.joml.Quaternionf()),
                RigidTransform.of(new net.minecraft.world.phys.Vec3(120.5,116,-35.5),new org.joml.Quaternionf()),departure.rig());
        var clearance=NervAirClearancePlanR53.create("same-corridor",3,17,departure,destination);
        clearance.putInt("Segment",1);clearance.putInt("Age",12);clearance.putBoolean("Validated",true);
        var clearanceData=j.ownerData();clearanceData.put(NervAirClearancePlanR53.KEY,clearance);
        restored.put(j.update(3,17,Phase.CRUISE,true,false,j.spaces(),j.mechanisms(),clearanceData,""));
        var clearanceReload=NervAirTransportStateR52.load(restored.save(new CompoundTag())).job(j.task());
        var route=clearanceReload.ownerData().getCompound(NervAirClearancePlanR53.KEY);
        check(clearanceReload.task().equals(j.task())&&clearanceReload.original().equals(j.original())&&clearanceReload.leg()==3&&clearanceReload.age()==17,
                "Clearance continuation retains the original actors, task and suspended fraction");
        check(route.equals(clearance)&&route.getInt("Segment")==1&&route.getInt("Age")==12,
                "Reload retains the separate continuous clearance segment and clock");
        check(NervAirClearancePlanR53.point(route,0).equals(departure)&&NervAirClearancePlanR53.point(route,3).equals(destination),
                "Clearance route joins the exact actual frame and original corridor destination");
        for(int k=0;k<4;k++)
        {
            var point=NervAirClearancePlanR53.point(route,k);
            check(Math.abs(point.plane().translation().y-point.cargo().translation().y-84)<1e-9&&point.rig().equals(departure.rig()),
                    "Clearance keeps the full attached assembly and hoist offset");
        }
        var before=route.copy();check(NervAirClearancePlanR53.raise(route),"Higher candidate available");
        check(route.getInt("OriginalAge")==17&&route.getCompound("From").equals(before.getCompound("From"))&&route.getCompound("To").equals(before.getCompound("To")),
                "Rejected clearance candidates cannot move the original endpoints or clock");
        System.out.println("PASS R52 multi-aircraft saved/reload/cancel state: "+checks);
    }
}

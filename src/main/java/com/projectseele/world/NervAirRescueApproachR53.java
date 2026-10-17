package com.projectseele.world;

import com.projectseele.entity.*;
import com.projectseele.world.NervRouteReservationsR52.Original;
import java.util.*;
import net.minecraft.nbt.ListTag;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.level.ChunkPos;
import com.projectseele.world.NervAirTransportManifestR52.*;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** Local rescue approach: preserve the observed body, then pull it into
 * clearance with the existing six telescopic clamps before vertical lift. */
public final class NervAirRescueApproachR53
{
    private static final TicketType<ChunkPos> TICKET=TicketType.create("nerv_rescue_approach_r53",Comparator.comparingLong(ChunkPos::toLong),100);
    public static String prepare(ServerLevel level, NervAirTransportManifestR52 manifest,
            Mission mission, NervFlightProofR52.FlightPickupPreview preview, CompoundTag data)
    {
        if(data.getBoolean("RescuePlannedR53"))return "";
        var eva=(EvaUnit01Entity)level.getEntity(preview.original().eva());
        var root=preview.root().translation();
        var pickup=NervActualPickupFramesR52.at(manifest,mission,mission.pickupNode(),preview.root(),false);
        var box=eva.getBoundingBox();
        // Native block collision ignores water. The ordinary first lift
        // raises a submerged EVA; dry foot support is never required.
        double waterLift=0;
        int cursor=data.getInt("RescueSearchR53");
        // Spread an obstructed search over ticks; never scan the whole world
        // or synchronously load distant chunks from a rescue request.
        for(int budget=0;budget<4&&cursor<65;budget++,cursor++)
        {
            int radius=cursor==0?0:((cursor-1)/8+1)*12;
            double angle=cursor==0?0:(cursor-1)%8*Math.PI/4;
            var delta=new Vec3(Math.cos(angle)*radius,waterLift,Math.sin(angle)*radius);
            var plane=pickup.plane().translation().add(delta);
            // Each original piston has a 144 m stroke. Its attachments,
            // rather than EVA foot support, determine rescue reach.
            boolean reachable=true;
            for(var anchor:preview.anchors())
                if(preview.root().transformPoint(anchor).distanceTo(plane.add(0,-11,0))>140){reachable=false;break;}
            if(!reachable)continue;
            var aircraft=NervRigidMeshSweepR52.transformed(new AABB(-59,-12,-28,59,10,28),RigidTransform.of(plane,pickup.plane().rotation()));
            var moved=box.move(delta);
            var upright=radius==0
                    ?new AABB(box.minX+.08,box.maxY+.08,box.minZ+.08,box.maxX-.08,Math.max(box.maxY+16,plane.y-12),box.maxZ-.08)
                    :new AABB(moved.minX+.08,moved.minY+.08,moved.minZ+.08,moved.maxX-.08,Math.max(moved.maxY+16,plane.y-12),moved.maxZ-.08);
            if(!loaded(level,aircraft)||!loaded(level,upright))
            {data.putInt("RescueSearchR53",cursor);return "正在载入附近起吊区域";}
            if(level.getBlockCollisions(eva,aircraft).iterator().hasNext())continue;
            if(level.getBlockCollisions(eva,upright).iterator().hasNext())continue;
            // Existing shallow contact at the source is allowed. Along the
            // pull, require the body corridor itself to remain unobstructed.
            boolean clear=true;int steps=Math.max(1,(int)Math.ceil(delta.length()/6));
            for(int i=1;radius!=0&&i<=steps;i++)
            {
                var sample=box.move(delta.scale(i/(double)steps)).deflate(.15);
                if(!loaded(level,sample)){data.putInt("RescueSearchR53",cursor);return "正在载入附近牵引通道";}
                for(var shape:level.getBlockCollisions(eva,sample))
                    for(var obstacle:shape.toAabbs())if(!obstacle.intersects(box.inflate(.15))){clear=false;break;}
                if(!clear)break;
            }
            if(!clear)continue;
            data.putDouble("RescueDXR53",delta.x);data.putDouble("RescueDYR53",delta.y);data.putDouble("RescueDZR53",delta.z);
            data.putBoolean("RescuePlannedR53",true);data.remove("RescueSearchR53");return "";
        }
        data.putInt("RescueSearchR53",cursor);
        return cursor>=65?"无法回收：夹具可达范围内未找到起吊口，空间封闭或出口净宽不足。":"正在寻找遮挡外的起吊位置";
    }
    private static boolean loaded(ServerLevel level,AABB box)
    {
        boolean ready=true;
        for(int x=(int)Math.floor(box.minX)>>4;x<=(int)Math.floor(box.maxX)>>4;x++)
            for(int z=(int)Math.floor(box.minZ)>>4;z<=(int)Math.floor(box.maxZ)>>4;z++)
                if(level.getChunkSource().getChunkNow(x,z)==null)
                {var cp=new ChunkPos(x,z);level.getChunkSource().addRegionTicket(TICKET,cp,1,cp);ready=false;}
        return ready;
    }
    public static Vec3 offset(CompoundTag data)
    {return new Vec3(data.getDouble("RescueDXR53"),data.getDouble("RescueDYR53"),data.getDouble("RescueDZR53"));}
    public static Frame frame(Mission mission,String node,Frame original,CompoundTag data)
    {
        if(!data.getBoolean("RescuePlannedR53")||!(node.equals(mission.pickupNode())||node.startsWith(mission.pickupNode()+"/")))return original;
        var shift=offset(data);var cargo=original.cargo();
        if(cargo!=null&&(!node.equals(mission.pickupNode())||data.getBoolean("RescueExtractedR53")))
            cargo=RigidTransform.of(cargo.translation().add(shift),cargo.rotation());
        return new Frame(RigidTransform.of(original.plane().translation().add(shift),original.plane().rotation()),cargo,original.rig());
    }
    public static boolean posture(ServerLevel level,Original original,UUID aircraft,CompoundTag data)
    {
        if(!(level.getEntity(original.eva()) instanceof EvaUnit01Entity eva)
                ||!(level.getEntity(aircraft) instanceof UNTransportEntity plane)
                ||!EvaMechanicalFrameR52.active(eva)||!EvaMechanicalFrameR52.flightCustody(eva)
                ||!NervAircraftFrameR52.active(plane))return false;
        var frame=NervAircraftFrameR52.frame(plane,1);
        if(frame.cargo()==null||frame.rig().deployment()!=1||frame.rig().jaws()!=0
                ||!NervAirTransportManifestR52.same(frame.cargo(),EvaMechanicalFrameR52.frame(eva,1)))return false;
        int age=data.getInt("RescuePoseAgeR53");if(age>=60)return true;
        if(!data.contains("RescueBodyR53"))
        {
            data.put("RescueBodyR53",EvaShutdownR30.encode(EvaMechanicalFrameR52.frozenLocalPose(eva)));
            data.put("RescueHandsR53",EvaFrozenHandsR52.capture(eva,1));
        }
        var start=EvaBodyPose.neutralForTransportR32(eva);EvaShutdownR30.decode(data.getCompound("RescueBodyR53"),start);
        float t=(float)NervAirTransportRuntimeR52.ease((age+1D)/60);
        var body=EvaBodyPose.blend(start,EvaBodyPose.neutralForTransportR32(eva),t);
        var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();
        var from=EvaFrozenHandsR52.decode(eva.getUnitVariant(),provider.handContractFingerprint(eva.getUnitVariant()),provider.handJoints(eva.getUnitVariant()),data.getCompound("RescueHandsR53"));
        var goal=EvaAnatomicalHandsR45.ordinaryReleaseTargetR52(eva.getUnitVariant(),false);
        var joints=new LinkedHashMap<String,org.joml.Quaternionf>();
        for(String name:from.rotations().keySet())joints.put(name,new org.joml.Quaternionf(from.rotations().get(name)).slerp(goal.rotations().get(name),t));
        var hands=new EvaAnatomicalHandsR45.Pose(goal.left(),goal.right(),Map.copyOf(joints));
        if(!EvaMechanicalFrameR52.applyGroundedPoseR52(eva,original,body,hands,provider.evaluate(eva.getUnitVariant(),body,hands)))return false;
        var refreshed=NervFlightProofR52.inspect(level,original,TransportMembershipR52.Kind.OCCUPIED);
        if(refreshed==null)throw new IllegalStateException("Aligned occupied rescue body lost its original capsule");
        // Update only the live contact samples. Aircraft frame, task and
        // original identity remain unchanged; jaws follow each joint step.
        var live=new CompoundTag();NervAircraftFrameR52.save(plane,live);var tag=live.getCompound("R52AircraftSample");
        tag.put("PreviousAnchorsR52",tag.getList("Anchors",10).copy());tag.put("PreviousJawAxesR52",tag.getList("JawAxes",10).copy());
        tag.putBoolean("RecoveryAnchorBlendR52",true);tag.putLong("At",level.getGameTime());
        tag.put("Previous",tag.getCompound("Current").copy());
        double clock=tag.getDouble("RotorCurrent");tag.putDouble("RotorPrevious",clock);tag.putDouble("RotorCurrent",clock+1);
        var anchors=new ListTag();var axes=new ListTag();
        for(var point:refreshed.anchors())anchors.add(point(point));
        for(var point:refreshed.jawAxes())axes.add(point(point));
        tag.put("Anchors",anchors);tag.put("JawAxes",axes);NervAircraftFrameR52.load(plane,live);
        data.putInt("RescuePoseAgeR53",age+1);
        if(age+1==60)eva.stowHandsForShutdownR30();
        return age+1==60;
    }
    public static void settleParked(ServerLevel level)
    {
        var state=NervRouteRuntimeR52.installationStateR52(level);if(state==null)return;
        for(var job:state.jobs())
        {
            if(job.snapshot().kind()!=TransportMembershipR52.Kind.OCCUPIED||!job.phase().name().equals("PARKED")||!job.ownerData().getString("Finish").equals("DONE"))continue;
            var original=job.snapshot().original();
            if(!(level.getEntity(original.eva()) instanceof EvaUnit01Entity eva)||!eva.isNervLogisticsLocked()
                    ||!EvaMechanicalFrameR52.serviceSourceHeldR52(eva))continue;
            var live=new CompoundTag();EvaMechanicalFrameR52.save(eva,live);var tag=live.getCompound("R52MechanicalSample");
            if(tag.getBoolean("RescueServiceSettledR53"))continue;
            if(!tag.contains("RescueServiceStartR53"))
            {tag.put("RescueServiceStartR53",tag.getCompound("HeldBody").copy());tag.put("RescueServiceHandsR53",tag.getCompound("HeldHands").copy());}
            int age=tag.getInt("RescueServiceAgeR53")+1;float t=(float)NervAirTransportRuntimeR52.ease(age/60D);
            var start=EvaBodyPose.neutralForTransportR32(eva);EvaShutdownR30.decode(tag.getCompound("RescueServiceStartR53"),start);
            var body=EvaBodyPose.blend(start,EvaBodyPose.neutralForTransportR32(eva),t);
            var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();
            var from=EvaFrozenHandsR52.decode(eva.getUnitVariant(),provider.handContractFingerprint(eva.getUnitVariant()),provider.handJoints(eva.getUnitVariant()),tag.getCompound("RescueServiceHandsR53"));
            var goal=EvaAnatomicalHandsR45.ordinaryReleaseTargetR52(eva.getUnitVariant(),false);
            var joints=new LinkedHashMap<String,org.joml.Quaternionf>();
            for(String name:from.rotations().keySet())joints.put(name,new org.joml.Quaternionf(from.rotations().get(name)).slerp(goal.rotations().get(name),t));
            var hands=new EvaAnatomicalHandsR45.Pose(goal.left(),goal.right(),Map.copyOf(joints));
            tag.put("HeldBody",EvaShutdownR30.encode(body));tag.put("HeldHands",EvaFrozenHandsR52.encode(eva.getUnitVariant(),EvaAnatomicalHandsR45.contractFingerprintR45(eva.getUnitVariant()),hands));
            tag.putLong("HeldAt",level.getGameTime());tag.putInt("RescueServiceAgeR53",age);
            if(age>=60){tag.putBoolean("RescueServiceSettledR53",true);tag.remove("RescueServiceStartR53");tag.remove("RescueServiceHandsR53");eva.stowHandsForShutdownR30();}
            EvaMechanicalFrameR52.load(eva,live);eva.setBoundingBox(EvaMechanicalFrameR52.serviceBoundsR52(eva));
        }
    }
    private static CompoundTag point(Vec3 p)
    {var t=new CompoundTag();t.putDouble("X",p.x);t.putDouble("Y",p.y);t.putDouble("Z",p.z);return t;}
    private NervAirRescueApproachR53(){}
}

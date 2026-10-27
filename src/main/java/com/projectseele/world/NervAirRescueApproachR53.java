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
            Mission mission, NervFlightProofR52.FlightPickupPreview preview, CompoundTag data,
            NervAirframeGeometryR52 geometry)
    {
        var observed=NervAircraftFrameR52.encodeRigid(preview.root());
        if(!observed.equals(data.getCompound("RescueObservedRootR53"))
                ||!preview.bodySnapshotR52().equals(data.getCompound("RescueObservedBodyR53"))
                ||!preview.handSnapshotR52().equals(data.getCompound("RescueObservedHandsR53")))
        {
            data.remove("RescuePlannedR53");data.remove("RescueSearchR53");data.remove("RescueRejectedR53");data.remove("RescueCanopyR53");
            data.put("RescueObservedRootR53",observed);data.put("RescueObservedBodyR53",preview.bodySnapshotR52());
            data.put("RescueObservedHandsR53",preview.handSnapshotR52());
        }
        if(data.getBoolean("RescuePlannedR53"))return "";
        String precheckMode=NervTraversalPolicyR53.mode(level).name();
        if(!precheckMode.equals(data.getString("RescuePrecheckModeR53")))
        {
            data.remove("RescueSearchR53");data.remove("RescueRejectedR53");
            data.remove("RescueLastRejectedCandidateR53");
            data.putString("RescuePrecheckModeR53",precheckMode);
        }
        // A persisted rejected cursor predates the exact captured-contact
        // proof. Reconsider its candidates once, within this same order.
        if(data.getInt("RescueContactProofVersionR53")<2)
        {
            data.remove("RescueSearchR53");data.remove("RescueRejectedR53");
            data.remove("RescueLastRejectedCandidateR53");
            data.putInt("RescueContactProofVersionR53",2);
        }
        var eva=(EvaUnit01Entity)level.getEntity(preview.original().eva());
        var pickup=NervActualPickupFramesR52.at(manifest,mission,mission.pickupNode(),preview.root(),false);
        // Native block collision ignores water. The ordinary first lift
        // raises a submerged EVA; dry foot support is never required.
        double waterLift=0;
        int cursor=data.getInt("RescueSearchR53");
        // Spread an obstructed search over ticks; never scan the whole world
        // or synchronously load distant chunks from a rescue request.
        for(int budget=0;budget<1&&cursor<65;budget++,cursor++)
        {
            int radius=cursor==0?0:((cursor-1)/8+1)*12;
            double angle=cursor==0?0:(cursor-1)%8*Math.PI/4;
            var delta=new Vec3(Math.cos(angle)*radius,waterLift,Math.sin(angle)*radius);
            var plane=pickup.plane().translation().add(delta);
            // Each original piston has a 144 m stroke. Its attachments,
            // rather than EVA foot support, determine rescue reach.
            boolean reachable=true;
            var planeRoot=RigidTransform.of(plane,pickup.plane().rotation());
            for(int i=0;i<preview.anchors().size();i++)
            {
                var top=planeRoot.transformPoint(new Vec3(i%2==0?14:-14,-11,(i/2-1)*11));
                if(preview.root().transformPoint(preview.anchors().get(i)).distanceTo(top)>144){reachable=false;break;}
            }
            if(!reachable)continue;
            var emptyFrame=new Frame(planeRoot,null,new Rig(pickup.rig().hoist(),0,1));
            var aircraftSweep=geometry.sweep(emptyFrame,emptyFrame,List.of(),0,360D/47,.2);
            AABB aircraft=null;
            for(var envelope:aircraftSweep.envelopes())aircraft=aircraft==null?envelope:aircraft.minmax(envelope);
            if(!loaded(level,aircraft))
            {data.putInt("RescueSearchR53",cursor);return "正在载入附近起吊区域";}
            boolean aircraftClear=true;
            if(!NervTraversalPolicyR53.bypass(level))for(var shape:level.getBlockCollisions(eva,aircraft))
            {
                for(var obstacle:shape.toAabbs())if(aircraftSweep.intersects(obstacle)){aircraftClear=false;break;}
                if(!aircraftClear)break;
            }
            if(!aircraftClear){rejection(data,"airframe",cursor);continue;}
            var extracted=RigidTransform.of(preview.root().translation().add(delta),preview.root().rotation());
            var first=manifest.corridor(mission.loaded().get(0));
            if(!first.from().equals(mission.pickupNode()))return "无法回收：已登记航路缺少原接载点的起吊段。";
            var declaredLift=NervActualPickupFramesR52.at(manifest,mission,first.to(),preview.root(),true);
            if(declaredLift.cargo()==null)return "无法回收：已登记起吊段缺少完整载荷。";
            var lifted=RigidTransform.of(declaredLift.cargo().translation().add(delta),preview.root().rotation());
            var clamped=new Frame(planeRoot,preview.root(),new Rig(pickup.rig().hoist(),1,0));
            var pulled=new Frame(planeRoot,extracted,clamped.rig());
            var liftFrame=new Frame(RigidTransform.of(declaredLift.plane().translation().add(delta),declaredLift.plane().rotation()),lifted,declaredLift.rig());
            if(NervTraversalPolicyR53.strict(level))
            {
                // Whole-corridor diagnosis is opt-in; ordinary movement still
                // obtains its real current-tick proof in the transport runtime.
                int vertical=clearance(level,manifest,mission,geometry,preview,pulled,liftFrame,
                        NervAirTravelR53.ticks(first,clamped,liftFrame),first.spaces());
                if(vertical==2){data.putInt("RescueSearchR53",cursor);return "正在载入附近起吊区域";}
                if(vertical!=0){rejection(data,"vertical",cursor);continue;}
                int pull=clearance(level,manifest,mission,geometry,preview,clamped,pulled,
                        Math.max(40,(int)Math.ceil(delta.length()*1.875/.6)),manifest.node(mission.pickupNode()).spaces());
                if(pull==2){data.putInt("RescueSearchR53",cursor);return "正在载入附近牵引通道";}
                if(pull!=0){rejection(data,"pull",cursor);continue;}
                int clamp=clearance(level,manifest,mission,geometry,preview,
                        new Frame(planeRoot,preview.root(),new Rig(pickup.rig().hoist(),0,1)),clamped,20,
                        manifest.node(mission.pickupNode()).spaces());
                if(clamp==2){data.putInt("RescueSearchR53",cursor);return "正在载入夹具接载区域";}
                if(clamp!=0){rejection(data,"clamp",cursor);continue;}
            }
            data.putDouble("RescueDXR53",delta.x);data.putDouble("RescueDYR53",delta.y);data.putDouble("RescueDZR53",delta.z);
            data.putBoolean("RescuePlannedR53",true);data.putBoolean("RescueCanopyR53",!manifest.receiver(mission.receiver()).delivery());data.remove("RescueSearchR53");return "";
        }
        data.putInt("RescueSearchR53",cursor);
        return cursor>=65?"无法回收：夹具可达范围内未找到起吊口，空间封闭或出口净宽不足。":"正在寻找遮挡外的起吊位置";
    }
    private static void rejection(CompoundTag data,String reason,int cursor)
    {
        var counts=data.getCompound("RescueRejectedR53");
        counts.putInt(reason,counts.getInt(reason)+1);data.put("RescueRejectedR53",counts);
        data.putInt("RescueLastRejectedCandidateR53",cursor);
    }
    /** 0 complete source clear, 1 blocked, 2 chunks not yet available. */
    private static int clearance(ServerLevel level,NervAirTransportManifestR52 manifest,Mission mission,
            NervAirframeGeometryR52 geometry,NervFlightProofR52.FlightPickupPreview preview,
            Frame from,Frame to,int ticks,Set<String> fallback)
    {
        var context=NervRouteRuntimeR52.flightContext(level);if(context==null)return 1;
        try
        {
            var prepared=NervFlightProofR52.prepareSourceSweepR52(level,geometry,preview,from,to,0,ticks,true);
            for(var envelope:prepared.envelopes())if(!loaded(level,envelope))return 2;
            var spaces=manifest.directory().dynamicSpacesR52().domains().isEmpty()?fallback:
                    manifest.directory().dynamicSpacesR52().required(manifest.dimension(),prepared.envelopes(),context.bindings());
            var aircraft=manifest.aircraft().get(mission.aircraft()).entity();
            boolean clear=manifest.receiver(mission.receiver()).delivery()
                    ?NervFlightProofR52.pathClear(level,manifest,geometry,aircraft,preview,from,to,spaces,context.bindings(),true,ticks,null,prepared)
                    :NervFlightProofR52.recoveryCanopyR53(level,manifest,geometry,aircraft,preview,from,to,spaces,context.bindings(),prepared,false);
            return clear?0:1;
        }
        catch(IllegalArgumentException|IllegalStateException unavailable){return 1;}
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
        // Preserve the captured orientation until the complete first rise ends.
        if(cargo!=null&&data.getBoolean("RescueLiftBeforeAlignR53")&&node.equals(mission.pickupNode()+"/lifted"))
            cargo=RigidTransform.of(cargo.translation(),NervAircraftFrameR52.decodeRigid(data.getCompound("PickupRoot")).rotation());
        return new Frame(RigidTransform.of(original.plane().translation().add(shift),original.plane().rotation()),cargo,original.rig());
    }
    public static boolean posture(ServerLevel level,Original original,UUID aircraft,CompoundTag data,NervAirframeGeometryR52 airframe)
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
        data.putBoolean("RescuePoseBlockedR53",false);
        var checkedGeometry=NervAirRescuePoseR53.check(level,original,plane,eva,body,hands,airframe);
        if(checkedGeometry==null)
        {data.putBoolean("RescuePoseBlockedR53",true);return false;}
        if(!EvaMechanicalFrameR52.applyGroundedPoseR52(eva,original,body,hands,checkedGeometry))return false;
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

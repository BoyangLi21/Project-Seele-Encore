package com.projectseele.world;

import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.world.NervRouteReservationsR52.*;
import com.projectseele.world.NervRouteDirectoryR52.*;
import java.util.*;
import net.minecraft.nbt.*;
import net.minecraft.server.level.ServerLevel;

/** One original empty carrier follows existing Root legs. Its separate hardware
 * lease uses the same physical broker, without acquiring EVA/pilot/plug control. */
public final class NervEmptyCarrierTransferR52
{
    private static final String KEY="EmptyCarrierTransferR52";
    private record Edge(String leg,String from,String to){}

    static long arrivalTicks(ServerLevel level, Original original, String targetPort)
    {
        var context=NervRouteRuntimeR52.flightContext(level);
        var controller=NervOriginalCarrierR52.controller(level,original);
        if(context==null||controller==null)return Long.MAX_VALUE/8;
        var directory=context.directory();var port=directory.ports().get(targetPort);
        if(port==null)return Long.MAX_VALUE/8;
        FootSupportFrameR52.Binding binding;
        try{binding=NervOriginalCarrierR52.nominalBinding(original.variant());}
        catch(java.io.IOException unavailable){return Long.MAX_VALUE/8;}
        var node=actualNode(directory,original.variant(),NervOriginalCarrierR52.actualRoot(controller,1),binding);
        if(node==null)return Long.MAX_VALUE/8;
        var path=existingPath(directory,original.variant(),node,port.node());
        if(path==null)return Long.MAX_VALUE/8;
        long ticks=(long)Math.ceil((1-NervOriginalCarrierR52.progress(controller,1))*80);
        for(String id:path)
        {
            var leg=directory.leg(id);
            int step=leg.motion()==Motion.FOOT_BEARING_TURN&&!NervR50CarrierModeR53.enabled()?2:4;
            ticks+=(leg.ticks()+step-1)/step;
        }
        return ticks;
    }
    /** Every edge already belongs to a Root forward or reverse route for this
     * variant. BFS cuts their shared prefix at the existing common bank node. */
    public static List<String> existingPath(NervRouteDirectoryR52 directory,int variant,String from,String to)
    {
        if(from.equals(to))return List.of();var edges=new LinkedHashMap<String,Edge>();
        for(var route:directory.routes().values())if(route.variant()==variant)for(String id:route.legs()){var leg=directory.leg(id);edges.put(id,new Edge(id,leg.from(),leg.to()));}
        var queue=new ArrayDeque<String>();var previous=new HashMap<String,Edge>();var visited=new HashSet<String>();queue.add(from);visited.add(from);
        while(!queue.isEmpty())
        {String node=queue.remove();for(var edge:edges.values())if(edge.from().equals(node)&&visited.add(edge.to())){previous.put(edge.to(),edge);if(edge.to().equals(to)){var result=new ArrayList<String>();String at=to;while(!at.equals(from)){var e=previous.get(at);result.add(e.leg());at=e.from();}Collections.reverse(result);return List.copyOf(result);}queue.add(edge.to());}}
        return null;
    }
    private static String actualNode(NervRouteDirectoryR52 directory,int variant,RigidTransform actual,FootSupportFrameR52.Binding binding)
    {
        for(var route:directory.routes().values())if(route.variant()==variant)for(String id:route.legs())
        {var leg=directory.leg(id);if(NervAirTransportManifestR52.same(directory.sample(leg,0,binding).evaRoot(),actual))return leg.from();if(NervAirTransportManifestR52.same(directory.sample(leg,1,binding).evaRoot(),actual))return leg.to();}return null;
    }
    private static List<String> readList(CompoundTag data,String key){var result=new ArrayList<String>();for(var value:data.getList(key,Tag.TAG_STRING))result.add(value.getAsString());return List.copyOf(result);}
    private static void list(CompoundTag data,String key,List<String> values){var tag=new ListTag();values.forEach(v->tag.add(StringTag.valueOf(v)));data.put(key,tag);}
    private static boolean geometryLease(ServerLevel level,Original original,NervCarrierPlatformEntity controller,UUID flight,CompoundTag state,Set<String> resources,NervOriginalCarrierR52.CheckedStep proof)
    {
        var context=NervRouteRuntimeR52.flightContext(level);if(context==null||proof==null||!proof.current(level))return false;
        var lease=new HardwareLease(state.getUUID("Task"),controller.getUUID(),original.variant(),context.directory().epoch(),context.directory().fingerprint(),resources,flight);
        return context.pool().reserveHardware(lease,new HardwareAccess(){
            @Override public boolean sameOriginalCarrier(UUID id,int variant,long epoch){return controller.getUUID().equals(id)&&variant==original.variant()&&epoch==context.directory().epoch()&&NervOriginalCarrierR52.controller(level,original)==controller;}
            @Override public boolean checkedCarrierGeometry(UUID id,Set<Resource> declared,boolean restoring)
            {
                if(!proof.current(level)||!declared.stream().allMatch(r->context.nativeAccess().resourceReady(r.id(),false)))return false;
                var boxes=new ArrayList<net.minecraft.world.phys.AABB>();for(var r:declared)if(r.kind()==ResourceKind.SPACE){var b=context.bindings().get(r.id());if(b==null)return false;boxes.addAll(b.spaces());}
                return proof.envelopes().stream().allMatch(b->NervAirspaceCoverageR52.covered(b,boxes));
            }
        },context.pool().queryHardware(lease.task())==null);
    }
    /** Actual source actor/pose is read first. A failed proof leaves its last
     * accepted frame, saved fraction and physical leases untouched. */
    public static boolean ensure(ServerLevel level,Original original,String targetPort,UUID companionFlight,CompoundTag flightData)
    {try{flightData.remove("EmptyCarrierWaitR53");return ensureSource(level,original,targetPort,companionFlight,flightData);}catch(java.io.IOException|IllegalArgumentException|IllegalStateException missing){flightData.putString("EmptyCarrierWaitR53",missing.getMessage()==null?missing.toString():missing.getMessage());return false;}}
    private static boolean ensureSource(ServerLevel level,Original original,String targetPort,UUID companionFlight,CompoundTag flightData)throws java.io.IOException
    {
        var context=NervRouteRuntimeR52.flightContext(level);var controller=NervOriginalCarrierR52.controller(level,original);if(context==null||controller==null)return false;
        var directory=context.directory();var port=directory.ports().get(targetPort);if(port==null||!port.reverseRoutes().containsKey(original.variant()))return false;
        var binding=NervOriginalCarrierR52.nominalBinding(original.variant());var reverse=directory.route(port.reverseRoutes().get(original.variant()));if(reverse==null||reverse.legs().isEmpty())return false;
        var endpoint=directory.sample(directory.leg(reverse.legs().get(0)),0,binding).evaRoot();var current=NervOriginalCarrierR52.actualRoot(controller,1);float rise=NervOriginalCarrierR52.progress(controller,1);
        var state=flightData.getCompound(KEY).copy();
        if(state.isEmpty())
        {
            String node=actualNode(directory,original.variant(),current,binding);if(node==null)return false;var legs=existingPath(directory,original.variant(),node,port.node());if(legs==null)return false;
            state.putUUID("Task",UUID.randomUUID());state.putUUID("Controller",controller.getUUID());state.putString("Directory",directory.fingerprint());state.putString("Port",targetPort);state.putString("Stage","RAISE");state.putInt("Index",0);state.putInt("Age",0);list(state,"Legs",legs);flightData.put(KEY,state.copy());
        }
        if(!state.getUUID("Controller").equals(controller.getUUID())||!state.getString("Directory").equals(directory.fingerprint())||!state.getString("Port").equals(targetPort))return false;
        var legs=readList(state,"Legs");int index=state.getInt("Index"),age=state.getInt("Age");if(index<0||index>legs.size())return false;
        var own=new HashSet<UUID>();own.add(controller.getUUID());
        var flight=context.pool().queryFlight(companionFlight);
        // At the receiving endpoint the rising rack docks around this flight's
        // original EVA. It is the handoff payload, not an unrelated obstacle.
        if(index==legs.size()&&NervAirTransportManifestR52.same(current,endpoint)
                &&flight!=null&&!flight.payloadTransferred()&&flight.original().equals(original))
        {
            own.addAll(TransportMembershipR52.members(original,flight.kind()));
            own.add(flight.aircraft());
        }
        Leg leg=index<legs.size()?directory.leg(legs.get(index)):directory.leg(reverse.legs().get(0));if(leg==null)return false;
        boolean legacy=NervR50CarrierModeR53.enabled();boolean mechanicalTurn=leg.motion()==Motion.FOOT_BEARING_TURN&&!legacy;
        Leg next=index+1<legs.size()?directory.leg(legs.get(index+1)):null;var held=new HashSet<>(leg.resources());if(next!=null&&next.motion()==Motion.FOOT_BEARING_TURN)held.addAll(next.resources());
        // A traversed station remains actual steel above its foundation until
        // its independently checked storage movement finishes. Its resources
        // remain owned across the next leg and the stopped receiver frame.
        held.addAll(context.owner().pendingEmptyStationResourcesR52(level,original,flightData));
        for(String id:held)if(!context.nativeAccess().resourceReady(id,false)){flightData.putString("EmptyCarrierWaitR53","resource:"+id);flightData.put(KEY,state);return false;}
        var stationary=NervOriginalCarrierR52.proposeActuator(level,controller,rise,rise,own);if(!geometryLease(level,original,controller,companionFlight,state,held,stationary)){flightData.putString("EmptyCarrierWaitR53","stationary/lease");flightData.put(KEY,state);return false;}
        if(!context.owner().prepareEmptyCarrierGatesR52(level,original,controller.getUUID(),Set.copyOf(leg.doors()),flightData)){flightData.putString("EmptyCarrierWaitR53","opening:"+leg.doors());flightData.put(KEY,state);return false;}
        for(String id:leg.resources())if(!context.nativeAccess().resourceReady(id,directory.resource(id).kind()==ResourceKind.DOOR)){flightData.putString("EmptyCarrierWaitR53","operating:"+id);flightData.put(KEY,state);return false;}
        if(index==legs.size()&&NervAirTransportManifestR52.same(current,endpoint)&&rise==1){
            if(!context.owner().finishEmptyStationIdleR52(level,original,controller.getUUID(),flightData)){flightData.put(KEY,state);return false;}
            if(!context.owner().pendingEmptyStationResourcesR52(level,original,flightData).isEmpty()){flightData.put(KEY,state);return false;}
            context.pool().releaseHardware(state.getUUID("Task"),controller.getUUID());state.putString("Stage","READY");flightData.put(KEY,state);return true;
        }
        if(rise<1)
        {
            float nextRise=Math.min(1,rise+1F/80);var accepted=NervOriginalCarrierR52.proposeActuator(level,controller,rise,nextRise,own);if(accepted==null||!geometryLease(level,original,controller,companionFlight,state,held,accepted)||!accepted.commit(level)){flightData.put(KEY,state);return false;}
            if(nextRise==1)state.putString("Stage","MOVE");flightData.put(KEY,state);return false;
        }
        if(index>=legs.size()){flightData.put(KEY,state);return false;}
        if(!legacy&&next!=null&&next.motion()==Motion.FOOT_BEARING_TURN&&!context.owner().prepareEmptyCarrierTurnR52(level,original,controller.getUUID(),next,flightData)){flightData.put(KEY,state);return false;}
        if(mechanicalTurn&&!context.owner().prepareEmptyCarrierTurnR52(level,original,controller.getUUID(),leg,flightData)){flightData.put(KEY,state);return false;}
        if(age==leg.ticks()){if(mechanicalTurn&&!context.owner().finishEmptyCarrierTurnR52(level,original,controller.getUUID(),leg,flightData)){flightData.put(KEY,state);return false;}state.putInt("Index",index+1);state.putInt("Age",0);flightData.put(KEY,state);return false;}
        if(age<0||age>leg.ticks()||!NervAirTransportManifestR52.same(current,directory.sample(leg,NervMechanicalTravelR52.fraction(age,leg.ticks()),binding).evaRoot()))return false;
        int nextAge=Math.min(leg.ticks(),age+(mechanicalTurn?2:4));
        var curve=new DirectoryTrajectoryR52(directory,leg,binding,NervMechanicalTravelR52.fraction(age,leg.ticks()),NervMechanicalTravelR52.fraction(nextAge,leg.ticks()));
        if(mechanicalTurn){if(!context.owner().applyEmptyCarrierTurnR52(level,original,controller.getUUID(),curve,flightData)){flightData.put(KEY,state);return false;}}
        else {var moved=NervOriginalCarrierR52.propose(level,controller,curve,1,1,own);if(moved==null||!geometryLease(level,original,controller,companionFlight,state,held,moved)||!moved.commit(level)){flightData.putString("EmptyCarrierWaitR53","movement/lease:"+NervOriginalCarrierR52.lastRejectionR53(controller));flightData.put(KEY,state);return false;}}
        state.put("LastFrom",NervAircraftFrameR52.encodeRigid(curve.sample(0).evaRoot()));state.put("LastTo",NervAircraftFrameR52.encodeRigid(curve.sample(1).evaRoot()));state.putLong("LastAt",level.getGameTime());
        if(nextAge>=leg.ticks()&&!mechanicalTurn){state.putInt("Index",index+1);state.putInt("Age",0);}else state.putInt("Age",nextAge);state.putString("Stage","MOVE");flightData.put(KEY,state);return false;
    }
    private NervEmptyCarrierTransferR52(){}
}

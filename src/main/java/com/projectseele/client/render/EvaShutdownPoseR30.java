package com.projectseele.client.render;

import com.projectseele.entity.*;
import com.projectseele.network.*;
import net.minecraft.client.Minecraft;
import net.minecraft.nbt.*;
import org.joml.Quaternionf;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.util.*;

/** Retain the fully composed last live pose; the server persists the pilot's power-loss snapshot. */
final class EvaShutdownPoseR30
{
    private static final Map<EvaUnit01Entity,View> VIEWS=new WeakHashMap<>();
    static void resetEntityR31(EvaUnit01Entity eva){VIEWS.remove(eva);EvaCombatPoseR31.resetEntityR31(eva);CombatFeelR31.clear(eva);}
    private static final class View {CompoundTag live=new CompoundTag(),held=new CompoundTag(),entry=new CompoundTag();int mode,sentMode=-1;boolean localPilot;UUID localOwner;long sent=-1,released,traceTick=Long.MIN_VALUE,episodeStamp=Long.MIN_VALUE;}
    private static void invalidateForeignOwnerR45(EvaUnit01Entity eva,View view)
    {
        if(!view.localPilot)return;
        var player=Minecraft.getInstance().player;var actual=eva.getPilotEntity();
        if(player==null||!player.getUUID().equals(view.localOwner)
                ||actual!=null&&!actual.getUUID().equals(view.localOwner))
        {view.localPilot=false;view.localOwner=null;view.live=new CompoundTag();}
    }
    static CompoundTag retainedPoseForBounds(EvaUnit01Entity eva)
    {
        var view=VIEWS.get(eva);
        if(view!=null&&view.localPilot&&!view.held.isEmpty())return view.held;
        return EvaShutdownR30.pose(eva);
    }
    private static CompoundTag capture(BakedGeoModel model)
    {
        CompoundTag result=new CompoundTag();
        for(var bone:model.topLevelBones())captureActualBoneR45(bone,result);
        return result;
    }
    private static void captureActualBoneR45(software.bernie.geckolib.cache.object.GeoBone bone,CompoundTag result)
    {
        ListTag values=new ListTag();
        for(float value:new float[]{bone.getRotX(),bone.getRotY(),bone.getRotZ(),bone.getPosX(),bone.getPosY(),bone.getPosZ(),bone.getScaleX(),bone.getScaleY(),bone.getScaleZ()})values.add(FloatTag.valueOf(value));
        result.put(bone.getName(),values);
        for(var child:bone.getChildBones())captureActualBoneR45(child,result);
    }
    /** Cache the final composed frame even when PoseGraph takes an early shared/physics branch. No bone writes. */
    static void rememberFinalLiveR45(EvaUnit01Entity eva,BakedGeoModel model)
    {
        if(ShaderShadowPassR44.active())return;
        // The paired scene owns its final shutdown pose on the server. An old
        // field-driving cut must never override that authored scene result.
        if(eva.isFirstBattleActive()){VIEWS.remove(eva);return;}
        var view=VIEWS.computeIfAbsent(eva,e->new View());
        invalidateForeignOwnerR45(eva,view);
        if(EvaShutdownR30.retainsPoseR45(eva)&&com.projectseele.physics.CombatBodyDynamics.active(eva))
        {view.held=capture(model);view.entry=view.held.copy();view.localPilot=false;view.localOwner=null;return;}
        if(EvaShutdownR30.mode(eva)!=EvaShutdownR30.ACTIVE||!eva.isPoweredOn()||eva.isNervLogisticsLocked()
                ||eva.hasActiveCarrierMotion()||eva.isLaunchSequenceActive()||EvaAirTransportR31.active(eva)||eva.isFirstBattleActive())return;
        var player=Minecraft.getInstance().player;
        boolean ownsNow=player!=null&&com.projectseele.world.EvaPilotResolver.controlTarget(player)==eva&&eva.getPilotEntity()==player;
        // Passenger removal can arrive one frame before the shutdown mode.
        // localPilot identifies the owner of the cached frame. Do not replace
        // that owned frame with a still-ACTIVE but already unpiloted frame.
        if(view.localPilot&&!ownsNow&&eva.getPilotEntity()==null)
        {
            if(com.projectseele.visual.StanceContactR41Review.shutdownFrozenAckEnabledR45(eva))
            {var trace=new com.google.gson.JsonObject();trace.addProperty("cached_owner_retained",true);trace.addProperty("previous_live_bones",view.live.size());com.projectseele.visual.StanceContactR41Review.shutdownFrozenAckTraceR45(eva,"client_owned_cut_preserved_before_mode",trace);}
            return;
        }
        view.live=capture(model);
        view.localPilot=ownsNow;
        view.localOwner=ownsNow?player.getUUID():null;
    }
    static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity eva,BakedGeoModel model,float partial)
    {
        var view=VIEWS.computeIfAbsent(eva,e->new View());int mode=EvaShutdownR30.displayed(eva)?EvaShutdownR30.mode(eva):0;long now=System.nanoTime();
        invalidateForeignOwnerR45(eva,view);
        if(mode!=0)
        {
            var mc=Minecraft.getInstance();long stamp=EvaShutdownR30.since(eva);
            // A live shared-body branch can bypass apply(mode=0) after re-entry.
            // Identify each retained freeze by the actual server mode/epoch.
            if(view.mode==0||EvaShutdownR30.retainsPoseModeR45(mode)&&(view.mode!=mode||view.episodeStamp!=stamp))
            {
                view.entry=view.live.isEmpty()?EvaShutdownR30.origin(eva).copy():view.live.copy();
                view.held=EvaShutdownR30.retainsPoseModeR45(mode)&&!view.live.isEmpty()?view.live.copy():EvaShutdownR30.pose(eva).copy();
                view.episodeStamp=stamp;
            }
            long age=eva.level().getGameTime()-stamp;
            boolean ownedCut=EvaShutdownR30.retainsPoseModeR45(mode)&&view.localPilot&&!view.live.isEmpty();
            boolean localSnapshot=ownedCut&&mc.player!=null
                    &&(mode==EvaShutdownR30.EMPTY&&age>=0&&age<=20||mode==EvaShutdownR30.POWER_LOCK
                    &&com.projectseele.world.EvaPilotResolver.controlTarget(mc.player)==eva&&eva.getPilotEntity()==mc.player);
            if(com.projectseele.visual.StanceContactR41Review.shutdownFrozenAckEnabledR45(eva)&&view.traceTick!=eva.level().getGameTime())
            {
                view.traceTick=eva.level().getGameTime();var trace=new com.google.gson.JsonObject();trace.addProperty("local_pilot_cached",view.localPilot);trace.addProperty("local_snapshot_allowed",localSnapshot);trace.addProperty("client_player_uuid",mc.player==null?"none":mc.player.getStringUUID());trace.addProperty("controls_now",mc.player!=null&&com.projectseele.world.EvaPilotResolver.controlTarget(mc.player)==eva&&eva.getPilotEntity()==mc.player);trace.addProperty("live_bones",view.live.size());trace.addProperty("held_bones",view.held.size());trace.addProperty("entry_bones",view.entry.size());trace.addProperty("held_valid",EvaShutdownR30.valid(view.held));trace.addProperty("sent_stamp",view.sent);trace.addProperty("sent_mode",view.sentMode);
                com.projectseele.visual.StanceContactR41Review.shutdownFrozenAckTraceR45(eva,"client_before_snapshot_decision",trace);
            }
            if(localSnapshot&&(view.sent!=stamp||view.sentMode!=mode)&&!view.held.isEmpty())
            {
                if(com.projectseele.visual.StanceContactR41Review.shutdownFrozenAckEnabledR45(eva)){var trace=new com.google.gson.JsonObject();trace.addProperty("packet_entity_id",eva.getId());trace.addProperty("payload_bones",view.held.size());trace.addProperty("payload_valid",EvaShutdownR30.valid(view.held));trace.addProperty("payload_snbt",view.held.toString());com.projectseele.visual.StanceContactR41Review.shutdownFrozenAckTraceR45(eva,"client_actual_send_frozen_packet",trace);}
                SeeleNetwork.CHANNEL.sendToServer(new ServerboundEvaFrozenPoseR30(eva.getId(),view.held.copy()));view.sent=stamp;view.sentMode=mode;
            }
            // Drawing the owned cut and permission to transmit it are separate.
            // In particular, a temporarily negative client clock must not
            // replace the110-bone cut by the server's provisional base pose.
            if(!EvaShutdownR30.pose(eva).isEmpty()&&!ownedCut)view.held=EvaShutdownR30.pose(eva).copy();
            float blend=EvaShutdownR30.collapse(eva,partial);if(blend<1)write(model,view.entry,1);
            view.mode=mode;view.released=0;var written=write(model,view.held,blend);
            if(!EvaShutdownR30.retainsPoseModeR45(mode))
            {
                var pose=EvaBodyPose.neutralForTransportR32(eva);EvaShutdownR30.decode(capture(model),pose);
                com.projectseele.physics.CombatBodyDynamics.alignJoints(eva,pose);return PhysicalBodyRenderer.write(pose,model);
            }
            return written;
        }
        if(view.mode!=0){view.mode=0;view.released=now;}
        var result=EvaMotionEngineV2.BoneWrites.empty();
        if(view.released!=0&&!eva.isNervLogisticsLocked())
        {float weight=1-EvaDorsalMechanism.smooth((now-view.released)/300_000_000F);if(weight>0)result=write(model,view.held,weight);else view.released=0;}
        // The final frame is remembered by PoseGraph.finish, after every actual writer.
        return result;
    }
    private static EvaMotionEngineV2.BoneWrites write(BakedGeoModel model,CompoundTag tag,float w)
    {
        Set<String> names=new HashSet<>();for(String name:tag.getAllKeys())model.getBone(name).ifPresent(b->{
            var v=tag.getList(name,Tag.TAG_FLOAT);if(v.size()!=9)return;
            var q=new Quaternionf().rotationZYX(b.getRotZ(),b.getRotY(),b.getRotX()).slerp(new Quaternionf().rotationZYX(v.getFloat(2),v.getFloat(1),v.getFloat(0)),w);var r=EvaShutdownR30.euler(q);
            b.setRotX(r.x);b.setRotY(r.y);b.setRotZ(r.z);b.setPosX(b.getPosX()+(v.getFloat(3)-b.getPosX())*w);b.setPosY(b.getPosY()+(v.getFloat(4)-b.getPosY())*w);b.setPosZ(b.getPosZ()+(v.getFloat(5)-b.getPosZ())*w);
            b.setScaleX(b.getScaleX()+(v.getFloat(6)-b.getScaleX())*w);b.setScaleY(b.getScaleY()+(v.getFloat(7)-b.getScaleY())*w);b.setScaleZ(b.getScaleZ()+(v.getFloat(8)-b.getScaleZ())*w);names.add(name);
        });return new EvaMotionEngineV2.BoneWrites(Set.copyOf(names),Set.copyOf(names),"MOTION_ENGINE_LIVE_ACTION");
    }
    private EvaShutdownPoseR30() {}
}

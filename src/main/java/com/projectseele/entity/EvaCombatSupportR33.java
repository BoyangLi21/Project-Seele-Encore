package com.projectseele.entity;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.network.syncher.*;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import org.joml.Vector3f;
import org.joml.Quaternionf;

/** World-space support for a complete planted strike, shared by skin and hit tests. */
public final class EvaCombatSupportR33
{
    private record ReactionOrigin(long start,Vec3 position){}
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,ReactionOrigin> REACTIONS=new com.projectseele.util.WeakIdentityMap<>();
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,Vec3[]> TARGETS=new com.projectseele.util.WeakIdentityMap<>();
    private record FootFrame(long tick,Vec3[] feet){}
    private record ReleaseFrame(long signal,long start,Vec3[] feet){}
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,FootFrame> FINAL_FEET=new com.projectseele.util.WeakIdentityMap<>();
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,ReleaseFrame> CLIENT_RELEASES=new com.projectseele.util.WeakIdentityMap<>();
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,ListTag> CLOCKS=new com.projectseele.util.WeakIdentityMap<>();
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,CompoundTag> FLOOR_WITNESS=new com.projectseele.util.WeakIdentityMap<>();
    private static final class RenderClockR45
    {
        long frame; double serverTime,clientTime; float latestMove; boolean timedStop;
    }
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,RenderClockR45> RENDER_CLOCKS_R45=new com.projectseele.util.WeakIdentityMap<>();
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,com.google.gson.JsonObject> SIGNAL_REVIEW_R45=new com.projectseele.util.WeakIdentityMap<>();
    public static com.google.gson.JsonObject signalReviewR45(EvaUnit01Entity e)
    {
        var review=SIGNAL_REVIEW_R45.get(e);return review==null?null:review.deepCopy();
    }
    private static float witnessSignalR45(EvaUnit01Entity e,float partial,int channel,float fallback,float value,String source,
                                          CompoundTag first,CompoundTag last,float amount,boolean stationary)
    {
        if(com.projectseele.visual.BodyPoseLayersR40.ENABLED&&e.level().isClientSide)
        {
            var review=SIGNAL_REVIEW_R45.get(e);
            if(review==null){review=new com.google.gson.JsonObject();SIGNAL_REVIEW_R45.put(e,review);}
            var row=new com.google.gson.JsonObject();row.addProperty("source",source);row.addProperty("partial",partial);
            row.addProperty("fallback",fallback);row.addProperty("value",value);row.addProperty("stationary",stationary);
            if(first!=null){row.addProperty("first_tick",first.getLong("tick"));row.addProperty("last_tick",last.getLong("tick"));row.addProperty("amount",amount);}
            var clock=RENDER_CLOCKS_R45.get(e);if(clock!=null){row.addProperty("server_time",clock.serverTime);row.addProperty("client_time",clock.clientTime);}
            review.add(channel==4?"gait":channel==5?"move":"run",row);
        }
        return value;
    }
    private static final EntityDataAccessor<CompoundTag> CONTACTS=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.COMPOUND_TAG);
    private static final EntityDataAccessor<CompoundTag> PHASE_HISTORY_R45=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.COMPOUND_TAG);
    private static final EntityDataAccessor<Vector3f> DIRECTION=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.VECTOR3);
    public static boolean bootstrap(){return true;}
    public static void define(SynchedEntityData d){d.define(CONTACTS,new CompoundTag());d.define(PHASE_HISTORY_R45,new CompoundTag());d.define(DIRECTION,new Vector3f(0,0,1));}
    public static boolean ready(EvaUnit01Entity e)
    {
        var p=EvaGameplayMotionR32.profile(EvaGameplayMotionR32.variant(e));
        return p!=null&&p.has("combat_foundation")&&p.get("combat_foundation").getAsInt()>=33;
    }
    public static boolean strike(EvaUnit01Entity e){return !EvaGameplayMotionR32.activeGroundClip(e,0).isEmpty();}
    public static CompoundTag diagnosticR44(EvaUnit01Entity e)
    {
        var tag=e.getEntityData().get(CONTACTS).copy();var floor=FLOOR_WITNESS.get(e);if(floor!=null)tag.put("free_floor_r44",floor.copy());
        var release=CLIENT_RELEASES.get(e);if(release!=null)tag.putDouble("client_release_ticks",(FirstBattleSignals.clientFrameTime()-release.start())/50_000_000D);return tag;
    }
    public static float renderLocomotionSignalR44(EvaUnit01Entity e,float partial,int channel,float fallback)
    {
        if(!e.level().isClientSide
                ||e.hasLiveActionForRender(partial)&&!EvaGameplayMotionR32.movementMayComposeR45(e)
                ||e.isFirstBattleActive()||e.isPilotCrouching()||e.isPilotProne())
            return witnessSignalR45(e,partial,channel,fallback,fallback,"ineligible",null,null,0,false);
        // Releasing a planted foot must not also discard the gait clock.
        // Attacks and turning previously cleared CONTACTS, switching the
        // same moving legs between two differently delayed sample streams.
        var tag=e instanceof EvaPrototypeEntity?e.getEntityData().get(CONTACTS):e.getEntityData().get(PHASE_HISTORY_R45);
        if(!tag.contains("position_phase_r44",Tag.TAG_LIST))return witnessSignalR45(e,partial,channel,fallback,fallback,"no_history",null,null,0,false);
        var samples=tag.getList("position_phase_r44",Tag.TAG_COMPOUND);if(samples.isEmpty())return witnessSignalR45(e,partial,channel,fallback,fallback,"empty_history",null,null,0,false);
        var origin=e.getPosition(partial);CompoundTag first=samples.getCompound(samples.size()-1),last=first;float amount=1;double best=Double.POSITIVE_INFINITY;
        for(int i=0;i+1<samples.size();i++)
        {
            var a=samples.getCompound(i);var b=samples.getCompound(i+1);
            double dx=b.getDouble("x")-a.getDouble("x"),dz=b.getDouble("z")-a.getDouble("z"),length=dx*dx+dz*dz;
            if(length<1e-8)continue;
            double u=Mth.clamp(((origin.x-a.getDouble("x"))*dx+(origin.z-a.getDouble("z"))*dz)/length,0,1);
            double x=Mth.lerp(u,a.getDouble("x"),b.getDouble("x")),z=Mth.lerp(u,a.getDouble("z"),b.getDouble("z"));
            double distance=(origin.x-x)*(origin.x-x)+(origin.z-z)*(origin.z-z)+(samples.size()-i)*1e-10;
            if(distance<best){best=distance;first=a;last=b;amount=(float)u;}
        }
        // Every pair contains a phase, blend and the server origin from the
        // same tick. Sample that pair at the actual renderer origin instead
        // of advancing phase ahead of vanilla's three-tick position lerp.
        if(best>64&&Double.isFinite(best))return witnessSignalR45(e,partial,channel,fallback,fallback,"far_from_history",first,last,amount,false);
        boolean stationaryReview=false,timedStopReview=false;
        if(!(e instanceof EvaPrototypeEntity))
        {
            var newest=samples.getCompound(samples.size()-1);
            var prior=samples.getCompound(Math.max(0,samples.size()-2));
            double dx=newest.getDouble("x")-prior.getDouble("x"),dz=newest.getDouble("z")-prior.getDouble("z");
            double ox=origin.x-newest.getDouble("x"),oz=origin.z-newest.getDouble("z");
            boolean stationary=dx*dx+dz*dz<1e-8&&ox*ox+oz*oz<.0025;
            stationaryReview=stationary;
            double spatialTime=Mth.lerp((double)amount,(double)first.getLong("tick"),(double)last.getLong("tick"));
            long frame=FirstBattleSignals.clientFrameTime();double clientTime=(double)e.level().getGameTime()+partial;
            var clock=RENDER_CLOCKS_R45.get(e);
            float newestMove=newest.getFloat("move"),priorMove=prior.getFloat("move");
            // Start the stop timeline when the SERVER blend begins to fall,
            // before vanilla's position lerp reaches the final point. Near a
            // stop, several almost coincident spatial segments are ambiguous:
            // nearest-segment selection jumped four source ticks in one frame.
            // The already selected delayed timeline has that information.
            boolean resumed=clock!=null&&newestMove>clock.latestMove+1e-4F;
            boolean timedStop=!resumed&&(stationary||newestMove+1e-4F<priorMove
                    ||clock!=null&&clock.timedStop&&newestMove<.999F&&newestMove<=priorMove+1e-4F);
            if(clock==null)
            {
                clock=new RenderClockR45();clock.serverTime=spatialTime;clock.clientTime=clientTime;
                clock.frame=frame;clock.timedStop=timedStop;clock.latestMove=newestMove;RENDER_CLOCKS_R45.put(e,clock);
            }
            else if(clock.frame!=frame)
            {
                // A zero-length spatial segment still contains real timed
                // blend samples. Continue the SAME delayed render timeline
                // through them; switching to the latest packet clock skips
                // the first stopping poses on slower clients.
                double elapsed=clientTime-clock.clientTime;
                clock.serverTime=timedStop&&elapsed>=0&&elapsed<4
                        ?clock.serverTime+elapsed:spatialTime;
                clock.clientTime=clientTime;clock.frame=frame;clock.timedStop=timedStop;clock.latestMove=newestMove;
            }
            // All three channels must consume the SAME frame decision, and
            // renewed movement must leave stop mode even if its rising packet
            // was skipped and the next history already contains two full rows.
            timedStop=clock.timedStop;timedStopReview=timedStop;
            if(timedStop)
            {
                first=last=samples.getCompound(0);amount=0;
                for(int i=1;i<samples.size();i++)
                {
                    var candidate=samples.getCompound(i);
                    if(candidate.getLong("tick")>=clock.serverTime)
                    {
                        last=candidate;double duration=last.getLong("tick")-first.getLong("tick");
                        amount=duration<=0?0:(float)Mth.clamp((clock.serverTime-first.getLong("tick"))/duration,0,1);break;
                    }
                    first=last=candidate;amount=0;
                }
            }
        }
        String key=channel==4?"gait":channel==5?"move":"run";float a=first.getFloat(key),b=last.getFloat(key);
        float value;
        if(channel==4){float difference=b-a;difference-=Math.round(difference);value=a+difference*amount;}
        else value=Mth.lerp(amount,a,b);
        return witnessSignalR45(e,partial,channel,fallback,value,timedStopReview?"stop_timeline":"position_history",first,last,amount,stationaryReview);
    }
    private static void rememberClockR44(EvaUnit01Entity e)
    {
        var prior=CLOCKS.get(e);var samples=prior==null?new ListTag():prior.copy();var row=new CompoundTag();
        row.putLong("tick",e.level().getGameTime());row.putDouble("x",e.getX());row.putDouble("y",e.getY());row.putDouble("z",e.getZ());
        row.putFloat("gait",e.rifleGaitPhase(0));row.putFloat("run",e.rifleRunBlend(0));row.putFloat("move",e.rifleMoveBlend(0));
        if(!samples.isEmpty()&&samples.getCompound(samples.size()-1).getLong("tick")==e.level().getGameTime())samples.remove(samples.size()-1);
        samples.add(row);while(samples.size()>8)samples.remove(0);CLOCKS.put(e,samples);
        if(!(e instanceof EvaPrototypeEntity))
        {
            var history=new CompoundTag();
            if(e.getPilotEntity()!=null&&!e.isNervLogisticsLocked())history.put("position_phase_r44",samples.copy());
            if(!history.equals(e.getEntityData().get(PHASE_HISTORY_R45)))e.getEntityData().set(PHASE_HISTORY_R45,history);
        }
    }
    private static void attachClockR44(EvaUnit01Entity e,CompoundTag tag)
    {var samples=CLOCKS.get(e);if(samples!=null)tag.put("position_phase_r44",samples.copy());}
    public static void rememberFinalFeetR44(EvaUnit01Entity e,EvaBodyPose.Sample pose,float partial)
    {
        if(!EvaBodyPose.runtimeLocomotionR44(e)||e.rifleStanceLevel(partial)>.01F||!supported(e))return;
        // Preserve the preceding moving pose at a stop; replacing it with an
        // already-idle free leg would make the release itself jump backwards.
        if(!e.level().isClientSide&&!strike(e)&&e.rifleMoveBlend(partial)<=.05F)return;
        Vec3[] feet=new Vec3[2];int i=0;
        for(String side:new String[]{"l","r"})
        {
            var p=pose.matrix("foot_"+side).transformPosition(new Vector3f(pose.rig.get("foot_"+side).pivot()).add(toe(e,side)))
                    .mul(EvaScale.RENDER_SCALE).rotateY((180-e.getYRot())*Mth.DEG_TO_RAD);
            feet[i++]=(e.level().isClientSide?e.getPosition(partial):e.position()).add(p.x,p.y,p.z);
        }
        FINAL_FEET.put(e,new FootFrame(e.level().getGameTime(),feet));
    }
    public static void beginReleaseR44(EvaUnit01Entity e)
    {
        if(e.level().isClientSide||!EvaBodyPose.runtimeLocomotionR44(e))return;
        var old=e.getEntityData().get(CONTACTS);if(old.isEmpty()||old.contains("release"))return;
        var t=old.copy();t.putLong("release",e.level().getGameTime());t.putBoolean("locomotion_r44",false);
        var previous=FINAL_FEET.get(e);
        if(previous!=null&&e.level().getGameTime()-previous.tick()<=3)
            for(int i=0;i<2;i++)
            {
                String side=i==0?"l":"r";Vec3 point=previous.feet()[i];
                var floor=e.level().clip(new net.minecraft.world.level.ClipContext(point.add(0,4,0),point.add(0,-8,0),net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,e));
                if(floor.getType()!=net.minecraft.world.phys.HitResult.Type.BLOCK)continue;
                t.putDouble(side+"x",point.x);t.putDouble(side+"z",point.z);t.putDouble(side+"y",floor.getLocation().y);
                t.putDouble(side+"startY",point.y);t.putLong(side+"plant",e.level().getGameTime());t.putBoolean(side+"active",true);
            }
        attachClockR44(e,t);e.getEntityData().set(CONTACTS,t);
    }
    public static void preventFreeFootPenetrationR44(EvaUnit01Entity e,EvaBodyPose.Sample pose,float partial)
    {
        FLOOR_WITNESS.remove(e);
        // Terrain non-penetration is independent of the optional locomotion
        // foot-lock asset. Legacy clips and attacks use the same final soles.
        if(e.isExperimentalUnit()||!supported(e)||!EvaGameplayMotionR32.sharedWeapon(e)||e.rifleStanceLevel(partial)>.01F
                ||e.isFirstBattleActive()||e.isNervLogisticsLocked()||EvaShutdownR30.disabled(e)||CombatReactionsR36.active(e))return;
        var origin=e.level().isClientSide?e.getPosition(partial):e.position();var diagnostics=new CompoundTag();
        var profile=com.projectseele.physics.CombatBodyProfiles.get(e);
        for(String side:new String[]{"l","r"})
        {
            var low=EvaBodyPose.lowestRigidFootR44(e,pose,side);if(low==null)continue;
            var world=new Vector3f(low).mul(EvaScale.RENDER_SCALE).rotateY((180-e.getYRot())*Mth.DEG_TO_RAD).add((float)origin.x,(float)origin.y,(float)origin.z);
            diagnostics.putDouble(side+"before_y",world.y);
            // Normalizing a knee after support IK can move even a planted
            // sole below its actual surface. Preserve its X/Z and orientation;
            // project only the penetrating leg, without lifting the assembly.
            if(world.y>=origin.y+.025)continue;
            var point=new Vec3(world.x,world.y,world.z);
            var hit=e.level().clip(new net.minecraft.world.level.ClipContext(point.add(0,4,0),point.add(0,-8,0),
                    net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,e));
            if(hit.getType()!=net.minecraft.world.phys.HitResult.Type.BLOCK||world.y>=hit.getLocation().y+.015)continue;
            String name="foot_"+side;var matrix=pose.matrix(name);var orientation=matrix.getUnnormalizedRotation(new Quaternionf()).normalize();
            var target=matrix.transformPosition(new Vector3f(pose.rig.get(name).pivot()));target.y+=(float)((hit.getLocation().y+.02-world.y)/EvaScale.RENDER_SCALE);
            com.projectseele.physics.AnatomicalLimbConstraints.reachFoot(pose,profile,side,target,orientation);
            var finalLow=EvaBodyPose.lowestRigidFootR44(e,pose,side);diagnostics.putDouble(side+"after_y",origin.y+finalLow.y*EvaScale.RENDER_SCALE);
            diagnostics.putDouble(side+"ground_y",hit.getLocation().y);
        }
        FLOOR_WITNESS.put(e,diagnostics);
    }
    public static float gaitWeight(EvaUnit01Entity e,float partial)
    {
        if(!ready(e))return 0;
        // R47 field travel keeps the base walk/run in the actual leg owner.
        // Its clock cannot still use combat-advance stride/contact timing.
        if(!(e instanceof EvaPrototypeEntity)&&!e.isBerserk()
                &&(!EvaGameplayMotionR32.sharedWeapon(e)
                   ||(e.pilotLocomotionRequestedR45()||e.rifleMoveBlend(partial)>.05F)
                     &&e.rifleStanceLevel(partial)<.01F))return 0;
        float low=Mth.clamp(e.rifleStanceLevel(partial),0,1),run=Mth.clamp(e.rifleRunBlend(partial),0,1);
        low=low*low*(3-2*low);run=run*run*(3-2*run);
        return EvaGameplayMotionR32.guardWeight(e)*(1-low)*(1-run);
    }
    public static float stride(EvaUnit01Entity e,double dx,double dz,float fallback)
    {
        if(!ready(e))return fallback;
        Vec3 f=e.getForward();float front=(float)(dx*f.x+dz*f.z),right=(float)(dx*f.z-dz*f.x);
        Vector3f v=new Vector3f(right,0,front);if(v.lengthSquared()<1e-6)return fallback;v.normalize();
        e.getEntityData().set(DIRECTION,new Vector3f(e.getEntityData().get(DIRECTION)).lerp(v,.25F));
        var clips=EvaGameplayMotionR32.profile(EvaGameplayMotionR32.variant(e)).getAsJsonObject("clips");
        var foreClip=clips.getAsJsonObject(front>=0?"r32_advance":"r32_retreat");
        var sideClip=clips.getAsJsonObject(right>=0?"r32_right":"r32_left");
        if(foreClip==null||sideClip==null)return fallback;
        float lateral=Math.abs(right)/Math.max(.001F,Math.abs(front)+Math.abs(right));
        float supported=Mth.lerp(lateral,foreClip.get("stride_blocks").getAsFloat(),sideClip.get("stride_blocks").getAsFloat());
        return Mth.lerp(gaitWeight(e,1),fallback,supported);
    }
    public static EvaBodyPose.Sample locomotion(EvaUnit01Entity e,EvaBodyPose.Sample guard,float partial)
    {
        if(!ready(e)||e.rifleMoveBlend(partial)<.01F)return guard;
        var dir=e.getEntityData().get(DIRECTION);float phase=e.rifleGaitPhase(partial);phase-=Mth.floor(phase);
        var fore=EvaBodyPose.gameplayClip(e,dir.z>=0?"advance":"retreat",phase);
        var side=EvaBodyPose.gameplayClip(e,dir.x>=0?"right":"left",phase);
        float w=Math.abs(dir.x)/Math.max(.001F,Math.abs(dir.x)+Math.abs(dir.z));
        return EvaBodyPose.blend(guard,EvaBodyPose.blend(fore,side,w),e.rifleMoveBlend(partial)*Math.min(1,Math.abs(dir.x)+Math.abs(dir.z)));
    }
    public static EvaBodyPose.Sample reactionStep(EvaUnit01Entity e,CombatFeelR31.Beat hit,float partial)
    {
        var start=REACTIONS.get(e);
        if(start==null||start.start!=hit.start()){start=new ReactionOrigin(hit.start(),e.position());REACTIONS.put(e,start);}
        Vec3 forward=e.getForward(),right=new Vec3(forward.z,0,-forward.x);
        double f=hit.direction().dot(forward),s=hit.direction().dot(right);
        String name=Math.abs(f)>=Math.abs(s)?f>=0?"advance":"retreat":s>=0?"right":"left";
        var clip=EvaGameplayMotionR32.profile(EvaGameplayMotionR32.variant(e)).getAsJsonObject("clips").getAsJsonObject("r32_"+name);
        double distance=(e.level().isClientSide?e.getPosition(partial):e.position()).subtract(start.position).horizontalDistance();
        return EvaBodyPose.gameplayClip(e,name,(float)Math.min(.48,distance/clip.get("stride_blocks").getAsFloat()));
    }
    public static Vector3f toe(EvaUnit01Entity e,String side)
    {
        var a=EvaGameplayMotionR32.profile(EvaGameplayMotionR32.variant(e)).getAsJsonObject("support_toes").getAsJsonArray(side);
        return new Vector3f(a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat());
    }
    public static void capture(EvaUnit01Entity e,EvaBodyPose.Sample pose)
    {
        if(e.level().isClientSide||!ready(e)||!supported(e)||e.isPilotCrouching()||e.isPilotProne())return;
        if(!(e instanceof EvaPrototypeEntity)&&(e.pilotLocomotionRequestedR45()||e.rifleMoveBlend(0)>.08F))
        {release(e);return;}
        CompoundTag t=new CompoundTag();t.putFloat("yaw",e.getYRot());t.putLong("plant",e.level().getGameTime());t.putInt("weapon",e.getWeapon());
        for(String s:new String[]{"l","r"})
        {
            String n="foot_"+s;Vector3f p=pose.matrix(n).transformPosition(new Vector3f(pose.rig.get(n).pivot()).add(toe(e,s)))
                    .mul(EvaScale.RENDER_SCALE).rotateY((180-e.getYRot())*Mth.DEG_TO_RAD);
            Vec3 w=e.position().add(p.x,p.y,p.z);
            var floor=e.level().clip(new net.minecraft.world.level.ClipContext(w.add(0,5,0),w.add(0,-8,0),
                    net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,e));
            if(floor.getType()!=net.minecraft.world.phys.HitResult.Type.BLOCK)
            {e.getEntityData().set(CONTACTS,new CompoundTag());return;}
            t.putDouble(s+"x",w.x);t.putDouble(s+"y",floor.getLocation().y);t.putDouble(s+"z",w.z);t.putDouble(s+"startY",Math.max(w.y,floor.getLocation().y));
            t.putBoolean(s+"active",true);t.putLong(s+"plant",e.level().getGameTime());
        }
        e.getEntityData().set(CONTACTS,t);
    }
    private static Vec3 plantTarget(EvaUnit01Entity e,CompoundTag t,String side,float partial,float soleOffset)
    {
        long since=EvaGameplayMotionR32.directed(e)?t.getLong(side+"plant"):t.getLong("plant");
        float step=Mth.clamp((e.level().getGameTime()-since+partial)/4F,0,1),u=step*step*step*(10+step*(-15+6*step));
        double ground=t.getDouble(side+"y")+soleOffset*EvaScale.RENDER_SCALE;
        double y=Mth.lerp(u,Math.max(t.getDouble(side+"startY"),ground),ground);
        return new Vec3(t.getDouble(side+"x"),y,t.getDouble(side+"z"));
    }
    public static Vec3 anchor(EvaUnit01Entity e,String side,float partial)
    {var t=e.getEntityData().get(CONTACTS);var targets=TARGETS.get(e);return t.isEmpty()||targets==null?null:targets[side.equals("l")?0:1];}
    private static boolean supported(EvaUnit01Entity e)
    {return e.onGround()&&!e.isVisuallyAirborneForRender()&&EvaGameplayMotionR32.airAge(e,0)<0;}
    public static void release(EvaUnit01Entity e)
    {if(!e.level().isClientSide)e.getEntityData().set(CONTACTS,new CompoundTag());TARGETS.remove(e);CLIENT_RELEASES.remove(e);}
    public static void tick(EvaUnit01Entity e)
    {
        if(e.level().isClientSide||!ready(e))return;
        // Packet/position timing also belongs to the preserved legacy clips.
        // Gating the history on a new foot-lock asset contract left those
        // clips on bursty packet clocks, skipping several gait poses at once.
        // This records timing only; it does not enable planted-foot IK.
        if(!(e instanceof EvaPrototypeEntity)||EvaBodyPose.runtimeLocomotionR44(e))rememberClockR44(e);
        boolean locomotion=EvaBodyPose.runtimeLocomotionR44(e)&&EvaGameplayMotionR32.sharedWeapon(e)
                &&e.getPilotEntity()!=null&&supported(e)&&!strike(e)&&e.rifleMoveBlend(0)>.05F&&e.rifleStanceLevel(0)<.01F
                &&!e.isNervLogisticsLocked()&&!e.isFirstBattleActive()&&!EvaShutdownR30.disabled(e)&&!CombatReactionsR36.active(e);
        if(locomotion){tickLocomotionR44(e);return;}
        if(e.getEntityData().get(CONTACTS).getBoolean("locomotion_r44"))beginReleaseR44(e);
        var beat=CombatFeelR31.beat(e);boolean fallen=beat!=null&&(beat.kind()==CombatFeelR31.DOWN||beat.kind()==CombatFeelR31.THROWN);
        boolean release=!supported(e)||e.isNervLogisticsLocked()||e.isFirstBattleActive()||EvaShutdownR30.disabled(e)
                ||!EvaGameplayMotionR32.sharedWeapon(e)||e.isPilotCrouching()||e.isPilotProne()||fallen||!strike(e)&&e.rifleMoveBlend(1)>.18F;
        if(!(e instanceof EvaPrototypeEntity))
        {
            var anchors=e.getEntityData().get(CONTACTS);
            release|=e.rifleMoveBlend(1)>.08F||!anchors.isEmpty()
                    &&Math.abs(Mth.wrapDegrees(EvaAirTransportR31.frameYaw(e,0)-anchors.getFloat("yaw")))>12;
        }
        if(release&&!e.getEntityData().get(CONTACTS).isEmpty())e.getEntityData().set(CONTACTS,new CompoundTag());
        var t=e.getEntityData().get(CONTACTS);
        if(t.contains("release")&&!strike(e))
        {
            if(e.level().getGameTime()-t.getLong("release")>=8)release(e);
            else{var updated=t.copy();attachClockR44(e,updated);e.getEntityData().set(CONTACTS,updated);}
            return;
        }
        if(EvaGameplayMotionR32.directed(e)&&strike(e)&&!t.isEmpty())
        {
            var updated=t.copy();boolean changed=false;
            for(String side:new String[]{"l","r"})
            {
                boolean plant=EvaGameplayMotionR32.planted(e,side,0);
                if(plant==t.getBoolean(side+"active"))continue;
                updated.putBoolean(side+"active",plant);changed=true;
                if(plant)
                {
                    var pose=EvaBodyPose.sample(e,0);String n="foot_"+side;
                    var point=pose.matrix(n).transformPosition(new Vector3f(pose.rig.get(n).pivot()).add(toe(e,side))).mul(EvaScale.RENDER_SCALE).rotateY((180-e.getYRot())*Mth.DEG_TO_RAD);
                    var world=e.position().add(point.x,point.y,point.z);
                    var floor=e.level().clip(new net.minecraft.world.level.ClipContext(world.add(0,6,0),world.add(0,-10,0),net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,e));
                    if(floor.getType()==net.minecraft.world.phys.HitResult.Type.BLOCK)
                    {
                        updated.putDouble(side+"x",world.x);updated.putDouble(side+"y",floor.getLocation().y);updated.putDouble(side+"z",world.z);
                        updated.putDouble(side+"startY",world.y);updated.putLong(side+"plant",e.level().getGameTime());
                        CombatFoleyR36.step(e,new Vec3(world.x,floor.getLocation().y,world.z),false,1.1F);
                    }
                    else updated.putBoolean(side+"active",false);
                }
            }
            if(changed){e.getEntityData().set(CONTACTS,updated);t=updated;}
        }
        if(!t.isEmpty()&&!strike(e))
        {
            if(!t.contains("release")&&Math.abs(Mth.wrapDegrees(e.getYRot()-t.getFloat("yaw")))>35)
            {t=t.copy();t.putLong("release",e.level().getGameTime());e.getEntityData().set(CONTACTS,t);}
            if(t.contains("release")&&e.level().getGameTime()-t.getLong("release")>=8)e.getEntityData().set(CONTACTS,new CompoundTag());
        }
    }
    private static void tickLocomotionR44(EvaUnit01Entity e)
    {
        var t=e.getEntityData().get(CONTACTS);
        if(t.isEmpty()||!t.getBoolean("locomotion_r44")||t.contains("release")||Math.abs(Mth.wrapDegrees(e.getYRot()-t.getFloat("yaw")))>20)
        {
            release(e);capture(e,EvaBodyPose.sample(e,0));t=e.getEntityData().get(CONTACTS);
            if(t.isEmpty())return;t=t.copy();t.putBoolean("locomotion_r44",true);
            for(String side:new String[]{"l","r"})t.putBoolean(side+"active",false);
            e.getEntityData().set(CONTACTS,t);
        }
        var updated=t.copy();boolean changed=false;
        for(String side:new String[]{"l","r"})
        {
            boolean planted=EvaBodyPose.locomotionPlantedR44(e,side,0);
            if(planted==t.getBoolean(side+"active"))continue;
            changed=true;updated.putBoolean(side+"active",false);e.getEntityData().set(CONTACTS,updated.copy());
            if(planted)
            {
                // Capture the current actual pose with the old support on the
                // other side retained. This world anchor is sent to the client,
                // so position prediction and gait interpolation cannot drag it.
                var pose=EvaBodyPose.sample(e,0);String name="foot_"+side;
                var point=pose.matrix(name).transformPosition(new Vector3f(pose.rig.get(name).pivot()).add(toe(e,side)))
                        .mul(EvaScale.RENDER_SCALE).rotateY((180-e.getYRot())*Mth.DEG_TO_RAD);
                var world=e.position().add(point.x,point.y,point.z);
                var floor=e.level().clip(new net.minecraft.world.level.ClipContext(world.add(0,5,0),world.add(0,-8,0),
                        net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,e));
                if(floor.getType()==net.minecraft.world.phys.HitResult.Type.BLOCK)
                {
                    updated.putDouble(side+"x",world.x);updated.putDouble(side+"y",floor.getLocation().y);updated.putDouble(side+"z",world.z);
                    updated.putDouble(side+"startY",world.y);updated.putLong(side+"plant",e.level().getGameTime());updated.putBoolean(side+"active",true);
                }
            }
        }
        attachClockR44(e,updated);e.getEntityData().set(CONTACTS,updated);
    }
    public static void apply(EvaUnit01Entity e,EvaBodyPose.Sample p,float partial)
    {
        if(!(e instanceof EvaPrototypeEntity)&&e.rifleMoveBlend(partial)>.08F)
        {TARGETS.remove(e);CLIENT_RELEASES.remove(e);return;}
        TARGETS.remove(e);
        if(CombatReactionsR36.active(e))return;
        if(!ready(e)||!supported(e)||!EvaGameplayMotionR32.owns(e,partial)||e.isNervLogisticsLocked()||EvaShutdownR30.disabled(e))return;
        var beat=CombatFeelR31.beat(e);if(beat!=null&&(beat.kind()==CombatFeelR31.DOWN||beat.kind()==CombatFeelR31.THROWN))return;
        var t=e.getEntityData().get(CONTACTS);if(t.isEmpty()||t.getInt("weapon")!=e.getWeapon())return;
        if(!t.contains("release"))CLIENT_RELEASES.remove(e);
        else if(e.level().isClientSide)
        {
            var previous=CLIENT_RELEASES.get(e);var feet=FINAL_FEET.get(e);
            if((previous==null||previous.signal()!=t.getLong("release"))&&feet!=null&&e.level().getGameTime()-feet.tick()<=3)
                CLIENT_RELEASES.put(e,new ReleaseFrame(t.getLong("release"),FirstBattleSignals.clientFrameTime(),feet.feet()));
        }
        var origin=e.level().isClientSide?e.getPosition(partial):e.position();
        String[] sides={"l","r"};Vector3f[] targets=new Vector3f[2];Quaternionf[] orientations=new Quaternionf[2];Vec3[] worldTargets=new Vec3[2];
        boolean[] supportActive=new boolean[2];
        for(int i=0;i<2;i++)supportActive[i]=e.level().isClientSide&&t.getBoolean("locomotion_r44")&&!t.contains("release")
                ?EvaBodyPose.locomotionPlantedR44(e,sides[i],partial):t.getBoolean(sides[i]+"active");
        for(int i=0;i<2;i++)
        {
            String s=sides[i];
            String foot="foot_"+s;var orientation=p.matrix(foot).getUnnormalizedRotation(new Quaternionf());
            if(EvaGameplayMotionR32.directed(e)&&!supportActive[i])
            {
                targets[i]=point(p,foot);orientations[i]=orientation;continue;
            }
            // A boot rolls on its real sole, not on an abstract marker floating
            // inside the mesh. Keep X/Z planted while its support patch changes.
            var planted=plantTarget(e,t,s,partial,EvaBodyPose.soleBelowToeR33(e,s,orientation,toe(e,s)));worldTargets[i]=planted;
            var target=new Vector3f((float)(planted.x-origin.x),(float)(planted.y-origin.y),(float)(planted.z-origin.z))
                    .rotateY(-(180-EvaAirTransportR31.frameYaw(e,partial))*Mth.DEG_TO_RAD).div(EvaScale.RENDER_SCALE);
            if(t.contains("release"))
            {
                var release=CLIENT_RELEASES.get(e);
                float ticks=release==null?e.level().getGameTime()-t.getLong("release")+partial
                        :(FirstBattleSignals.clientFrameTime()-release.start())/50_000_000F;
                if(release!=null)
                {
                    var start=release.feet()[i];target.set((float)(start.x-origin.x),(float)(start.y-origin.y),(float)(start.z-origin.z))
                            .rotateY(-(180-EvaAirTransportR31.frameYaw(e,partial))*Mth.DEG_TO_RAD).div(EvaScale.RENDER_SCALE);
                }
                float step=Mth.clamp((ticks-i*4)/4F,0,1);
                float u=step*step*step*(10+step*(-15+6*step));
                var free=p.matrix(foot).transformPosition(new Vector3f(p.rig.get(foot).pivot()).add(toe(e,s)));
                target.lerp(free,u).add(0,(float)Math.sin(step*Math.PI)*.25F,0);
                var world=new Vector3f(target).mul(EvaScale.RENDER_SCALE).rotateY((180-EvaAirTransportR31.frameYaw(e,partial))*Mth.DEG_TO_RAD);
                worldTargets[i]=origin.add(world.x,world.y,world.z);
            }
            target.sub(orientation.transform(toe(e,s)));
            targets[i]=target;orientations[i]=orientation;
        }
        // A moving entry stance or an actual hit can differ from the authored
        // stance. Put the pelvis inside BOTH legs' reachable volumes before
        // solving either knee; otherwise the second foot can never reach its
        // support point and the visible sole silently slides several metres.
        for(int pass=0;pass<12;pass++)for(int i=0;i<2;i++)
        {
            if(EvaGameplayMotionR32.directed(e)&&!supportActive[i])continue;
            String s=sides[i],a="leg_"+s,c="foot_"+s;Vector3f joint=knee(p,s);
            float reach=(joint.distance(p.rig.get(a).pivot())+joint.distance(p.rig.get(c).pivot()))*.997F;
            Vector3f delta=point(p,a).sub(targets[i]);float distance=delta.length();
            if(distance>reach){p.positions.get("root").sub(delta.mul(1-reach/distance));p.dirty();}
        }
        var profile=com.projectseele.physics.CombatBodyProfiles.get(e);
        for(int i=0;i<2;i++)if(!EvaGameplayMotionR32.directed(e)||supportActive[i])
            com.projectseele.physics.AnatomicalLimbConstraints.reachFoot(p,profile,sides[i],targets[i],orientations[i]);
        TARGETS.put(e,worldTargets);
    }
    private static Vector3f point(EvaBodyPose.Sample p,String n){return p.matrix(n).transformPosition(new Vector3f(p.rig.get(n).pivot()));}
    private static Vector3f knee(EvaBodyPose.Sample p,String side)
    {String marker="r30_knee_socket_"+side;return p.rig.containsKey(marker)?new Vector3f(p.rig.get(marker).pivot()):new Vector3f(p.rig.get("shin_"+side).pivot()).add(0,11.4F/16,0);}
    private EvaCombatSupportR33(){}
}

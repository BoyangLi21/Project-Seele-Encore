package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.entity.*;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;
import java.util.*;

/** Opt-in real-input stance and stationary-target contact regression. */
public final class StanceContactR41Review
{
    public static final boolean ENABLED=CombatR31Review.ENABLED&&Boolean.getBoolean("projectseele.r41StanceContacts");
    public static final boolean ARTICULATION=ENABLED&&Boolean.getBoolean("projectseele.r42Locomotion");
    public static final boolean GAIT_R43=ARTICULATION&&Boolean.getBoolean("projectseele.r43Gait");
    private static final boolean POSE_ONLY=Boolean.getBoolean("projectseele.r41PoseOnly");
    private static final JsonArray EVENTS=new JsonArray(),POSES=new JsonArray(),CONTACTS=new JsonArray();
    private static final Map<String,Quaternionf> PREVIOUS=new HashMap<>();
    private static float maxRotation,healthBefore;
    private static Vec3 crawlStart;
    private static double crawlDistance;
    private static int poseSamples,contactCase=-1,caseStarted;
    private static int weaponActionFrames;
    private static final boolean WEAPON_ACTIONS=Boolean.getBoolean("projectseele.r45WeaponActionReview");
    private static final boolean HANDLING=Boolean.getBoolean("projectseele.weaponHandlingReviewR45");
    private static int handlingCases;
    private static boolean strikeStarted,passed=true;
    private static final double[] RANGES={12,18,23,23,16,39};
    private static final int[] MODES={SachielStrike.SHOVE,SachielStrike.JAB,SachielStrike.HOOK,SachielStrike.OVERHEAD,SachielStrike.STOMP,SachielStrike.PILE};
    public static void sound(EvaUnit01Entity eva,String name,Vec3 at)
    {
        if(!ENABLED||!CombatR31Review.ownsFixture(eva))return;
        JsonObject row=new JsonObject();row.addProperty("event",name);row.addProperty("tick",CombatR31Review.stageTicks);
        row.addProperty("stance",eva.rifleStanceLevel(0));row.addProperty("x",at.x);row.addProperty("y",at.y);row.addProperty("z",at.z);EVENTS.add(row);
    }
    public static final boolean FIELD_INPUT_R45=ENABLED&&Boolean.getBoolean("projectseele.r45FieldInputReview");
    public static volatile boolean fieldRestoreInputsR45,fieldInputsRestoredR45;
    private static final String[] FIELD_NAMES_R45={"evade_forward","evade_back","evade_left","evade_right","roll_forward"};
    private static final JsonArray FIELD_CASES_R45=new JsonArray(),FIELD_SAMPLES_R45=new JsonArray();
    private static UUID fieldEvaR45,fieldPilotR45;
    private static int fieldCaseR45,fieldPhaseR45,fieldClockR45,fieldDurationR45,fieldTicksR45;
    private static float fieldMaxPhaseR45;
    private static Vec3 fieldBeforeKeyR45,fieldStartR45,fieldExpectedR45,fieldIdleR45,fieldDirectionR45,fieldFullR45;
    private static boolean fieldSeenR45;
    private static boolean fieldInputR45(EvaUnit01Entity eva,ServerPlayer pilot,int tick)
    {
        if(fieldEvaR45==null)
        {
            if(pilot instanceof net.minecraftforge.common.util.FakePlayer||!CombatR31Review.ownsFixture(eva)||eva.isExperimentalUnit())throw new IllegalStateException("Field requires real client and original NERV fixture");
            fieldEvaR45=eva.getUUID();fieldPilotR45=pilot.getUUID();CombatR31Review.arrangeR41(-180);
            if(!eva.selectMotionLabWeapon(EvaUnit01Entity.WEAPON_FISTS))throw new IllegalStateException("Field fists rejected");
        }
        if(!fieldEvaR45.equals(eva.getUUID())||!fieldPilotR45.equals(pilot.getUUID())||eva.getPilotEntity()!=pilot)throw new IllegalStateException("Field actor/pilot changed");
        CombatR31Review.forward=CombatR31Review.strafe=0;CombatR31Review.sprint=CombatR31Review.jump=false;
        if(fieldCaseR45==5){fieldRestoreInputsR45=true;if(++fieldClockR45>80)throw new IllegalStateException("Field input restore timeout");return fieldInputsRestoredR45;}
        if(++fieldClockR45>fieldDurationR45+180)throw new IllegalStateException("Field timeout case="+fieldCaseR45+" phase="+fieldPhaseR45);
        var row=new JsonObject();row.addProperty("case",fieldCaseR45);row.addProperty("tick",tick);row.addProperty("actual_active",EvaFieldActionsR45.active(eva));row.addProperty("actual_clip",EvaFieldActionsR45.clip(eva));row.addProperty("actual_phase",EvaFieldActionsR45.progress(eva,0));row.addProperty("position",eva.position().toString());row.addProperty("ground",eva.onGround());FIELD_SAMPLES_R45.add(row);
        if(fieldPhaseR45==0)
        {
            if(EvaFieldActionsR45.active(eva)||eva.hasLiveActionForRender(0)||!eva.onGround()||eva.rifleStanceLevel(0)>.01F||eva.isPilotSprinting())return false;
            var profile=EvaGameplayMotionR32.profile(eva.getUnitVariant());String name="r32_"+FIELD_NAMES_R45[fieldCaseR45];
            if(profile==null||!profile.getAsJsonObject("clips").has(name)||!EvaBodyPose.combatCaptureReadyR31(eva,name))throw new IllegalStateException("Actual Field clip missing: "+name);
            fieldDurationR45=(int)Math.ceil(profile.getAsJsonObject("clips").getAsJsonObject(name).get("source_duration_seconds").getAsDouble()*20);
            fieldSeenR45=false;fieldTicksR45=0;fieldMaxPhaseR45=0;fieldPhaseR45=1;fieldClockR45=0;return false;
        }
        if(fieldPhaseR45==1)
        {
            CombatR31Review.forward=fieldCaseR45==0||fieldCaseR45==4?1:fieldCaseR45==1?-1:0;CombatR31Review.strafe=fieldCaseR45==2?1:fieldCaseR45==3?-1:0;CombatR31Review.sprint=fieldCaseR45==4;
            if(fieldClockR45==3){fieldBeforeKeyR45=eva.position();CombatR31Review.inputR42(10);fieldPhaseR45=2;fieldClockR45=0;}return false;
        }
        if(fieldPhaseR45==2)
        {
            // Keep the real direction held until the server acknowledges the action; renderer latency must not erase the C direction.
            if(!fieldSeenR45&&!EvaFieldActionsR45.active(eva))
            {CombatR31Review.forward=fieldCaseR45==0||fieldCaseR45==4?1:fieldCaseR45==1?-1:0;CombatR31Review.strafe=fieldCaseR45==2?1:fieldCaseR45==3?-1:0;CombatR31Review.sprint=fieldCaseR45==4;}
            if(EvaFieldActionsR45.active(eva))
            {
                if(!FIELD_NAMES_R45[fieldCaseR45].equals(EvaFieldActionsR45.clip(eva)))throw new IllegalStateException("C actual clip differs");
                float phase=EvaFieldActionsR45.progress(eva,0);if(phase+1e-5F<fieldMaxPhaseR45)throw new IllegalStateException("C actual phase went backwards");fieldMaxPhaseR45=Math.max(fieldMaxPhaseR45,phase);fieldTicksR45++;
                if(!fieldSeenR45)
                {
                    fieldSeenR45=true;fieldStartR45=eva.position();var points=EvaGameplayMotionR32.profile(eva.getUnitVariant()).getAsJsonObject("clips").getAsJsonObject("r32_"+FIELD_NAMES_R45[fieldCaseR45]).getAsJsonArray("trajectory_m");
                    float at=phase*(points.size()-1);int a=(int)at,b=Math.min(a+1,points.size()-1);var one=points.get(a).getAsJsonArray();var two=points.get(b).getAsJsonArray();var end=points.get(points.size()-1).getAsJsonArray();
                    double x=end.get(0).getAsDouble()-net.minecraft.util.Mth.lerp(at-a,one.get(0).getAsDouble(),two.get(0).getAsDouble()),z=end.get(2).getAsDouble()-net.minecraft.util.Mth.lerp(at-a,one.get(2).getAsDouble(),two.get(2).getAsDouble());
                    Vec3 forward=eva.getForward().multiply(1,0,1).normalize(),left=new Vec3(0,1,0).cross(forward);double scale=112.0D*EvaScale.RENDER_SCALE/16;fieldExpectedR45=left.scale(x*scale).add(forward.scale(-z*scale));
                    fieldDirectionR45=fieldCaseR45==2?left:fieldCaseR45==3?left.scale(-1):fieldCaseR45==1?forward.scale(-1):forward;
                    var begin=points.get(0).getAsJsonArray();fieldFullR45=left.scale((end.get(0).getAsDouble()-begin.get(0).getAsDouble())*scale).add(forward.scale(-(end.get(2).getAsDouble()-begin.get(2).getAsDouble())*scale));
                    if(fieldExpectedR45.horizontalDistanceSqr()<1e-8)throw new IllegalStateException("C actual source has no remaining travel");
                }
                if(phase>=.2F&&phase<.3F||phase>=.45F&&phase<.55F||phase>=.7F&&phase<.8F)
                    CombatR31Review.photo="r45_field_"+eva.getUnitVariant()+"_"+FIELD_NAMES_R45[fieldCaseR45]+"_"+(phase<.3F?20:phase<.55F?45:70);
                return false;
            }
            if(!fieldSeenR45)return false;
            Vec3 delta=eva.position().subtract(fieldStartR45);
            if(fieldTicksR45<2||fieldMaxPhaseR45<1-1.5F/fieldDurationR45||delta.dot(fieldDirectionR45)<=0||delta.subtract(fieldExpectedR45).horizontalDistance()>.05)throw new IllegalStateException("C actual root/phase differs: "+FIELD_NAMES_R45[fieldCaseR45]+" actual="+delta+" expected="+fieldExpectedR45);
            fieldIdleR45=eva.position();fieldPhaseR45=3;fieldClockR45=0;return false;
        }
        if(EvaFieldActionsR45.active(eva)||eva.hasLiveActionForRender(0)||eva.getOrdinaryAttackStage()>=0||eva.isHeavyMotionActive()||eva.getKnifeMotionType(0)>=0||EvaCombatR31.active(eva)||EvaWeaponHandlingR45.active(eva)||eva.isPilotCrouching()||eva.isPilotProne()||eva.getWeapon()!=EvaUnit01Entity.WEAPON_FISTS||EvaShutdownR30.disabled(eva))throw new IllegalStateException("C exit retained another action/stance/weapon owner");
        if(fieldClockR45<12||eva.isPilotSprinting())return false;
        if(eva.position().subtract(fieldIdleR45).horizontalDistance()>.05)throw new IllegalStateException("C completion retained root travel");
        var result=new JsonObject();result.addProperty("case",FIELD_NAMES_R45[fieldCaseR45]);result.addProperty("passed",true);result.addProperty("actual_active_ticks",fieldTicksR45);result.addProperty("max_actual_phase",fieldMaxPhaseR45);result.addProperty("root_before_key",fieldBeforeKeyR45.toString());result.addProperty("first_active_root",fieldStartR45.toString());result.addProperty("root_after",eva.position().toString());result.addProperty("expected_remaining_delta",fieldExpectedR45.toString());result.addProperty("full_source_world_delta",fieldFullR45.toString());result.addProperty("full_source_world_distance",fieldFullR45.horizontalDistance());result.addProperty("camera_direction",fieldDirectionR45.toString());result.addProperty("exit_no_residual",true);FIELD_CASES_R45.add(result);fieldCaseR45++;fieldPhaseR45=fieldClockR45=0;return false;
    }

    public static final boolean SHUTDOWN_LIFECYCLE=ENABLED&&Boolean.getBoolean("projectseele.r45ShutdownLifecycleReview");
    public static volatile int shutdownPhaseR45,shutdownEmptyFramesR45,shutdownPowerFramesR45,shutdownDownFramesR45;
    public static volatile UUID shutdownPilotR45;
    public static volatile boolean shutdownExitKeyR45,shutdownReboardKeyR45,shutdownReleasedR45,shutdownDownRenderedR45;
    public static volatile String shutdownClientFailureR45="";
    public static volatile net.minecraft.nbt.CompoundTag shutdownLiveR45=new net.minecraft.nbt.CompoundTag(),shutdownAtExitKeyR45=new net.minecraft.nbt.CompoundTag(),shutdownEmptyEntryR45=new net.minecraft.nbt.CompoundTag(),shutdownPowerEntryR45=new net.minecraft.nbt.CompoundTag();
    public static volatile double shutdownRotationErrorR45,shutdownPositionErrorR45,shutdownScaleErrorR45;
    private static int shutdownClockR45,shutdownCasesR45,powerPreviousR45,powerPositiveTicksR45;
    private static boolean shutdownInitializedR45,shutdownServerDownR45;
    private static UUID shutdownEvaR45;
    private static float shutdownHitHealthR45;
    private static net.minecraft.nbt.CompoundTag shutdownServerEmptyR45,shutdownServerPowerR45;
    private static final JsonArray SHUTDOWN_EVENTS_R45=new JsonArray();
    private static void shutdownCheckR45(String name,boolean value)
    {
        var row=new JsonObject();row.addProperty("check",name);row.addProperty("passed",value);row.addProperty("phase",shutdownPhaseR45);row.addProperty("phase_tick",shutdownClockR45);SHUTDOWN_EVENTS_R45.add(row);
        if(!value)throw new IllegalStateException("shutdown lifecycle: "+name);
    }
    private static void shutdownNextR45(int next){shutdownPhaseR45=next;shutdownClockR45=0;}
    private static int handBonesR45(net.minecraft.nbt.CompoundTag tag)
    {return (int)tag.getAllKeys().stream().filter(n->n.startsWith("r45_hand_")).count();}
    private static boolean shutdownLifecycleR45(EvaUnit01Entity eva,SachielEntity angel,ServerPlayer pilot,int tick)
    {
        if(!shutdownInitializedR45)
        {
            shutdownInitializedR45=true;
            shutdownCheckR45("real_client_player_not_fake",!(pilot instanceof net.minecraftforge.common.util.FakePlayer));
            shutdownCheckR45("exact_isolated_fixture",CombatR31Review.ownsFixture(eva)&&eva.getUnitVariant()==1);
            shutdownPilotR45=pilot.getUUID();shutdownEvaR45=eva.getUUID();
            CombatR31Review.arrangeR41(80);eva.selectMotionLabWeapon(EvaUnit01Entity.WEAPON_RIFLE);
        }
        if(!shutdownClientFailureR45.isEmpty())throw new IllegalStateException(shutdownClientFailureR45);
        if(++shutdownClockR45>550)throw new IllegalStateException("shutdown phase timeout "+shutdownPhaseR45);
        if(!shutdownEvaR45.equals(eva.getUUID())||!shutdownPilotR45.equals(pilot.getUUID()))throw new IllegalStateException("shutdown fixture actor replaced");
        if(tick%5==0)
        {
            var row=new JsonObject();row.addProperty("tick",tick);row.addProperty("phase",shutdownPhaseR45);row.addProperty("mode",EvaShutdownR30.mode(eva));row.addProperty("power_ticks",eva.getPowerTicks());row.addProperty("pilot_at_controls",com.projectseele.world.EvaPilotResolver.controlTarget(pilot)==eva);row.addProperty("captured_pose_displayed",EvaShutdownR30.displaysCapturedPoseR45(eva));row.addProperty("physical_down",com.projectseele.physics.CombatBodyDynamics.active(eva));row.addProperty("server_pose_bones",EvaShutdownR30.pose(eva).getAllKeys().size());SHUTDOWN_EVENTS_R45.add(row);
        }
        switch(shutdownPhaseR45)
        {
            case 0 ->
            {
                CombatR31Review.forward=shutdownClockR45<36?1:0;
                if(shutdownClockR45==42)CombatR31Review.inputR42(1);
                if(shutdownClockR45>=46&&shutdownLiveR45.getAllKeys().size()==110)
                {
                    shutdownCheckR45("live_final_cache_110_bones_34_hands",handBonesR45(shutdownLiveR45)==34);
                    shutdownCheckR45("real_pilot_controls_before_v",com.projectseele.world.EvaPilotResolver.controlTarget(pilot)==eva&&EvaShutdownR30.mode(eva)==EvaShutdownR30.ACTIVE);
                    CombatR31Review.photo="r45_shutdown_requested_before_v";CombatR31Review.inputR42(7);shutdownNextR45(1);
                }
            }
            case 1 ->
            {
                CombatR31Review.forward=0;
                if(EvaShutdownR30.mode(eva)!=EvaShutdownR30.EMPTY)return false;
                if(shutdownServerEmptyR45==null&&eva.getPersistentData().getBoolean("R30FrozenPoseConfirmed")&&!shutdownEmptyEntryR45.isEmpty())
                {
                    shutdownServerEmptyR45=EvaShutdownR30.pose(eva).copy();
                    shutdownCheckR45("v_key_reached_production_exit",shutdownExitKeyR45&&eva.getPilotEntity()==null&&com.projectseele.world.EvaPilotResolver.controlTarget(pilot)!=eva);
                    shutdownCheckR45("empty_uses_actual_final_cached_frame",shutdownServerEmptyR45.equals(shutdownEmptyEntryR45)&&shutdownServerEmptyR45.getAllKeys().size()==110&&handBonesR45(shutdownServerEmptyR45)==34);
                }
                if(shutdownServerEmptyR45!=null)shutdownCheckStableR45(eva,shutdownServerEmptyR45);
                if(shutdownClockR45>=140&&shutdownEmptyFramesR45>=100)
                {
                    shutdownCheckR45("empty_hold_without_physical_fall",shutdownServerEmptyR45!=null&&!com.projectseele.physics.CombatBodyDynamics.active(eva)&&EvaShutdownR30.displaysCapturedPoseR45(eva));
                    shutdownCheckR45("empty_actual_render_stable",shutdownRotationErrorR45<=1e-4&&shutdownPositionErrorR45<=1e-4&&shutdownScaleErrorR45<=1e-4);
                    shutdownCasesR45++;CombatR31Review.photo="r45_shutdown_empty_hold";shutdownNextR45(2);
                }
            }
            case 2 ->
            {
                if(shutdownClockR45==1)
                {
                    // A nine-cell disposable QA deck is explicit test geometry,
                    // not evidence of a delivered field/hangar boarding port.
                    Vec3 actualSocket=eva.getEntryPlugSocketPosition();
                    double x=actualSocket.x,y=eva.getY()+Math.ceil(EvaScale.fromLegacy(26D)),z=eva.getZ()-EvaScale.fromLegacy(5D);
                    var standing=pilot.getBoundingBox().move(new Vec3(x,y,z).subtract(pilot.position()));
                    if(standing.intersects(eva.getBoundingBox())||!pilot.serverLevel().noCollision(pilot,standing))throw new IllegalStateException("QA gantry standing volume intersects EVA/terrain");
                    var floor=net.minecraft.core.BlockPos.containing(x,y-1,z);
                    for(int dx=-1;dx<=1;dx++)for(int dz=-2;dz<=0;dz++)
                    {
                        var at=floor.offset(dx,0,dz);
                        if(new net.minecraft.world.phys.AABB(at).intersects(eva.getBoundingBox()))throw new IllegalStateException("QA gantry support intersects frozen EVA");
                        if(at.getY()<pilot.serverLevel().getMinBuildHeight()||at.getY()>=pilot.serverLevel().getMaxBuildHeight())throw new IllegalStateException("QA boarding deck exceeds actual build height "+at);
                        if(!pilot.serverLevel().getBlockState(at).isAir()||pilot.serverLevel().getBlockEntity(at)!=null)throw new IllegalStateException("QA boarding deck is occupied; choose a fresh declared shutdown arena "+at);
                    }
                    var deckState=net.minecraft.world.level.block.Blocks.SMOOTH_STONE.defaultBlockState();
                    for(int dx=-1;dx<=1;dx++)for(int dz=-2;dz<=0;dz++)
                    {
                        var at=floor.offset(dx,0,dz);boolean placed=pilot.serverLevel().setBlock(at,deckState,2);
                        if(!placed||!pilot.serverLevel().getBlockState(at).equals(deckState)||pilot.serverLevel().getBlockEntity(at)!=null
                                ||!pilot.serverLevel().getBlockState(at).isFaceSturdy(pilot.serverLevel(),at,net.minecraft.core.Direction.UP))throw new IllegalStateException("QA boarding deck failed actual placement/readback "+at);
                    }
                    var feet=net.minecraft.core.BlockPos.containing(x,y,z);
                    if(!pilot.serverLevel().getBlockState(feet).getCollisionShape(pilot.serverLevel(),feet).isEmpty()
                            ||!pilot.serverLevel().getBlockState(feet.above()).getCollisionShape(pilot.serverLevel(),feet.above()).isEmpty())throw new IllegalStateException("QA boarding deck headroom obstructed");
                    Vec3 eye=new Vec3(x,y+pilot.getEyeHeight(),z),aim=eva.getEntryPlugSocketPosition().subtract(eye);
                    float yaw=(float)(Math.toDegrees(Math.atan2(-aim.x,aim.z))),pitch=(float)-Math.toDegrees(Math.atan2(aim.y,aim.horizontalDistance()));
                    pilot.teleportTo(pilot.serverLevel(),x,y,z,yaw,pitch);
                    var sight=pilot.serverLevel().clip(new net.minecraft.world.level.ClipContext(pilot.getEyePosition(),eva.getEntryPlugSocketPosition(),net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,pilot));
                    if(!eva.isEntryPlugTargeted(pilot)||sight.getType()!=net.minecraft.world.phys.HitResult.Type.MISS&&sight.getLocation().distanceToSqr(eva.getEntryPlugSocketPosition())>Math.pow(EvaScale.fromLegacy(.75D),2))throw new IllegalStateException("QA gantry cannot actually target socket within unchanged native reach/LOS");
                }
                boolean riding=com.projectseele.world.EvaPilotResolver.controlTarget(pilot)==eva;
                if(!riding&&shutdownClockR45%20==0){shutdownEntryTraceR45(pilot,eva,"review_before_use_request",true,null);CombatR31Review.inputR42(9);}
                if(riding)CombatR31Review.forward=1;
                if(riding&&eva.isPoweredOn()&&shutdownClockR45>=150&&shutdownReleasedR45)
                {
                    shutdownCheckR45("normal_right_click_reboard_releases_empty",shutdownReboardKeyR45&&EvaShutdownR30.mode(eva)==EvaShutdownR30.ACTIVE&&!EvaShutdownR30.displaysCapturedPoseR45(eva)&&EvaShutdownR30.pose(eva).isEmpty());
                    shutdownCasesR45++;CombatR31Review.photo="r45_shutdown_normal_reboard";
                    // Same bounded positive battery fixture used by PowerFreeze.
                    // Never write zero power, shutdown mode, pose or success.
                    var tag=eva.saveWithoutId(new net.minecraft.nbt.CompoundTag());tag.putInt("SeelePowerTicks",120);tag.putBoolean("SeeleBatterySession",true);tag.putBoolean("SeeleUmbilicalSevered",true);eva.load(tag);
                    shutdownCheckR45("positive_battery_seed_preserves_original_pilot",eva.getPowerTicks()==120&&eva.getPilotEntity()==pilot&&shutdownEvaR45.equals(eva.getUUID()));
                    powerPreviousR45=120;shutdownNextR45(3);
                }
            }
            case 3 ->
            {
                int power=eva.getPowerTicks();if(power>powerPreviousR45)throw new IllegalStateException("battery replenished during depletion case");
                if(power>0)powerPositiveTicksR45++;powerPreviousR45=power;CombatR31Review.forward=1;
                if(EvaShutdownR30.mode(eva)==EvaShutdownR30.POWER_LOCK)
                {
                    shutdownCheckR45("actual_positive_battery_consumed_to_zero",power==0&&powerPositiveTicksR45>=90&&eva.getPilotEntity()==pilot);
                    CombatR31Review.forward=0;shutdownNextR45(4);
                }
            }
            case 4 ->
            {
                if(shutdownServerPowerR45==null&&eva.getPersistentData().getBoolean("R30FrozenPoseConfirmed")&&!shutdownPowerEntryR45.isEmpty())
                {
                    shutdownServerPowerR45=EvaShutdownR30.pose(eva).copy();
                    shutdownCheckR45("power_uses_actual_final_cached_frame",shutdownServerPowerR45.equals(shutdownPowerEntryR45)&&shutdownServerPowerR45.getAllKeys().size()==110&&handBonesR45(shutdownServerPowerR45)==34);
                }
                if(shutdownServerPowerR45!=null)shutdownCheckStableR45(eva,shutdownServerPowerR45);
                if(shutdownClockR45>=140&&shutdownPowerFramesR45>=100)
                {
                    shutdownCheckR45("power_hold_without_physical_fall",shutdownServerPowerR45!=null&&EvaShutdownR30.mode(eva)==EvaShutdownR30.POWER_LOCK&&!com.projectseele.physics.CombatBodyDynamics.active(eva));
                    shutdownCheckR45("power_actual_render_stable",shutdownRotationErrorR45<=1e-4&&shutdownPositionErrorR45<=1e-4&&shutdownScaleErrorR45<=1e-4);
                    shutdownCasesR45++;CombatR31Review.photo="r45_shutdown_power_hold";shutdownNextR45(5);
                }
            }
            case 5 ->
            {
                if(shutdownClockR45==1)
                {
                    // Only the independent attacker moves; the held EVA is untouched.
                    angel.cancelStrikeR31();angel.setTarget(null);angel.moveTo(eva.getX(),eva.getY(),eva.getZ()+23,180,0);angel.yBodyRot=angel.yHeadRot=180;
                    shutdownHitHealthR45=eva.getHealth();shutdownCheckR45("real_overhead_strike_started",angel.beginStrike(eva,SachielStrike.OVERHEAD));
                }
                var reaction=CombatFeelR31.beat(eva);
                if(reaction!=null&&reaction.kind()==CombatFeelR31.DOWN
                        &&com.projectseele.physics.CombatBodyDynamics.active(eva)&&!EvaShutdownR30.displaysCapturedPoseR45(eva))shutdownServerDownR45=true;
                if(shutdownClockR45>=100&&shutdownDownFramesR45>=10)
                {
                    shutdownCheckR45("actual_crushing_hit_not_swallowed",angel.lastStrikeConnectedR36()&&eva.getHealth()<shutdownHitHealthR45&&eva.getHealth()>0);
                    shutdownCheckR45("real_down_has_physical_and_render_authority",shutdownServerDownR45&&shutdownDownRenderedR45);
                    shutdownCasesR45++;CombatR31Review.photo="r45_shutdown_actual_down";shutdownNextR45(6);return true;
                }
            }
            case 6 -> {return true;}
            default -> throw new IllegalStateException("Unknown shutdown phase");
        }
        return false;
    }
    private static void shutdownCheckStableR45(EvaUnit01Entity eva,net.minecraft.nbt.CompoundTag expected)
    {if(!expected.equals(EvaShutdownR30.pose(eva)))throw new IllegalStateException("server captured pose changed before real DOWN");}
    private static final java.util.concurrent.ConcurrentLinkedQueue<JsonObject> SHUTDOWN_ENTRY_TRACE_R45=new java.util.concurrent.ConcurrentLinkedQueue<>();
    public static boolean shutdownEntryTraceEnabledR45()
    {return SHUTDOWN_LIFECYCLE&&Boolean.getBoolean("projectseele.r45ShutdownEntryTrace")&&shutdownPhaseR45==2;}
    public static boolean shutdownEntryTraceAllowedR45(net.minecraft.world.entity.player.Player player,EvaUnit01Entity eva)
    {return shutdownEntryTraceEnabledR45()&&player!=null&&player.getUUID().equals(shutdownPilotR45)&&eva.getUUID().equals(shutdownEvaR45);}
    /** Bounded observations of the existing entry path; no authority/mode writes. */
    public static void shutdownEntryTraceR45(net.minecraft.world.entity.player.Player player,net.minecraft.world.entity.Entity target,String edge,boolean requireAim,Boolean actualClearRay)
    {
        if(!shutdownEntryTraceEnabledR45()
                ||player==null||!player.getUUID().equals(shutdownPilotR45)||SHUTDOWN_ENTRY_TRACE_R45.size()>=256)return;
        var bound=player.level().getEntity(CombatR31Review.evaId);
        if(!(bound instanceof EvaUnit01Entity eva)||!eva.getUUID().equals(shutdownEvaR45))return;
        var row=new JsonObject();row.addProperty("edge",edge);row.addProperty("client",player.level().isClientSide);row.addProperty("game_tick",player.level().getGameTime());row.addProperty("nano_time",System.nanoTime());row.addProperty("phase_tick",shutdownClockR45);
        row.addProperty("target_found",target!=null);if(target!=null){row.addProperty("target_id",target.getId());row.addProperty("target_uuid",target.getStringUUID());row.addProperty("target_type",net.minecraft.core.registries.BuiltInRegistries.ENTITY_TYPE.getKey(target.getType()).toString());}
        row.addProperty("player_uuid",player.getStringUUID());row.addProperty("player_passenger",player.isPassenger());row.addProperty("eva_uuid",eva.getStringUUID());row.addProperty("eva_vehicle",eva.isVehicle());row.addProperty("require_aim",requireAim);
        row.addProperty("minimum_build_y",player.level().getMinBuildHeight());row.addProperty("maximum_build_y_exclusive",player.level().getMaxBuildHeight());row.addProperty("actual_player_floor",player.level().getBlockState(player.blockPosition().below()).toString());
        row.addProperty("mode",EvaShutdownR30.mode(eva));row.addProperty("nerv_locked",eva.isNervLogisticsLocked());row.addProperty("launch_active",eva.isLaunchSequenceActive());row.addProperty("berserk",eva.isBerserk());row.addProperty("actual_native_targeted",eva.isEntryPlugTargeted(player));
        Vec3 eye=player.getEyePosition(),socket=eva.getEntryPlugSocketPosition(),look=player.getViewVector(1).normalize(),to=socket.subtract(eye),horizontal=player.position().subtract(eva.position()).multiply(1,0,1),rear=eva.getForward().multiply(-1,0,-1).normalize();
        row.addProperty("relative_height",player.getY()-eva.getY());row.addProperty("horizontal_distance",horizontal.length());row.addProperty("rear_dot",horizontal.lengthSqr()>1e-8?horizontal.normalize().dot(rear):-1);
        row.addProperty("socket_distance",to.length());row.addProperty("ray_along",to.dot(look));row.addProperty("ray_miss_squared",Math.max(0,to.lengthSqr()-Math.pow(to.dot(look),2)));row.addProperty("player_yaw",player.getYRot());row.addProperty("player_pitch",player.getXRot());
        for(var p:Map.of("player",player.position(),"eva",eva.position(),"eye",eye,"socket",socket,"look",look).entrySet())
        {var vector=new JsonArray();vector.add(p.getValue().x);vector.add(p.getValue().y);vector.add(p.getValue().z);row.add(p.getKey(),vector);}
        var box=eva.getBoundingBox();var bounds=new JsonArray();for(double n:new double[]{box.minX,box.minY,box.minZ,box.maxX,box.maxY,box.maxZ})bounds.add(n);row.add("eva_actual_bounds",bounds);
        row.addProperty("legacy_find_search_intersects",player.getBoundingBox().inflate(18,48,18).intersects(box));
        var clip=player.level().clip(new net.minecraft.world.level.ClipContext(eye,socket,net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,player));
        row.addProperty("observed_clip_type",clip.getType().name());row.addProperty("observed_clip_block",clip.getBlockPos().toShortString());row.addProperty("observed_clip_state",player.level().getBlockState(clip.getBlockPos()).toString());
        row.addProperty("observed_clear_ray",clip.getType()==net.minecraft.world.phys.HitResult.Type.MISS||clip.getLocation().distanceToSqr(socket)<=Math.pow(EvaScale.fromLegacy(.75D),2));
        if(actualClearRay!=null)row.addProperty("production_private_clear_ray",actualClearRay);
        SHUTDOWN_ENTRY_TRACE_R45.add(row);com.projectseele.ProjectSeele.LOGGER.info("R45 SHUTDOWN ENTRY TRACE {}",row);
    }

    private static final java.util.concurrent.ConcurrentLinkedQueue<JsonObject> SHUTDOWN_FROZEN_ACK_R45=new java.util.concurrent.ConcurrentLinkedQueue<>();
    public static boolean shutdownFrozenAckEnabledR45(EvaUnit01Entity eva)
    {return SHUTDOWN_LIFECYCLE&&Boolean.getBoolean("projectseele.r45FrozenAckTrace")&&shutdownEvaR45!=null&&shutdownEvaR45.equals(eva.getUUID())&&SHUTDOWN_FROZEN_ACK_R45.size()<256;}
    public static void shutdownFrozenAckTraceR45(EvaUnit01Entity eva,String edge,JsonObject details)
    {
        if(!shutdownFrozenAckEnabledR45(eva))return;
        var row=details.deepCopy();row.addProperty("edge",edge);row.addProperty("client",eva.level().isClientSide);row.addProperty("game_tick",eva.level().getGameTime());row.addProperty("nano_time",System.nanoTime());row.addProperty("phase",shutdownPhaseR45);row.addProperty("actor_uuid",eva.getStringUUID());row.addProperty("mode",EvaShutdownR30.mode(eva));row.addProperty("since",EvaShutdownR30.since(eva));row.addProperty("mode_age",eva.level().getGameTime()-EvaShutdownR30.since(eva));row.addProperty("server_pose_bones",EvaShutdownR30.pose(eva).size());
        var pilot=eva.getPilotEntity();row.addProperty("actual_pilot_uuid",pilot==null?"none":pilot.getStringUUID());SHUTDOWN_FROZEN_ACK_R45.add(row);com.projectseele.ProjectSeele.LOGGER.info("R45 FROZEN ACK TRACE {}",row);
    }

    private static JsonObject shutdownDetailsR45()
    {
        var r=new JsonObject();r.addProperty("passed",shutdownCasesR45==4&&shutdownClientFailureR45.isEmpty());r.addProperty("completed_cases",shutdownCasesR45);
        r.addProperty("scope","Existing isolated R31 actor with one real integrated client; initial mount uses existing fixture helper. V and reboard use actual client keys/production dispatch.");
        r.addProperty("formal_hangar_original_plug_verified",false);r.addProperty("cold_restart_verified",false);r.addProperty("second_real_client_verified",false);r.addProperty("user_art_accepted",false);
        r.addProperty("qa_arena_x",CombatR31Review.X);r.addProperty("qa_arena_z",CombatR31Review.Z);r.addProperty("qa_floor",CombatR31Review.FLOOR);
        r.addProperty("qa_reboard_deck_cells",9);r.addProperty("fixture_battery_seed",120);r.addProperty("positive_consumption_ticks",powerPositiveTicksR45);
        r.addProperty("empty_actual_frames",shutdownEmptyFramesR45);r.addProperty("power_actual_frames",shutdownPowerFramesR45);r.addProperty("physical_down_actual_frames",shutdownDownFramesR45);
        r.addProperty("maximum_rotation_quaternion_error",shutdownRotationErrorR45);r.addProperty("maximum_position_channel_error",shutdownPositionErrorR45);r.addProperty("maximum_scale_channel_error",shutdownScaleErrorR45);
        r.addProperty("actual_final_cache_before_v_key_snbt",shutdownAtExitKeyR45.toString());r.addProperty("actual_last_live_before_empty_snbt",shutdownEmptyEntryR45.toString());r.addProperty("actual_last_live_before_power_lock_snbt",shutdownPowerEntryR45.toString());
        if(shutdownServerEmptyR45!=null)r.addProperty("server_confirmed_empty_snbt",shutdownServerEmptyR45.toString());if(shutdownServerPowerR45!=null)r.addProperty("server_confirmed_power_snbt",shutdownServerPowerR45.toString());
        var entry=new JsonArray();for(var row:SHUTDOWN_ENTRY_TRACE_R45)entry.add(row);r.add("entry_trace",entry);var ack=new JsonArray();for(var row:SHUTDOWN_FROZEN_ACK_R45)ack.add(row);r.add("frozen_ack_trace",ack);r.addProperty("client_error",shutdownClientFailureR45);r.add("events",SHUTDOWN_EVENTS_R45);return r;
    }

    public static final boolean CANNON_FIRE_R45=ENABLED&&Boolean.getBoolean("projectseele.r45CannonFireReview");
    public static volatile boolean cannonUseHeldR45;
    public static volatile float cannonViewPitchR45;
    private static int cannonCaseR45,cannonPhaseR45,cannonClockR45,cannonCasesPassedR45;
    private static UUID cannonEvaR45,cannonPilotR45;
    private static final JsonArray CANNON_SHOTS_R45=new JsonArray(),CANNON_SAMPLES_R45=new JsonArray(),CANNON_CASES_R45=new JsonArray();
    private static final java.util.concurrent.ConcurrentLinkedQueue<JsonObject> CANNON_CLIENT_R45=new java.util.concurrent.ConcurrentLinkedQueue<>();
    private static float cannonTargetHealthR45;
    private static boolean cannonFixtureReadyR45,cannonLivingHitR45;
    private static final JsonArray CANNON_HIT_PREFLIGHT_R45=new JsonArray();
    private static JsonArray cannonVectorR45(Vec3 v){var a=new JsonArray();a.add(v.x);a.add(v.y);a.add(v.z);return a;}
    /** Called only by the real server firing consumer after ray/damage resolution. */
    public static void actualCannonShotR45(EvaUnit01Entity eva,net.minecraft.world.entity.LivingEntity pilot,Vec3 muzzle,Vec3 direction,Vec3 endpoint,net.minecraft.world.entity.Entity hit)
    {
        if(!CANNON_FIRE_R45||!CombatR31Review.ownsFixture(eva)||!eva.getUUID().equals(cannonEvaR45)||pilot==null||!pilot.getUUID().equals(cannonPilotR45))return;
        var row=new JsonObject();row.addProperty("case",cannonCaseR45);row.addProperty("server_tick",eva.level().getGameTime());row.addProperty("stance",eva.rifleStanceLevel(0));row.addProperty("requested_pitch",cannonViewPitchR45);row.addProperty("actual_pilot_pitch",pilot.getXRot());row.addProperty("weapon_pitch",eva.clampPilotWeaponPitch(pilot.getXRot(),1));row.addProperty("cooldown_after_release",eva.getCannonCooldown());row.addProperty("range",eva.effectiveCannonRangeR45());row.addProperty("cannon_contact_frame_enabled",EvaCannonFrameR45.enabled(eva));
        row.addProperty("eva_uuid",eva.getStringUUID());row.addProperty("pilot_uuid",pilot.getStringUUID());row.add("server_actual_muzzle",cannonVectorR45(muzzle));row.add("server_actual_direction",cannonVectorR45(direction));row.add("server_actual_endpoint",cannonVectorR45(endpoint));row.addProperty("hit_uuid",hit==null?"none":hit.getStringUUID());row.addProperty("hit_type",hit==null?"none":net.minecraft.core.registries.BuiltInRegistries.ENTITY_TYPE.getKey(hit.getType()).toString());
        if(hit instanceof net.minecraft.world.entity.LivingEntity living)row.addProperty("hit_health_after_ray",living.getHealth());
        if(EvaCannonFrameR45.enabled(eva))
        {
            var frame=EvaCannonFrameR45.sample(eva,1,direction);row.add("same_production_cannon_frame_muzzle",cannonVectorR45(frame.muzzle()));row.add("cannon_frame_stock",cannonVectorR45(frame.stock()));row.add("cannon_frame_forward",cannonVectorR45(frame.forward()));
            row.addProperty("server_muzzle_frame_delta",frame.muzzle().distanceTo(muzzle));
        }
        CANNON_SHOTS_R45.add(row);com.projectseele.ProjectSeele.LOGGER.info("R45 ACTUAL CANNON FIRE {}",row);
    }
    public static void actualClientCannonBeamR45(double x1,double y1,double z1,double x2,double y2,double z2)
    {
        if(!CANNON_FIRE_R45||CANNON_CLIENT_R45.size()>=12)return;
        var row=new JsonObject();row.addProperty("case",cannonCaseR45);row.add("actual_received_muzzle",cannonVectorR45(new Vec3(x1,y1,z1)));row.add("actual_received_endpoint",cannonVectorR45(new Vec3(x2,y2,z2)));CANNON_CLIENT_R45.add(row);
    }
    /** One pre-fire placement using production body/ray admission, never a guessed centre hit. */
    private static void cannonLivingPlacementR45(EvaUnit01Entity eva,SachielEntity angel,ServerPlayer pilot)
    {
        Vec3 dir=Vec3.directionFromRotation(eva.clampPilotWeaponPitch(pilot.getXRot(),1),eva.clampPilotWeaponYaw(pilot.getYRot(),1)).normalize();
        Vec3 from=eva.getMuzzlePositionForPoseCapture(dir);var level=pilot.serverLevel();
        var terrain=level.clip(new net.minecraft.world.level.ClipContext(from,from.add(dir.scale(eva.effectiveCannonRangeR45())),net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,eva));
        Vec3 side=dir.cross(new Vec3(0,1,0)).normalize();double width=angel.getBbWidth();
        // Candidates stay on the existing 513-square floor. Earlier real craters must pass the support check.
        for(double distance:new double[]{96,128,160})for(double lateral:new double[]{0,width*.25,-width*.25})
        {
            Vec3 at=from.add(dir.scale(distance)).add(side.scale(lateral));
            angel.moveTo(at.x,CombatR31Review.FLOOR+1,at.z,180,0);angel.refreshDimensions();
            var box=angel.getBoundingBox();boolean supported=true;int cells=0;
            for(int x=net.minecraft.util.Mth.floor(box.minX);x<=net.minecraft.util.Mth.floor(box.maxX);x++)
                for(int z=net.minecraft.util.Mth.floor(box.minZ);z<=net.minecraft.util.Mth.floor(box.maxZ);z++)
                {
                    var block=new net.minecraft.core.BlockPos(x,CombatR31Review.FLOOR,z);cells++;
                    if(!level.getBlockState(block).isFaceSturdy(level,block,net.minecraft.core.Direction.UP))supported=false;
                }
            var hit=supported?com.projectseele.physics.CombatDamageTargetsR44.ray(level,from,terrain.getLocation(),.3,eva,pilot):null;
            boolean admitted=hit!=null&&hit.getEntity()==angel;
            var row=new JsonObject();row.addProperty("distance",distance);row.addProperty("lateral",lateral);row.addProperty("full_floor_support",supported);row.addProperty("support_cells",cells);
            row.add("target_position",cannonVectorR45(angel.position()));row.add("actual_muzzle",cannonVectorR45(from));row.add("terrain_endpoint",cannonVectorR45(terrain.getLocation()));
            row.addProperty("ray_first_hit_uuid",hit==null?"none":hit.getEntity().getStringUUID());row.addProperty("original_target_admitted",admitted);
            if(hit!=null)row.add("actual_body_contact",cannonVectorR45(hit.getLocation()));CANNON_HIT_PREFLIGHT_R45.add(row);
            if(admitted){angel.setOnGround(true);cannonTargetHealthR45=angel.getHealth();return;}
        }
        throw new IllegalStateException("No supported original living target admits the production cannon ray");
    }
    private static boolean cannonFireTickR45(EvaUnit01Entity eva,SachielEntity angel,ServerPlayer pilot,int tick)
    {
        if(!cannonFixtureReadyR45)
        {
            if(pilot instanceof net.minecraftforge.common.util.FakePlayer||!CombatR31Review.ownsFixture(eva)||eva.getUnitVariant()!=1)throw new IllegalStateException("Cannon fire needs one real Unit01 fixture pilot");
            cannonFixtureReadyR45=true;cannonEvaR45=eva.getUUID();cannonPilotR45=pilot.getUUID();CombatR31Review.arrangeR41(80);
            if(!eva.selectMotionLabWeapon(EvaUnit01Entity.WEAPON_CANNON))throw new IllegalStateException("Actual cannon selection rejected");
            // Keep the original actor out of all six stance/pitch calibration rays.
            angel.moveTo(eva.getX()+150,CombatR31Review.FLOOR+1,eva.getZ(),180,0);angel.setTarget(null);
        }
        if(++cannonClockR45>550)throw new IllegalStateException("Cannon input case timeout "+cannonCaseR45+" phase "+cannonPhaseR45);
        if(!cannonEvaR45.equals(eva.getUUID())||!cannonPilotR45.equals(pilot.getUUID())||eva.getPilotEntity()!=pilot)throw new IllegalStateException("Cannon original actor/pilot changed");
        CombatR31Review.forward=CombatR31Review.strafe=0;CombatR31Review.jump=CombatR31Review.sprint=false;
        float desired=cannonCaseR45==6?0:cannonCaseR45/2==0?0:cannonCaseR45/2==1?1:3;cannonViewPitchR45=cannonCaseR45==6?8:cannonCaseR45%2==0?-8:8;
        if(tick%5==0)
        {
            var row=new JsonObject();row.addProperty("tick",tick);row.addProperty("case",cannonCaseR45);row.addProperty("phase",cannonPhaseR45);row.addProperty("actual_stance",eva.rifleStanceLevel(0));row.addProperty("charge",eva.getCannonCharge());row.addProperty("cooldown",eva.getCannonCooldown());row.addProperty("use_key_held_requested",cannonUseHeldR45);row.addProperty("pilot_pitch",pilot.getXRot());CANNON_SAMPLES_R45.add(row);
        }
        if(cannonPhaseR45==0)
        {
            cannonUseHeldR45=false;
            if(cannonClockR45==1)
            {
                if(eva.isPilotProne()&&desired!=3)eva.toggleProne(pilot);
                if(desired==3){eva.setPilotCrouching(pilot,true);if(!eva.isPilotProne())eva.toggleProne(pilot);}
                else eva.setPilotCrouching(pilot,desired==1);
            }
            if(Math.abs(eva.rifleStanceLevel(0)-desired)>.01F||eva.getCannonCooldown()>0||!eva.isPoweredOn()||Math.abs(pilot.getXRot()-cannonViewPitchR45)>.25F)return false;
            cannonPhaseR45=1;cannonClockR45=0;cannonUseHeldR45=true;return false;
        }
        if(cannonPhaseR45==1)
        {
            cannonUseHeldR45=true;
            if(eva.getCannonCharge()<com.projectseele.config.SeeleConfig.CANNON_CHARGE_TICKS.get())return false;
            if(cannonCaseR45==6)cannonLivingPlacementR45(eva,angel,pilot);
            cannonUseHeldR45=false;cannonPhaseR45=2;cannonClockR45=0;return false;
        }
        if(CANNON_SHOTS_R45.size()<cannonCaseR45+1||CANNON_CLIENT_R45.size()<cannonCaseR45+1)return false;
        if(CANNON_SHOTS_R45.size()!=cannonCaseR45+1)throw new IllegalStateException("Unexpected duplicate actual cannon shot");
        var shot=CANNON_SHOTS_R45.get(cannonCaseR45).getAsJsonObject();var expectedPitch=eva.clampPilotWeaponPitch(cannonViewPitchR45,1);
        var received=new java.util.ArrayList<>(CANNON_CLIENT_R45).get(cannonCaseR45);
        if(!shot.get("server_actual_muzzle").equals(received.get("actual_received_muzzle"))||!shot.get("server_actual_endpoint").equals(received.get("actual_received_endpoint")))throw new IllegalStateException("Actual client beam differs from the real server ray");
        if(Math.abs(shot.get("stance").getAsFloat()-desired)>.01F||Math.abs(shot.get("weapon_pitch").getAsFloat()-expectedPitch)>.25F)throw new IllegalStateException("Actual shot stance/pitch differs from requested input");
        if(shot.has("server_muzzle_frame_delta")&&shot.get("server_muzzle_frame_delta").getAsDouble()>1e-4)throw new IllegalStateException("Cannon shot did not use production geometry frame muzzle");
        if(cannonCaseR45==6)
        {
            if(!shot.get("hit_uuid").getAsString().equals(angel.getStringUUID())||!shot.has("hit_health_after_ray")
                    ||shot.get("hit_health_after_ray").getAsFloat()>=cannonTargetHealthR45)
                throw new IllegalStateException("Pre-admitted cannon ray did not actually hit/damage the original living actor");
            cannonLivingHitR45=true;
        }
        var row=new JsonObject();row.addProperty("case",cannonCaseR45);row.addProperty("stance",desired);row.addProperty("pitch",cannonViewPitchR45);row.addProperty("passed",true);row.addProperty("actual_server_shot_index",cannonCaseR45);CANNON_CASES_R45.add(row);cannonCasesPassedR45++;
        CombatR31Review.photo="r45_cannon_actual_"+cannonCaseR45;cannonUseHeldR45=false;
        if(++cannonCaseR45>=7)return true;cannonPhaseR45=0;cannonClockR45=0;return false;
    }
    private static JsonObject cannonFireDetailsR45()
    {
        var result=new JsonObject();result.addProperty("passed",cannonCasesPassedR45==7&&cannonLivingHitR45&&CANNON_SHOTS_R45.size()==7&&CANNON_CLIENT_R45.size()==7);result.addProperty("actual_cases",cannonCasesPassedR45);result.addProperty("six_stance_pitch_calibrations_passed",cannonCasesPassedR45>=6);result.addProperty("independent_original_living_hit_verified",cannonLivingHitR45);result.add("living_hit_preflight",CANNON_HIT_PREFLIGHT_R45);result.addProperty("source","Actual real-client use-key edges, production charge/release/ray/damage and received beam packet; original pose changes reuse existing authorized fixture methods");result.addProperty("rendered_surface_alignment_verified",false);result.addProperty("Yashima_full_mission_verified",false);result.addProperty("user_art_accepted",false);result.add("server_actual_shots",CANNON_SHOTS_R45);result.add("input_charge_samples",CANNON_SAMPLES_R45);result.add("cases",CANNON_CASES_R45);var client=new JsonArray();for(var row:CANNON_CLIENT_R45)client.add(row);result.add("actual_received_beams",client);return result;
    }

    public static boolean tick(EvaUnit01Entity eva,SachielEntity angel,ServerPlayer pilot,int tick)
    {
        if(CANNON_FIRE_R45)return cannonFireTickR45(eva,angel,pilot,tick);
        if(SHUTDOWN_LIFECYCLE)return shutdownLifecycleR45(eva,angel,pilot,tick);
        if(FIELD_INPUT_R45)return fieldInputR45(eva,pilot,tick);
        if(HANDLING)return handling(eva,pilot,tick);
        if(GAIT_R43)return gaitR43(eva,angel,pilot,tick);
        if(ARTICULATION)return locomotion(eva,angel,pilot,tick);
        if(tick<=360)
        {
            if(tick==1)
            {
                CombatR31Review.arrangeR41(90);
                int weapon=Integer.getInteger("projectseele.r41PoseWeapon",0);
                if(weapon!=0&&!eva.selectMotionLabWeapon(weapon))throw new IllegalStateException("Pose review weapon rejected");
            }
            if(tick==30)eva.setPilotCrouching(pilot,true);
            if(tick==90)eva.toggleProne(pilot);
            if(tick==220)eva.toggleProne(pilot);
            if(tick==232)eva.setPilotCrouching(pilot,true);
            if(tick==280)eva.setPilotCrouching(pilot,false);
            boolean rifle=eva.getWeapon()==EvaUnit01Entity.WEAPON_RIFLE;
            CombatR31Review.rifleFireHeldR45=WEAPON_ACTIONS&&rifle
                    &&java.util.stream.IntStream.of(15,70,145,250,310,335).anyMatch(start->tick>=start&&tick<start+8);
            CombatR31Review.rifleAimHeldR45=WEAPON_ACTIONS&&rifle
                    &&(tick>=60&&tick<85||tick>=130&&tick<158||tick>=240&&tick<264||tick>=330&&tick<348);
            if(WEAPON_ACTIONS&&!rifle&&Set.of(15,70,145,250,310,335).contains(tick))
                CombatR31Review.inputR42(tick==335&&eva.getWeapon()==EvaUnit01Entity.WEAPON_KNIFE?2:1);
            if(WEAPON_ACTIONS&&(eva.getKnifeMotionType(0)>=0||eva.rifleRecoilBlend(0)>.01F))weaponActionFrames++;
            CombatR31Review.forward=tick>=160&&tick<210?1:0;
            if(tick==160)crawlStart=eva.position();
            if(tick==210&&crawlStart!=null)crawlDistance=eva.position().distanceTo(crawlStart);
            sample(eva,tick);
            if(Set.of(25,70,77,145,152,190,250,257,320,342).contains(tick))CombatR31Review.photo="r41_stance_"+tick;
            return false;
        }
        if(POSE_ONLY)return true;
        int requested=(tick-361)/140;
        if(requested>=RANGES.length)return true;
        if(requested!=contactCase)
        {
            contactCase=requested;caseStarted=tick;strikeStarted=false;
            CombatR31Review.arrangeR41(90);eva.setHealth(eva.getMaxHealth());
            if(eva.isPilotProne())eva.toggleProne(pilot);
            eva.setPilotCrouching(pilot,requested==3);
            if(requested==4)eva.toggleProne(pilot);
            healthBefore=eva.getHealth();
        }
        int age=tick-caseStarted;
        if(age==55)
        {
            float wanted=requested==4?3:requested==3?1:0;
            if(Math.abs(eva.rifleStanceLevel(0)-wanted)>.01F)throw new IllegalStateException("Contact fixture stance did not settle: "+requested);
            CombatR31Review.arrangeR41(RANGES[requested]);
        }
        if(age==65)strikeStarted=angel.beginStrike(eva,MODES[requested]);
        if(age==135)
        {
            JsonObject row=new JsonObject();row.addProperty("mode",MODES[requested]);row.addProperty("range",RANGES[requested]);
            row.addProperty("stance",eva.rifleStanceLevel(0));row.addProperty("started",strikeStarted);
            row.addProperty("damage",healthBefore-eva.getHealth());row.addProperty("connected",angel.lastStrikeConnectedR36());
            boolean success=strikeStarted&&angel.lastStrikeConnectedR36();row.addProperty("passed",success);passed&=success;CONTACTS.add(row);
        }
        return false;
    }
    private static void sample(EvaUnit01Entity eva,int tick)
    {
        var pose=EvaBodyPose.sample(eva,0);poseSamples++;
        float worst=0;String worstBone="";
        for(String name:pose.rig.keySet())
        {
            if(HANDLING&&Set.of("knife","cannon","n2","lance").contains(name))continue;
            var now=pose.rotations.get(name);var old=PREVIOUS.put(name,new Quaternionf(now));
            if(old!=null){float angle=(float)Math.toDegrees(2*Math.acos(Math.min(1,Math.abs(old.dot(now)))));if(angle>worst){worst=angle;worstBone=name;}}
        }
        maxRotation=Math.max(maxRotation,worst);
        JsonObject row=new JsonObject();row.addProperty("tick",tick);row.addProperty("stance",eva.rifleStanceLevel(0));row.addProperty("joint_delta_degrees",worst);
        row.addProperty("worst_bone",worstBone);
        row.addProperty("weapon",eva.getWeapon());row.addProperty("knife_type",eva.getKnifeMotionType(0));row.addProperty("rifle_recoil",eva.rifleRecoilBlend(0));
        row.addProperty("rifle_sight_blend",eva.rifleSightBlendR45(0));
        if(HANDLING){row.addProperty("equipment_active",EvaWeaponHandlingR45.active(eva));row.addProperty("equipment_phase",EvaWeaponHandlingR45.phase(eva,0));}
        row.addProperty("sprinting",eva.isPilotSprinting());row.addProperty("ground",eva.onGround());
        row.addProperty("guard_weight",EvaGameplayMotionR32.guardWeight(eva));row.addProperty("server_movement",EvaGameplayMotionR32.serverMovement(eva));
        row.addProperty("gait",eva.rifleGaitPhase(0));row.addProperty("move",eva.rifleMoveBlend(0));row.addProperty("run",eva.rifleRunBlend(0));
        var position=new JsonArray();position.add(eva.getX());position.add(eva.getY());position.add(eva.getZ());row.add("position",position);
        JsonObject fingers=new JsonObject();
        for(String side:List.of("l","r"))for(String digit:List.of("index","middle","thumb"))
        {
            String name="finger_"+digit+"_"+side;if(!pose.rig.containsKey(name))continue;
            var q=pose.rotations.get(name);var a=new JsonArray();for(float f:new float[]{q.x,q.y,q.z,q.w})a.add(f);fingers.add(name,a);
        }
        row.add("fingers",fingers);POSES.add(row);
    }
    private static boolean handling(EvaUnit01Entity eva,ServerPlayer pilot,int tick)
    {
        CombatR31Review.forward=0;
        if(tick==1){CombatR31Review.arrangeR41(90);eva.selectMotionLabWeapon(EvaUnit01Entity.WEAPON_FISTS);}
        if(tick==20||tick==160||tick==200)CombatR31Review.inputR42(6);
        if(tick==65)
        {if(EvaWeaponHandlingR45.active(eva)||eva.getWeapon()!=EvaUnit01Entity.WEAPON_KNIFE)throw new IllegalStateException("Knife draw did not hand off");handlingCases++;}
        if(tick==90&&!EvaWeaponHandlingR45.request(eva,EvaUnit01Entity.WEAPON_FISTS))throw new IllegalStateException("Knife stow rejected");
        if(tick==135)
        {if(EvaWeaponHandlingR45.active(eva)||eva.getWeapon()!=EvaUnit01Entity.WEAPON_FISTS)throw new IllegalStateException("Knife stow did not complete");handlingCases++;}
        if(tick==175||tick==226)eva.setNervLogisticsLocked(true);
        if(tick==180||tick==230)
        {
            int expected=tick==180?EvaUnit01Entity.WEAPON_FISTS:EvaUnit01Entity.WEAPON_KNIFE;
            if(EvaWeaponHandlingR45.active(eva)||eva.getWeapon()!=expected)throw new IllegalStateException("Cancelled equipment transaction changed committed weapon");handlingCases++;
        }
        if(tick==181||tick==231)eva.setNervLogisticsLocked(false);
        if(tick<=140)sample(eva,tick);
        if(Set.of(24,28,34,41,49,111,121,135).contains(tick))CombatR31Review.photo="r45_equipment_"+tick;
        return tick>=260;
    }
    private static int flightTicks,jumps;
    private static boolean inFlight;
    private static double jumpFloor,peak;
    private static int sprintTicks;
    private static final net.minecraft.server.level.TicketType<net.minecraft.world.level.ChunkPos> GAIT_TARGET=net.minecraft.server.level.TicketType.create("r43_gait_target",Comparator.comparingLong(net.minecraft.world.level.ChunkPos::toLong));
    private static net.minecraft.world.level.ChunkPos gaitTargetChunk;
    private static boolean gaitR43(EvaUnit01Entity eva,SachielEntity angel,ServerPlayer pilot,int tick)
    {
        if(tick==1)
        {
            CombatR31Review.arrangeR41(240);gaitTargetChunk=angel.chunkPosition();
            if(Boolean.getBoolean("projectseele.r43GuardLocomotion"))
            {angel.teleportTo(eva.getX()+50,CombatR31Review.FLOOR+1,eva.getZ()+100);gaitTargetChunk=angel.chunkPosition();}
            pilot.serverLevel().getChunkSource().addRegionTicket(GAIT_TARGET,gaitTargetChunk,3,gaitTargetChunk);
        }
        // One continuous trajectory: no teleport between gait transitions.
        CombatR31Review.forward=tick>=20&&tick<135||tick>=330&&tick<380?1:tick>=260&&tick<295?-1:0;
        CombatR31Review.sprint=tick>=65&&tick<120;
        if(tick>=90&&tick<=120)CombatR31Review.heading=(tick-90)*6;
        CombatR31Review.jump=tick>=180&&tick<184;
        if(eva.isPilotSprinting())sprintTicks++;
        if(tick==175){jumpFloor=eva.getY();peak=jumpFloor;}
        if(tick>=180&&tick<250)
        {
            if(!eva.onGround()){if(!inFlight)jumps++;inFlight=true;flightTicks++;peak=Math.max(peak,eva.getY());}
            else inFlight=false;
        }
        if(tick==305)eva.setPilotCrouching(pilot,true);
        if(tick==390)eva.toggleProne(pilot);
        if(tick==440)crawlStart=eva.position();
        if(tick>=440&&tick<485)CombatR31Review.forward=1;
        if(tick==485)crawlDistance=eva.position().distanceTo(crawlStart);
        if(tick==495)eva.toggleProne(pilot);
        if(tick==520)eva.setPilotCrouching(pilot,false);
        if(tick!=1)sample(eva,tick);else PREVIOUS.clear();
        if(Set.of(18,28,32,36,40,42,44,48,52,56,60,80,100,140,182,188,195,210,280,352,415,465,548).contains(tick))CombatR31Review.photo="r43_gait_"+tick;
        if(tick>=560)pilot.serverLevel().getChunkSource().removeRegionTicket(GAIT_TARGET,gaitTargetChunk,3,gaitTargetChunk);
        return tick>=560;
    }
    private static boolean locomotion(EvaUnit01Entity eva,SachielEntity angel,ServerPlayer pilot,int tick)
    {
        if(tick==1)CombatR31Review.arrangeR41(240);
        if(tick==110)CombatR31Review.arrangeR41(32);
        CombatR31Review.forward=tick>=20&&tick<80||tick>=120&&tick<132||tick>=385&&tick<430?1:0;
        CombatR31Review.jump=tick>=165&&tick<169;
        if(tick==160){jumpFloor=eva.getY();peak=jumpFloor;}
        if(tick>=165&&tick<250)
        {
            if(!eva.onGround()) {if(!inFlight)jumps++;inFlight=true;flightTicks++;peak=Math.max(peak,eva.getY());}
            else if(inFlight)inFlight=false;
        }
        if(tick==270||tick==286)CombatR31Review.inputR42(1);
        // The low-stance traversal case needs unobstructed terrain. Keep the
        // EVA continuous; move only the separate strike target out of its path.
        if(tick==312)angel.setPos(eva.getX()+70,CombatR31Review.FLOOR+1,eva.getZ()-50);
        if(tick==315)eva.setPilotCrouching(pilot,true);
        if(tick==350)eva.toggleProne(pilot);
        if(tick==385)crawlStart=eva.position();
        if(tick==430)crawlDistance=eva.position().distanceTo(crawlStart);
        if(tick==440)eva.toggleProne(pilot);
        if(tick==465)eva.setPilotCrouching(pilot,false);
        if(tick!=1&&tick!=110)sample(eva,tick);else PREVIOUS.clear();
        if(Set.of(50,90,141,178,185,205,285,338,379,410,485).contains(tick))CombatR31Review.photo="r42_motion_"+tick;
        return tick>=510;
    }
    public static boolean passed(){if(FIELD_INPUT_R45)return FIELD_CASES_R45.size()==5&&fieldInputsRestoredR45;if(CANNON_FIRE_R45)return cannonCasesPassedR45==7&&cannonLivingHitR45&&CANNON_SHOTS_R45.size()==7&&CANNON_CLIENT_R45.size()==7;if(SHUTDOWN_LIFECYCLE)return shutdownCasesR45==4&&shutdownClientFailureR45.isEmpty();return HANDLING?handlingCases==4&&poseSamples>=130&&maxRotation<35:ARTICULATION?(!GAIT_R43||sprintTicks>=40)&&jumps==1&&flightTicks>=10&&flightTicks<=35&&peak-jumpFloor>10&&crawlDistance>1:passed&&(POSE_ONLY||CONTACTS.size()==RANGES.length)&&EVENTS.size()>=4&&poseSamples>=300&&crawlDistance>1&&maxRotation<35&&(!WEAPON_ACTIONS||weaponActionFrames>=6);}
    public static String caseName(){return FIELD_INPUT_R45?"actual_real_client_five_C_field_actions":CANNON_FIRE_R45?"actual_client_cannon_six_calibrations_and_living_hit":SHUTDOWN_LIFECYCLE?"real_v_empty_power_down_r45":HANDLING?"weapon_handoff_and_interrupt_r45":ARTICULATION?"locomotion_and_jump_r42":POSE_ONLY?"stance_weapon_sequence_r45":"stance_and_contact";}
    public static int caseCount(){return FIELD_INPUT_R45?FIELD_CASES_R45.size():CANNON_FIRE_R45?cannonCasesPassedR45:SHUTDOWN_LIFECYCLE?shutdownCasesR45:HANDLING?handlingCases:ARTICULATION||POSE_ONLY?1:CONTACTS.size();}
    public static JsonObject details()
    {
        if(FIELD_INPUT_R45)
        {var out=new JsonObject();out.addProperty("passed",passed());out.addProperty("actual_cases",FIELD_CASES_R45.size());out.addProperty("real_client_not_fake",true);out.addProperty("same_production_actor",true);out.addProperty("inputs_restored",fieldInputsRestoredR45);out.addProperty("visual_or_user_accepted",false);out.add("cases",FIELD_CASES_R45);out.add("actual_server_samples",FIELD_SAMPLES_R45);return out;}
        if(CANNON_FIRE_R45)return cannonFireDetailsR45();
        if(SHUTDOWN_LIFECYCLE)return shutdownDetailsR45();
        JsonObject result=new JsonObject();result.addProperty("passed",passed());result.addProperty("pose_samples",poseSamples);result.addProperty("maximum_joint_delta_degrees",maxRotation);result.addProperty("crawl_distance",crawlDistance);
        result.addProperty("weapon_actions_requested",WEAPON_ACTIONS);result.addProperty("weapon_action_frames",weaponActionFrames);
        result.addProperty("pose_sequence_only",POSE_ONLY);result.addProperty("actual_contact_cases",CONTACTS.size());
        result.addProperty("joint_delta_scope","Server body sample; final client firearm IK and skin require their own actual-render witnesses");
        result.addProperty("equipment_review",HANDLING);result.addProperty("equipment_cases",handlingCases);
        result.addProperty("r42_locomotion",ARTICULATION);result.addProperty("r43_fullbody_gait",GAIT_R43);result.addProperty("sprint_ticks",sprintTicks);result.addProperty("jump_count",jumps);result.addProperty("airborne_ticks",flightTicks);result.addProperty("jump_height",peak-jumpFloor);
        result.add("events",EVENTS);result.add("poses",POSES);result.add("contact_cases",CONTACTS);return result;
    }
    private StanceContactR41Review(){}
}

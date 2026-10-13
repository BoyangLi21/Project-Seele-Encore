package com.projectseele.visual;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.capability.EvaPilotCapability;
import com.projectseele.entity.*;
import com.projectseele.event.FirstBattleDirector;
import com.projectseele.registry.ModEntities;
import com.projectseele.world.EvaPilotResolver;
import com.projectseele.world.FirstBattleSavedData;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.level.GameRules;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.UUID;

/** Real mounted input, full completion, skip, missing-actor recovery and saved-session continuation. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class FirstBattleR10Review
{
    public static final boolean ENABLED="r10-firstbattle".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean MOVIE_ONLY=Boolean.getBoolean("projectseele.firstBattleMovieOnly");
    private static final boolean BERSERK_R52=Boolean.getBoolean("projectseele.firstBattleBerserkReviewR52");
    private static final boolean FOLLOWUP_ORDINARY_R52=Boolean.getBoolean("projectseele.firstBattleFollowupOrdinaryReviewR52");
    private static final boolean CONTROL_CAPTURE_R52=Boolean.getBoolean("projectseele.firstBattleControlRecoveryCaptureR52");
    public static volatile int reviewSequenceR52;
    private static boolean berserkFixtureR52(){return BERSERK_R52&&reviewSequenceR52==0;}
    public static volatile boolean clientTracked,clientMounted,clientCameraRestored,finished,reloadRequested,captureMovie,warming;
    public static volatile boolean capturePostStopR52;
    public static volatile boolean captureControlRecoveryR52;
    public static volatile int ordinaryOpticFramesR52,ordinaryDarkFramesR52,controlFramesR52,lockedControlFramesR52;
    public static volatile int heroId,action=-1,actionSerial,forward;
    public static volatile int clientFrames,droppedFrames;
    private static int age,stage,ticks,stageStart;
    private static EvaUnit01Entity hero;
    private static SachielEntity angel;
    private static ServerPlayer pilot;
    private static UUID heroUuid;
    private static float pilotHealth,hullHealth;
    private static Vec3 position;
    private static final JsonArray checks=new JsonArray();
    public static boolean ownsBerserkFixtureR52(EvaUnit01Entity unit)
    {
        return ENABLED&&berserkFixtureR52()&&unit==hero&&unit.isFirstBattleActive()&&unit.level() instanceof ServerLevel level
                &&level==level.getServer().overworld()&&level.getServer().getWorldPath(LevelResource.ROOT).normalize().getFileName().toString().equals("SEELE_FIRST_BATTLE_REVIEW_R10");
    }
    private static void check(String name,boolean passed,String detail)
    {
        JsonObject item=new JsonObject();item.addProperty("name",name);item.addProperty("passed",passed);item.addProperty("detail",detail);checks.add(item);
        if(!passed)throw new IllegalStateException(name+": "+detail);ProjectSeele.LOGGER.info("R10 BATTLE REVIEW PASS {} {}",name,detail);
    }
    private static void request(int next){action=next;actionSerial++;}
    private static SachielEntity enemy(ServerLevel level)
    {
        SachielEntity s=ModEntities.SACHIEL.get().create(level);s.moveTo(hero.getX(),-60,hero.getZ()+28,180,0);s.yBodyRot=s.yHeadRot=s.yBodyRotO=s.yHeadRotO=180;s.setNoAi(true);s.setPersistenceRequired();s.addTag("seele_first_battle_replay");s.setFirstBattleField(0);s.setHealth(s.getMaxHealth()*.32F+1);level.addFreshEntity(s);return s;
    }
    private static void forceEncounter(ServerLevel level)
    {
        angel=enemy(level);check("explicit_review_start_"+stage,FirstBattleDirector.tryStart(angel,hero,true),"same hero "+hero.getUUID());ticks=0;
    }
    private static void write(Path world,boolean passed,String failure)throws Exception
    {
        JsonObject result=new JsonObject();result.addProperty("passed",passed);result.add("checks",checks);result.addProperty("captured_frames",clientFrames);result.addProperty("dropped_frames",droppedFrames);result.addProperty("failure",failure);result.addProperty("clip_sha256",FirstBattleClip.fingerprint());
        Files.writeString(world.resolve("r10_first_battle_review.json"),result.toString());
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||finished||reloadRequested||event.phase!=TickEvent.Phase.END)return;var server=event.getServer();
        if(server.getPlayerList().getPlayers().isEmpty()||++age<80)return;
        Path world=server.getWorldPath(LevelResource.ROOT).normalize();if(!world.getFileName().toString().equals("SEELE_FIRST_BATTLE_REVIEW_R10"))throw new IllegalStateException("First-battle review is lab-only");
        ServerLevel level=server.overworld();var data=FirstBattleSavedData.get(level);
        try
        {
            if(age>9000)throw new IllegalStateException("Battle review deadline");
            if(stage==0)
            {
                pilot=server.getPlayerList().getPlayers().get(0);pilot.setGameMode(GameType.SURVIVAL);server.setFlightAllowed(true);
                Path resume=world.resolve("r10_resume_expected.json");
                if(Files.exists(resume))
                {
                    Path previous=world.resolve("r10_first_battle_review.json");if(Files.exists(previous))checks.addAll(JsonParser.parseString(Files.readString(previous)).getAsJsonObject().getAsJsonArray("checks"));
                    var expected=JsonParser.parseString(Files.readString(resume)).getAsJsonObject();heroUuid=UUID.fromString(expected.get("hero").getAsString());pilotHealth=expected.get("pilot_health").getAsFloat();hullHealth=expected.get("hull_health").getAsFloat();stage=20;ticks=0;return;
                }
                data.active=null;data.setDirty();
                level.getGameRules().getRule(GameRules.RULE_DOMOBSPAWNING).set(false,server);level.getGameRules().getRule(GameRules.RULE_MOBGRIEFING).set(false,server);level.getGameRules().getRule(GameRules.RULE_DAYLIGHT).set(false,server);level.setDayTime(6000);
                var old=new java.util.ArrayList<Mob>();for(var e:level.getAllEntities())if(e instanceof Mob mob)old.add(mob);for(var e:old)e.discard();
                for(BlockPos p:BlockPos.betweenClosed(-144,-61,-64,144,-61,240))level.setBlock(p,Blocks.GRAY_CONCRETE.defaultBlockState(),2);
                for(int z=-64;z<=240;z++)for(int x:new int[]{-32,32})level.setBlock(new BlockPos(x,-61,z),Blocks.WHITE_CONCRETE.defaultBlockState(),2);
                hero=ModEntities.EVA_UNIT01.get().create(level);hero.prepareForMotionLab();hero.setNoGravity(false);hero.moveTo(0,-60,0,0,0);hero.yBodyRot=hero.yHeadRot=0;hero.setOnGround(true);level.addFreshEntity(hero);heroUuid=hero.getUUID();heroId=hero.getId();
                pilot.teleportTo(level,0,-59,-18,0,0);pilot.setHealth(pilot.getMaxHealth());pilot.getFoodData().setFoodLevel(20);pilot.getCapability(EvaPilotCapability.DATA).ifPresent(c->c.setSynchronization(100));
                if(MOVIE_ONLY){hero.setNoAi(true);angel=enemy(level);warming=true;}
                stage=1;ticks=0;return;
            }
            ticks++;
            if(stage==1)
            {
                int warmup=MOVIE_ONLY?1200:20;
                if(ticks>warmup+300)throw new IllegalStateException("Client tracking or mounted chain deadline");
                if(ticks>20&&clientTracked&&EvaPilotResolver.controlTarget(pilot)!=hero){check("native_boarding",hero.boardFromExternalPlug(pilot,100),"real mounted pilot");ticks=0;return;}
                if(MOVIE_ONLY&&ticks%200==0)ProjectSeele.LOGGER.info("R18 MOVIE WARMUP ticks={} tracked={} mounted={} alive={} pos={}",ticks,clientTracked,clientMounted,hero.isAlive(),hero.position());
                if(ticks>(MOVIE_ONLY?1200:45)&&clientMounted)
                {
                    warming=false;hero.setNoAi(false);hero.setDeltaMovement(Vec3.ZERO);if(angel==null||!angel.isAlive())angel=enemy(level);angel.setFirstBattleField(0);angel.setHealth(angel.getMaxHealth()*.32F+1);pilotHealth=pilot.getHealth();hullHealth=hero.getHealth();request(com.projectseele.network.ServerboundEvaControlPacket.ACTION_MELEE);stage=2;ticks=0;captureMovie=true;return;
                }
            }
            else if(stage==2)
            {
                if(data.active!=null)
                {
                    stage=3;ticks=0;check("real_contact_trigger",data.active.eva.equals(heroUuid)&&data.active.angel.equals(angel.getUUID()),"ordinary attack crossed 32% health threshold");
                }
                else if(ticks>120)throw new IllegalStateException("Contact did not start the encounter: health="+angel.getHealth()+", field="+angel.getAtField()+", positions="+hero.position()+"/"+angel.position()+", ground="+hero.onGround());
            }
            else if(stage==3)
            {
                if(berserkFixtureR52()&&data.active!=null&&data.active.age==60)
                {
                    hero.reviewBerserkR34();EvaBerserkMotionR34.clear(hero);FirstBattleClip.applyKinematics(hero);hullHealth=hero.getHealth();
                    check("real_berserk_entry_r52",hero.isBerserk()&&hero.getPowerTicks()==0,"real beginBerserk; introduction hands pose ownership to active first-battle clip at age60");
                }
                if(data.active!=null&&data.active.age==FirstBattleClip.RETURN_TICK)
                    ProjectSeele.LOGGER.info("R52 RETURN WINDOW age={} firstBattleActive={} pilotControlLocked={} powered={} berserk={} reviewSequence={}",data.active.age,hero.isFirstBattleActive(),hero.pilotControlLockedForReviewR52(),hero.isPoweredOn(),hero.isBerserk(),reviewSequenceR52);
                if(data.active!=null&&data.active.age==40)
                {
                    pilot.hurt(level.damageSources().generic(),5);hero.hurt(level.damageSources().generic(),20);
                    check("directed_damage_protection",pilot.getHealth()==pilotHealth&&hero.getHealth()==hullHealth,"pilot and airframe preserved");
                }
                if(data.active==null)
                {
                    captureMovie=false;check("normal_completion",data.completedPilots.contains(pilot.getUUID())&&!angel.isAlive(),"first victory recorded");
                    check("original_hero_identity",hero.getUUID().equals(heroUuid),"no duplicate/replacement airframe");
                    check("restored_physics",!hero.isFirstBattleActive()&&!hero.noPhysics&&!hero.isNoGravity(),"normal collision and gravity");
                    check("pilot_still_mounted",EvaPilotResolver.controlTarget(pilot)==hero,"same rider");
                    if(berserkFixtureR52()){check("actual_berserk_stop_r52",!hero.isBerserk()&&hero.isPowerDepleted(),"EVA actual stop at complete; no movement pass inferred from ordinary powered mode");capturePostStopR52=true;}
                    else if(reviewSequenceR52==1)
                    {
                        check("followup_ordinary_completion_r52",hero.isPoweredOn()&&!hero.isBerserk()&&!hero.pilotControlLockedForReviewR52(),"second complete native clip releases powered pilot control");
                        if(CONTROL_CAPTURE_R52)
                        {
                            check("ordinary_client_optics_r52",ordinaryOpticFramesR52>0&&ordinaryDarkFramesR52==0,"actual ordinary client render frames="+ordinaryOpticFramesR52+" dark="+ordinaryDarkFramesR52);
                            captureControlRecoveryR52=true;
                        }
                    }
                    stage=4;ticks=0;
                }
            }
            else if(stage==4)
            {
                if(ticks==30){check("camera_restored",clientCameraRestored,"pilot camera returned");position=hero.position();forward=berserkFixtureR52()?0:1;}
                if(ticks==65)
                {
                    forward=0;
                    if(berserkFixtureR52())check("stopped_airframe_retains_rider_r52",!hero.isFirstBattleActive()&&EvaPilotResolver.controlTarget(pilot)==hero,"cinematic ownership released; stopped EVA is not falsely required to walk on depleted power");
                    else check("movement_after_film",hero.position().subtract(position).horizontalDistanceSqr()>4,"real W input moves the same EVA from "+position+" to "+hero.position());
                    if(reviewSequenceR52==1&&CONTROL_CAPTURE_R52)
                    {
                        captureControlRecoveryR52=false;
                        check("client_control_recovery_r52",controlFramesR52>0&&lockedControlFramesR52==0,"actual W render frames="+controlFramesR52+" locked or unpowered="+lockedControlFramesR52);
                    }
                    if(MOVIE_ONLY&&berserkFixtureR52()&&FOLLOWUP_ORDINARY_R52)
                    {
                        // Re-arm only this disposable review actor after its real stop
                        // was recorded. The next full clip uses ordinary powered mode.
                        reviewSequenceR52=1;hero.prepareForMotionLab();EvaShutdownR30.clear(hero);
                        hero.setDeltaMovement(Vec3.ZERO);hero.moveTo(0,-60,0,0,0);hero.setOnGround(true);
                        pilotHealth=pilot.getHealth();hullHealth=hero.getHealth();stage=3;
                        forceEncounter(level);captureMovie=true;
                        check("followup_ordinary_fixture_r52",hero.getUUID().equals(heroUuid)&&hero.isPoweredOn()&&!hero.isBerserk(),"same actor re-armed explicitly in disposable lab for separate ordinary full-completion/W check");
                        return;
                    }
                    if(MOVIE_ONLY){write(world,true,"");finished=true;return;}
                    stage=5;forceEncounter(level);
                }
            }
            else if(stage==5)
            {
                if(data.active!=null&&data.active.age>=80){position=hero.position();request(com.projectseele.network.ServerboundEvaControlPacket.ACTION_SKIP_FIRST_BATTLE);stage=6;ticks=0;}
            }
            else if(stage==6)
            {
                if(data.active==null)
                {
                    check("skip_completed",!angel.isAlive()&&!hero.isFirstBattleActive(),"outcome resolved and control released");
                    check("skip_keeps_location",hero.position().subtract(position).horizontalDistanceSqr()<2.25,"no long-distance skip teleport");stage=7;forceEncounter(level);
                }
            }
            else if(stage==7)
            {
                if(data.active!=null&&data.active.age>=70){angel.discard();stage=8;ticks=0;}
            }
            else if(stage==8)
            {
                if(data.active==null)
                {
                    check("missing_actor_recovery",!hero.isFirstBattleActive()&&!hero.noPhysics&&!hero.isNoGravity(),"interrupted sequence released the pilot");stage=9;forceEncounter(level);
                }
                else if(ticks>60)throw new IllegalStateException("Missing-actor lock not released");
            }
            else if(stage==9)
            {
                if(data.active!=null&&data.active.age>=140)
                {
                    JsonObject expected=new JsonObject();expected.addProperty("hero",heroUuid.toString());expected.addProperty("angel",angel.getUUID().toString());expected.addProperty("pilot_health",pilot.getHealth());expected.addProperty("hull_health",hero.getHealth());expected.addProperty("age",data.active.age);
                    Files.writeString(world.resolve("r10_resume_expected.json"),expected.toString());write(world,true,"awaiting reload continuation");reloadRequested=true;ProjectSeele.LOGGER.info("R10 BATTLE REVIEW RELOAD CHECKPOINT age={}",data.active.age);
                }
            }
            else if(stage==20)
            {
                if(level.getEntity(heroUuid) instanceof EvaUnit01Entity found){hero=found;heroId=hero.getId();}
                if(hero!=null&&data.active!=null&&data.active.age>160&&EvaPilotResolver.controlTarget(pilot)==hero)
                {
                    check("resumed_same_rider_and_hero",hero.getUUID().equals(heroUuid),"saved encounter continued at age "+data.active.age);stage=21;
                }
                else if(ticks>260)throw new IllegalStateException("Saved encounter did not resume");
            }
            else if(stage==21&&data.active==null)
            {
                check("resumed_completion",data.completedPilots.contains(pilot.getUUID())&&!hero.isFirstBattleActive(),"resumed scene completed");
                check("resumed_health_preserved",pilot.getHealth()==pilotHealth&&hero.getHealth()==hullHealth,"no reload/scene damage");write(world,true,"");finished=true;
            }
        }
        catch(Exception failure)
        {
            captureMovie=false;forward=0;ProjectSeele.LOGGER.error("R10 BATTLE REVIEW FAILED",failure);
            try{write(world,false,failure.toString());}catch(Exception ignored){}finished=true;
        }
    }
}

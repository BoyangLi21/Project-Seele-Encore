package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.capability.EvaPilotCapability;
import com.projectseele.entity.*;
import com.projectseele.registry.ModEntities;
import com.projectseele.world.EvaFleetSavedData;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.protocol.game.ClientboundTeleportEntityPacket;
import net.minecraft.server.level.*;
import net.minecraft.world.level.*;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** Isolated actors, production client inputs, bounded state-based combat review. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class CombatR31Review
{
    public static final boolean ENABLED="r31-combat".equals(System.getProperty("projectseele.regionalBuild",""));
    public static final boolean DUEL=Boolean.getBoolean("projectseele.combatDuel");
    public static final boolean NORMALS=Boolean.getBoolean("projectseele.combatNormals");
    private static final boolean OPTICS_R43=Boolean.getBoolean("projectseele.r43OpticsStates");
    public static final boolean EXCHANGE=Boolean.getBoolean("projectseele.combatExchange");
    public static final boolean RECOVERY=Boolean.getBoolean("projectseele.combatRecovery");
    public static final boolean WRECK=Boolean.getBoolean("projectseele.combatWreck");
    public static final boolean AWAKENING=Boolean.getBoolean("projectseele.combatAwakening");
    public static final boolean MOUTH_ONLY=Boolean.getBoolean("projectseele.combatMouth");
    public static final boolean CLOSE=Boolean.getBoolean("projectseele.r38Close"),CLOSE_FINALE=Boolean.getBoolean("projectseele.r38CloseFinale");
    public static final boolean PRONE_WRECK=Boolean.getBoolean("projectseele.r38ProneWreck");
    private static int closeCase;
    public static void inputR42(int action){input(action);}
    private static int finaleCompleteAt=-1;
    private static int opticsTrackedAt=-1;
    public static volatile boolean postFinaleOptics;
    public static final String WORLD="SEELE_FIELD_R31_REVIEW";
    public static final int X=12000,Z=12000,FLOOR=280;
    public static volatile boolean ready,tracked,mounted,done,jump,sprint;
    public static volatile int evaId,angelId,forward,strafe,warmFrames,stageTicks,inputAction,inputEpoch,stageOrdinal;
    public static volatile float heading;
    public static volatile String stageName="arena",photo="",failure="",mediaFolder="";
    public static volatile double maximumHandError;
    public static volatile int handSamples;
    private enum Stage {ARENA,TRACK,MOUNT,WARM,WALK_FORWARD,WALK_BACKWARD,NORMAL_EMPTY,NORMAL_CONTACT,NORMAL_HEAVY,NORMAL_MOVING,DUEL,AIR_STRIKE,AIR_SLAM,REACH,HOLD,THROW,REACTION,FINISH}
    private static Stage stage=Stage.ARENA;
    private static ServerPlayer pilot;private static EvaUnit01Entity eva;private static SachielEntity angel;
    private static Path world;private static ServerLevel level;
    private static int floorCursor,totalTicks,phase,airTicks,baseJump,attempts,contactHits,lastHitAt;
    private static float healthBefore,initialEvaHealth;private static double peak,maximumVictimLift,maximumVictimDistance,maximumEvaReactionMove;
    private static double previousObservedY,olderObservedY,observedVerticalPerTick;
    private static Vec3 stageOrigin,angelOrigin;private static boolean sawAction,sawThrown,sawDown;
    private static int falseAerial,normalFrames;
    private static boolean sawSilence,sawRoar,sawFinale,protectedHull=true;private static final Set<Integer> feralKinds=new HashSet<>();
    private static final JsonArray cases=new JsonArray(),trace=new JsonArray(),events=new JsonArray();
    private static final Map<Integer,UUID> fleetIds=new HashMap<>();

    /** Single transient test actor; a tag by itself never bypasses fleet ownership. */
    public static boolean ownsFixture(EvaUnit01Entity unit)
    {
        return ENABLED&&unit==eva&&unit.level() instanceof ServerLevel serverLevel
                &&serverLevel==serverLevel.getServer().overworld()&&unit.getTags().contains("seele_r31_combat_fixture")
                &&serverLevel.getServer().getWorldPath(LevelResource.ROOT).normalize().getFileName().toString().equals(WORLD);
    }

    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||done||event.phase!=TickEvent.Phase.END||!ready)return;
        var server=event.getServer();world=server.getWorldPath(LevelResource.ROOT).normalize();
        if(!world.getFileName().toString().equals(WORLD))throw new IllegalStateException("R31 combat fixture refused world: "+world);
        if(server.getPlayerList().getPlayers().isEmpty())return;
        try
        {
            if(++totalTicks>6500)throw new IllegalStateException("R31 total combat deadline");
            if(pilot==null)
            {
                level=server.overworld();pilot=server.getPlayerList().getPlayers().get(0);pilot.stopRiding();pilot.setGameMode(GameType.SPECTATOR);
                pilot.teleportTo(level,X+.5,FLOOR+3,Z+.5,0,0);server.setFlightAllowed(true);
                level.getGameRules().getRule(GameRules.RULE_DOMOBSPAWNING).set(false,server);level.getGameRules().getRule(GameRules.RULE_DAYLIGHT).set(false,server);level.setDayTime(6000);
                level.getGameRules().getRule(GameRules.RULE_WEATHER_CYCLE).set(false,server);level.setWeatherParameters(120000,0,false,false);
                for(int v=0;v<3;v++){final int slot=v;EvaFleetSavedData.get(server).canonicalId(v).ifPresent(id->fleetIds.put(slot,id));}
            }
            stageTicks++;stageOrdinal=stage.ordinal();stageName=stage.name().toLowerCase(Locale.ROOT);
            if(stage==Stage.ARENA){buildArena();return;}
            if(OPTICS_R43&&stage==Stage.TRACK&&tracked)
            {
                if(opticsTrackedAt<0)opticsTrackedAt=stageTicks;
                int observed=stageTicks-opticsTrackedAt;
                if(observed==40)photo="r43_optics_parked";
                if(observed<80)return;
                photo="";
                eva.setNervLogisticsLocked(false);eva.prepareForMotionLab();
            }
            if(OPTICS_R43&&stage==Stage.WARM)
            {
                if(stageTicks==25)photo="r43_optics_powered";
                if(stageTicks==65){photo="";eva.setHealth(50);EvaDorsalMechanism.afterBerserk(eva);}
                if(stageTicks==100)photo="r43_optics_post_berserk";
                if(stageTicks==140){photo="";eva.setHealth(eva.getMaxHealth());}
                if(stageTicks==175)photo="r43_optics_repaired";
                if(stageTicks>=210){record("optics_lifecycle_recorded",true,"states",4);finish("");}
                return;
            }
            if(TempoR43Review.ENABLED&&stage==Stage.WARM)
            {
                stageName="normal_tempo";
                if(TempoR43Review.tick(eva,pilot,stageTicks)){for(var row:TempoR43Review.results())cases.add(row);finish("");}
                return;
            }
            if(AWAKENING&&sawFinale&&eva!=null&&!eva.isFirstBattleActive()&&(angel==null||!angel.isAlive()||angel.isRemoved()))
            {
                if(Boolean.getBoolean("projectseele.r42OpticsReview"))
                {
                    if(finaleCompleteAt<0){finaleCompleteAt=stageTicks;postFinaleOptics=true;}
                    if(stageTicks-finaleCompleteAt==20)photo="r42_dormant_eyes";
                    if(stageTicks-finaleCompleteAt<40)return;
                    record("post_berserk_dark_eyes",!EvaDorsalMechanism.eyesEnabled(eva),"powered",eva.isPoweredOn()?1:0);
                }
                record("natural_awakening_to_finale",sawSilence&&sawRoar&&protectedHull&&(CLOSE_FINALE||feralKinds.size()>=3),"attack_kinds",feralKinds.size());
                var row=cases.get(cases.size()-1).getAsJsonObject();row.addProperty("silence",sawSilence);row.addProperty("roar",sawRoar);row.addProperty("protection",protectedHull);row.addProperty("automatic_finale",sawFinale);finish("");return;
            }
            if(stage==Stage.DUEL&&eva!=null&&!eva.isRemoved()&&angel!=null&&angel.isRemoved()&&angel.isSelfDestructing())
            {if(AWAKENING)throw new IllegalStateException("Angel exploded without the requested paired finale");finishDuel(true);finish("");return;}
            if(AWAKENING&&sawFinale&&eva!=null&&eva.isFirstBattleActive()&&angel!=null&&angel.isRemoved())
            {
                var encounter=com.projectseele.world.FirstBattleSavedData.get(level).active;
                if(encounter!=null&&encounter.deathResolved&&encounter.angel.equals(angel.getUUID())&&stageTicks<1900)return;
            }
            if(eva==null||eva.isRemoved()||angel==null||angel.isRemoved())throw new IllegalStateException("Review actor missing; no replacement or canonical lookup permitted");
            // Ridden vehicles report authoritative positions, while vanilla
            // clears their server velocity. Derive descent from those samples.
            observedVerticalPerTick=(eva.getY()-olderObservedY)*.5;olderObservedY=previousObservedY;previousObservedY=eva.getY();
            if(stageTicks>(StanceContactR41Review.ENABLED?2000:AWAKENING?1900:700))throw new IllegalStateException("Deadline in "+stage+" action="+EvaCombatR31.action(eva)+" eva="+eva.position()+" angel="+angel.position());
            if(totalTicks%2==0)sample();
            switch(stage)
            {
                case TRACK->{if(tracked&&stageTicks>20){pilot.setGameMode(GameType.SURVIVAL);pilot.setHealth(pilot.getMaxHealth());pilot.getFoodData().setFoodLevel(20);pilot.getCapability(EvaPilotCapability.DATA).ifPresent(c->c.setSynchronization(100));if(!eva.boardFromExternalPlug(pilot,100))throw new IllegalStateException("R31 real pilot boarding failed");next(Stage.MOUNT);}}
                case MOUNT->{if(mounted&&eva.getActivationTicks()==0&&stageTicks>20){if(eva.isAtFieldOn())input(4);next(Stage.WARM);}}
                case WARM->{if(PRONE_WRECK){if(phase==0){eva.toggleProne(pilot);phase=1;}if(stageTicks<65)return;if(!eva.isPilotProne())throw new IllegalStateException("Prone key was not accepted");}if(warmFrames>=35&&stageTicks>25){photo="01_ready";if(RECOVERY||CLOSE||StanceContactR41Review.ENABLED){arrange(23);initialEvaHealth=eva.getHealth();next(Stage.REACTION);}else if(EXCHANGE){arrange(MOUTH_ONLY?100:CLOSE_FINALE?12:39);if(CLOSE_FINALE)angel.setHealth(250);angel.setNoAi(MOUTH_ONLY||CLOSE_FINALE);if(!MOUTH_ONLY&&!CLOSE_FINALE)angel.setTarget(eva);initialEvaHealth=eva.getHealth();if(AWAKENING){eva.setHealth(70);pilot.getCapability(EvaPilotCapability.DATA).ifPresent(c->c.setSynchronization(10));eva.hurt(angel.damageSources().mobAttack(angel),60);if(!eva.isBerserk()||eva.getHealth()!=50)throw new IllegalStateException("Natural 50 HP awakening did not trigger");}else if(Boolean.getBoolean("projectseele.combatBerserk"))eva.reviewBerserkR34();next(Stage.DUEL);}else next(Stage.WALK_FORWARD);}}
                case WALK_FORWARD->{forward=1;if(eva.getZ()-stageOrigin.z>=10){record("real_forward",true,"distance",eva.getZ()-stageOrigin.z);forward=0;photo="02_forward";next(Stage.WALK_BACKWARD);}}
                case WALK_BACKWARD->{forward=-1;if(stageOrigin.z-eva.getZ()>=7){record("real_backward",true,"distance",stageOrigin.z-eva.getZ());forward=0;arrange(NORMALS?100:23);next(NORMALS?Stage.NORMAL_EMPTY:Stage.AIR_STRIKE);}}
                case NORMAL_EMPTY,NORMAL_CONTACT,NORMAL_HEAVY,NORMAL_MOVING->normalAttack();
                case DUEL->{if(AWAKENING)awakening();else duel();}
                case AIR_STRIKE->airborne(false);
                case AIR_SLAM->airborne(true);
                case REACH->
                {
                    if(stageTicks==15){contactEvent("before_reach");input(3);}
                    if(EvaCombatR31.action(eva)==EvaCombatR31.REACH){sawAction=true;if(stageTicks%4==0)contactEvent("reach");}
                    if(EvaCombatR31.action(eva)==EvaCombatR31.HOLD){contactEvent("hold_started");record("real_grab",true,"start_distance",stageOrigin.distanceTo(angelOrigin));photo="05_grab_contact";next(Stage.HOLD);}
                    else if(sawAction&&EvaCombatR31.action(eva)==EvaCombatR31.NONE&&stageTicks>25)
                        throw new IllegalStateException("Real grab key failed: "+new Gson().toJson(CombatReachR31.errors(eva,angel,0))+" eva="+eva.position()+" angel="+angel.position());
                }
                case HOLD->
                {
                    if(EvaCombatR31.action(eva)!=EvaCombatR31.HOLD)throw new IllegalStateException("Held actor released before throw input");
                    maximumVictimLift=Math.max(maximumVictimLift,angel.getY()-(FLOOR+1));
                    if(stageTicks>=26){contactEvent("before_throw");photo="06_two_hand_hold";input(3);next(Stage.THROW);}
                }
                case THROW->
                {
                    var b=CombatFeelR31.beat(angel);if(b!=null&&b.kind()==CombatFeelR31.THROWN){if(!sawThrown){contactEvent("released");photo="07_actual_throw";}sawThrown=true;}
                    if(b!=null&&b.kind()==CombatFeelR31.DOWN){sawDown=true;photo="08_angel_grounded";}
                    maximumVictimDistance=Math.max(maximumVictimDistance,angel.position().subtract(angelOrigin).horizontalDistance());
                    if(sawThrown&&sawDown&&angel.onGround()&&EvaCombatR31.action(eva)==EvaCombatR31.NONE&&!CombatFeelR31.restrained(angel))
                    {
                        record("real_throw_landed",maximumVictimDistance>8,"victim_displacement",maximumVictimDistance);record("grip_lift",maximumVictimLift>.5,"lift",maximumVictimLift);
                        arrange(23);initialEvaHealth=eva.getHealth();next(Stage.REACTION);
                    }
                }
                case REACTION->{if(StanceContactR41Review.ENABLED){if(StanceContactR41Review.tick(eva,angel,pilot,stageTicks)){record(StanceContactR41Review.ARTICULATION?"locomotion_and_jump_r42":"stance_and_contact",StanceContactR41Review.passed(),"native_cases",StanceContactR41Review.ARTICULATION?1:6);finish("");}}else reaction();}
                case FINISH->finish("");
                default->{}
            }
        }
        catch(Exception error){ProjectSeele.LOGGER.error("R31 native combat review failed",error);finish(error.toString());}
    }

    private static void buildArena()
    {
        int width=513,length=513,total=width*length;
        for(int n=0;n<500&&floorCursor<total;n++,floorCursor++)
        {
            int x=X-256+floorCursor%width,z=Z-256+floorCursor/width;BlockPos p=new BlockPos(x,FLOOR,z);
            level.getChunkAt(p);if(level.getBlockEntity(p)!=null)throw new IllegalStateException("Arena intersects authored block entity");
            for(int y=FLOOR+1;y<level.getMaxBuildHeight();y++)if(!level.getBlockState(new BlockPos(x,y,z)).isAir())throw new IllegalStateException("Review arena has an overhead obstacle at "+x+","+y+","+z);
            level.setBlock(p,(Math.floorMod(x-X,16)==0||Math.floorMod(z-Z,16)==0?Blocks.LIGHT_GRAY_CONCRETE:Blocks.GRAY_CONCRETE).defaultBlockState(),2);
        }
        if(floorCursor<total)return;
        // Only actors authored by this exact fixture are eligible for stale cleanup.
        var stale=new ArrayList<net.minecraft.world.entity.Entity>();for(var e:level.getAllEntities())if(e.getTags().contains("seele_r31_combat_fixture"))stale.add(e);stale.forEach(net.minecraft.world.entity.Entity::discard);
        int variant=Integer.getInteger("projectseele.combatVariant",1);
        eva=(variant==0?ModEntities.EVA_UNIT00.get():variant==2?ModEntities.EVA_UNIT02.get():variant>=3?ModEntities.EVA_PROTOTYPE.get():ModEntities.EVA_UNIT01.get()).create(level);angel=ModEntities.SACHIEL.get().create(level);
        if(eva instanceof EvaPrototypeEntity un)un.setUNSerial(variant-3);
        if(eva==null||angel==null)throw new IllegalStateException("Combat test actor factory");
        eva.addTag("seele_r31_combat_fixture");eva.addTag("seele_motion_lab");
        if(OPTICS_R43)eva.setNervLogisticsLocked(true);else eva.prepareForMotionLab();
        eva.setNoGravity(false);eva.setNoAi(false);eva.setPersistenceRequired();
        CompoundTag tag=new CompoundTag();angel.saveWithoutId(tag);tag.putBoolean("FirstBattleUsed",!AWAKENING);tag.putInt("SachielSelfDestruct",-1);angel.load(tag);angel.setFirstBattleField(0);angel.setNoAi(true);angel.addTag("seele_r31_combat_fixture");angel.setPersistenceRequired();
        eva.moveTo(X+.5,FLOOR+1,Z-30.5,0,0);eva.yBodyRot=eva.yHeadRot=0;eva.setOnGround(true);
        angel.moveTo(X+.5,FLOOR+1,Z+80.5,180,0);angel.yBodyRot=angel.yHeadRot=180;
        if(!level.addFreshEntity(eva)||!level.addFreshEntity(angel))throw new IllegalStateException("Review actor spawn rejected");
        angel.setFirstBattleField(Float.parseFloat(System.getProperty("projectseele.combatFieldEnergy","0")));
        evaId=eva.getId();angelId=angel.getId();pilot.teleportTo(level,X+.5,FLOOR+2,Z-45.5,0,0);next(Stage.TRACK);
    }

    /** Reposition only between independent cases, never to make a failed contact pass. */
    static void arrangeR41(double range)
    {
        arrange(range);
        // Independent contact cases must not inherit a cancelled ragdoll's
        // root height or bounds. Continuous recovery is reviewed separately.
        eva.setPos(eva.getX(),FLOOR+1,eva.getZ());eva.refreshDimensions();eva.setOnGround(true);
        angel.refreshDimensions();
        pilot.connection.send(new net.minecraft.network.protocol.game.ClientboundMoveVehiclePacket(eva));
    }
    private static void arrange(double distance)
    {
        forward=0;jump=false;EvaCombatR31.clear(eva);CombatFeelR31.clear(eva);CombatFeelR31.clear(angel);angel.cancelStrikeR31();angel.setTarget(null);
        eva.setDeltaMovement(Vec3.ZERO);angel.setDeltaMovement(Vec3.ZERO);eva.setYRot(0);eva.setYBodyRot(0);eva.setYHeadRot(0);heading=0;
        angel.teleportTo(eva.getX(),FLOOR+1,eva.getZ()+distance);angel.setYRot(180);angel.yRotO=180;angel.yBodyRot=angel.yBodyRotO=angel.yHeadRot=angel.yHeadRotO=180;angel.setOnGround(true);
        pilot.connection.send(new ClientboundTeleportEntityPacket(angel));healthBefore=angel.getHealth();
    }
    private static void airborne(boolean heavy)
    {
        if(phase==0&&stageTicks>15&&eva.onGround()){jump=true;baseJump=eva.getJumpSequence();peak=eva.getY();phase=1;}
        if(phase>=1){peak=Math.max(peak,eva.getY());if(!eva.onGround())airTicks++;}
        if(phase==1&&!eva.onGround()){jump=false;phase=2;}
        boolean early=Boolean.getBoolean("projectseele.combatEarlyAir");
        if(phase==2&&(early?observedVerticalPerTick>.25&&eva.getY()>FLOOR+10:observedVerticalPerTick<-.25&&eva.getY()<FLOOR+36))
        {input(heavy?2:1);phase=3;photo=heavy?"04_air_slam":"03_air_strike";}
        if(phase==3&&EvaCombatR31.active(eva)){sawAction=true;phase=4;}
        if(phase>=3&&sawAction&&eva.onGround()&&!EvaCombatR31.active(eva)&&stageTicks>30)
        {
            double damage=healthBefore-angel.getHealth();boolean pass=eva.getJumpSequence()>baseJump&&airTicks>4&&peak>FLOOR+8&&damage>0;
            record(heavy?"real_jump_slam":"real_jump_strike",pass,"damage",damage);
            var last=cases.get(cases.size()-1).getAsJsonObject();last.addProperty("jump_delta",eva.getJumpSequence()-baseJump);last.addProperty("peak_y",peak);last.addProperty("air_ticks",airTicks);last.addProperty("landed",eva.onGround());
            arrange(heavy?20:23);next(heavy?Stage.REACH:Stage.AIR_SLAM);
        }
    }
    private static void normalAttack()
    {
        jump=false;forward=stage==Stage.NORMAL_MOVING&&stageTicks<110?1:0;
        if(stageTicks>=15&&stageTicks<125&&(stage==Stage.NORMAL_HEAVY?(stageTicks==15||stageTicks==85):stageTicks%6==3))input(stage==Stage.NORMAL_HEAVY?2:1);
        if(eva.getOrdinaryAttackStage()>=0||eva.isHeavyMotionActive())normalFrames++;
        if(EvaCombatR31.active(eva))falseAerial++;
        if(stageTicks>=150)
        {
            record(stage.name().toLowerCase(Locale.ROOT),falseAerial==0&&normalFrames>0&&(stage!=Stage.NORMAL_CONTACT&&stage!=Stage.NORMAL_HEAVY||healthBefore-angel.getHealth()>0),"unexpected_air_ticks",falseAerial);
            var row=cases.get(cases.size()-1).getAsJsonObject();row.addProperty("normal_action_ticks",normalFrames);row.addProperty("actual_damage",healthBefore-angel.getHealth());
            falseAerial=normalFrames=0;
            switch(stage)
            {
                case NORMAL_EMPTY->{arrange(23);next(Stage.NORMAL_CONTACT);}
                case NORMAL_CONTACT->{arrange(23);next(Stage.NORMAL_HEAVY);}
                case NORMAL_HEAVY->{arrange(100);next(Stage.NORMAL_MOVING);}
                default->{if(DUEL){arrange(25);angel.setNoAi(false);angel.setTarget(eva);initialEvaHealth=eva.getHealth();next(Stage.DUEL);}else next(Stage.FINISH);}
            }
        }
    }
    private static void duel()
    {
        Vec3 difference=angel.position().subtract(eva.position());heading=(float)Math.toDegrees(Math.atan2(-difference.x,difference.z));
        double range=difference.horizontalDistance();
        forward=range>25?1:range<17?-1:0;
        jump=false;
        strafe=EXCHANGE&&stageTicks%150>=105?(stageTicks/150%2==0?1:-1):0;
        if(stageTicks%100>70&&angel.isStrikeActive())forward=-1;
        if(stageTicks>15&&stageTicks%6==0&&(!EXCHANGE||range<35))input(stageTicks%120==0?2:1);
        if(stageTicks>=550||eva.getHealth()<30||angel.getHealth()<80)
        {
            finishDuel(false);
            angel.setNoAi(true);angel.setTarget(null);forward=strafe=0;next(Stage.FINISH);
        }
    }
    private static void awakening()
    {
        forward=strafe=0;heading=eva.getYRot();sawFinale|=eva.isFirstBattleActive();
        if(MOUTH_ONLY&&stageTicks>=96){record("native_mouth_open_close_render",sawSilence&&sawRoar&&protectedHull,"native_ticks",stageTicks);finish("");return;}
        if(EvaBerserkMotionR34.silent(eva))
        {sawSilence=true;if(eva.isPoweredOn()||eva.getPowerTicks()!=0||EvaBerserkMotionR34.mouth(eva,0)>0)throw new IllegalStateException("Silence phase kept power or opened mouth");photo="r37_silence";}
        if(EvaBerserkMotionR34.kind(eva)==1&&EvaBerserkMotionR34.mouth(eva,0)>.8F){sawRoar=true;photo="r37_roar";}
        if(EvaBerserkMotionR34.striking(eva))feralKinds.add(EvaBerserkMotionR34.kind(eva));
        if(eva.isBerserk()&&!eva.isFirstBattleActive())
        {
            if(stageTicks==20||stageTicks==110)eva.hurt(angel.damageSources().mobAttack(angel),100);
            if(eva.getHealth()!=50||EvaShutdownR30.wreck(eva)){protectedHull=false;throw new IllegalStateException("Plot-protected hull was damaged");}
        }
        if(MOUTH_ONLY&&stageTicks==76)photo="r37_mouth_fully_open";
        if(stageTicks>120&&!eva.isBerserk()&&!sawFinale)throw new IllegalStateException("Berserk ended before the low-health finale");
    }
    private static void finishDuel(boolean defeated)
    {
        double dealt=healthBefore-angel.getHealth(),received=initialEvaHealth-eva.getHealth();
        boolean supported=true;for(var sample:trace){var row=sample.getAsJsonObject();if(row.get("phase").getAsString().equals("DUEL")&&row.getAsJsonArray("eva").get(1).getAsDouble()<FLOOR)supported=false;}
        record("continuous_live_duel",dealt>0&&received>0&&supported,"damage_dealt",dealt);
        var row=cases.get(cases.size()-1).getAsJsonObject();row.addProperty("damage_received",received);row.addProperty("ticks",stageTicks);row.addProperty("natural_self_destruct",defeated);row.addProperty("floor_retained",supported);forward=0;
    }
    private static void reaction()
    {
        if(CLOSE){closeContacts();return;}
        if(PRONE_WRECK&&stageTicks<20)return;
        if(PRONE_WRECK&&stageTicks==20){EvaShutdownR30.fail(eva);sawDown=true;lastHitAt=stageTicks;}
        var b=CombatFeelR31.beat(eva);maximumEvaReactionMove=Math.max(maximumEvaReactionMove,eva.position().subtract(stageOrigin).horizontalDistance());
        if(b!=null&&b.kind()==CombatFeelR31.DOWN){sawDown=true;photo="10_eva_down";}
        if(eva.getHealth()<healthBefore-.01){contactHits++;lastHitAt=stageTicks;healthBefore=eva.getHealth();photo="09_eva_actual_hit";}
        if(WRECK&&sawDown)
        {
            if(!EvaShutdownR30.wreck(eva)){if(Boolean.getBoolean("projectseele.combatBerserk"))eva.reviewBerserkR34();EvaShutdownR30.fail(eva);lastHitAt=stageTicks;}
            if(stageTicks-lastHitAt>40&&!com.projectseele.physics.CombatBodyDynamics.active(eva))
            {
                CompoundTag saved=new CompoundTag();eva.saveWithoutId(saved);photo="physical_wreck";
                record("physical_wreck_retains_pose",saved.contains("R35RestBounds")&&!saved.getCompound("R35RestBounds").isEmpty()&&eva.getBoundingBox().getYsize()<40&&eva.getY()>FLOOR-1&&!eva.isBerserk()&&!angel.canAttack(eva),"resting_height",eva.getBoundingBox().getYsize());next(Stage.FINISH);
            }
            return;
        }
        // Keep the original two-hit requirement. A first hit can already
        // knock the body down; recovering from it must not end the review
        // before the second independent incoming strike can be attempted.
        if(sawDown&&contactHits>=2&&!CombatFeelR31.restrained(eva)&&eva.onGround())
        {
            record("angel_actual_hits_and_knockdown",contactHits>=2&&maximumEvaReactionMove>.5&&eva.getY()>=FLOOR+.5,"actual_damage",initialEvaHealth-eva.getHealth());
            var last=cases.get(cases.size()-1).getAsJsonObject();last.addProperty("hits",contactHits);last.addProperty("eva_displacement",maximumEvaReactionMove);next(Stage.FINISH);return;
        }
        if(!angel.isStrikeActive()&&!CombatFeelR31.restrained(eva)&&stageTicks-lastHitAt>15)
        {
            if(attempts>=8)throw new IllegalStateException("Sachiel real hit review exhausted attempts; hits="+contactHits+" down="+sawDown);
            // A new independent incoming strike begins at a recorded contact distance.
            angel.teleportTo(eva.getX(),FLOOR+1,eva.getZ()+23);angel.setYRot(180);angel.yBodyRot=angel.yHeadRot=180;pilot.connection.send(new ClientboundTeleportEntityPacket(angel));
            if(angel.beginStrike(eva,attempts%2==0?SachielStrike.JAB:SachielStrike.OVERHEAD)){attempts++;healthBefore=eva.getHealth();lastHitAt=stageTicks;}
        }
    }
    private static void closeContacts()
    {
        int[] modes={SachielStrike.SHOVE,SachielStrike.HOOK,SachielStrike.JAB,SachielStrike.OVERHEAD};double[] ranges={14,14,18,20};
        if(phase==0)
        {
            arrange(ranges[closeCase]);eva.setHealth(eva.getMaxHealth());healthBefore=eva.getHealth();lastHitAt=stageTicks;phase=1;return;
        }
        if(phase==1&&stageTicks-lastHitAt>=20)
        {if(angel.beginStrike(eva,modes[closeCase])){phase=2;lastHitAt=stageTicks;}return;}
        if(phase==2&&stageTicks-lastHitAt>SachielStrike.duration(modes[closeCase])+12)
        {
            double damage=healthBefore-eva.getHealth();record("close_contact_mode_"+modes[closeCase],damage>0,"damage",damage);
            cases.get(cases.size()-1).getAsJsonObject().addProperty("start_range",ranges[closeCase]);
            if(++closeCase==modes.length){next(Stage.FINISH);return;}phase=0;
        }
    }
    private static void input(int action){inputAction=action;inputEpoch++;}
    private static void next(Stage next)
    {
        stage=next;stageTicks=0;phase=0;airTicks=0;sawAction=false;sawThrown=false;sawDown=false;stageOrigin=eva==null?Vec3.ZERO:eva.position();angelOrigin=angel==null?Vec3.ZERO:angel.position();
        previousObservedY=olderObservedY=stageOrigin.y;observedVerticalPerTick=0;
        if(next==Stage.REACTION){healthBefore=eva.getHealth();contactHits=attempts=0;lastHitAt=-100;}
        ProjectSeele.LOGGER.info("R31 COMBAT phase={} eva={} angel={}",next,stageOrigin,angelOrigin);
    }
    private static void record(String name,boolean passed,String metric,double value)
    {var r=new JsonObject();r.addProperty("name",name);r.addProperty("passed",passed);r.addProperty(metric,value);cases.add(r);}
    private static JsonArray vector(Vec3 p){var a=new JsonArray();a.add(p.x);a.add(p.y);a.add(p.z);return a;}
    private static void contactEvent(String name)
    {
        var r=new JsonObject();r.addProperty("event",name);r.addProperty("tick",totalTicks);r.add("eva",vector(eva.position()));r.add("victim",vector(angel.position()));r.add("left_contact",vector(EvaCombatR31.grip(eva,angel,true,1)));r.add("right_contact",vector(EvaCombatR31.grip(eva,angel,false,1)));r.add("reach",new Gson().toJsonTree(CombatReachR31.errors(eva,angel,0)));events.add(r);
    }
    public static void aerialContact(EvaUnit01Entity source,Vec3 previous,Vec3 hand)
    {
        if(!ENABLED||source!=eva||angel==null)return;
        var r=new JsonObject();r.addProperty("event","server_air_contact");r.addProperty("tick",stageTicks);r.addProperty("action_age",EvaCombatR31.age(eva,0));r.addProperty("ground",eva.onGround());r.addProperty("distance",eva.distanceTo(angel));r.add("eva",vector(eva.position()));r.add("previous",vector(previous));r.add("hand",vector(hand));r.add("angel",vector(angel.position()));r.addProperty("inside",angel.getBoundingBox().inflate(2).contains(previous));r.addProperty("clip",angel.getBoundingBox().inflate(2).clip(previous,hand).isPresent());r.addProperty("health",angel.getHealth());events.add(r);
    }
    private static void sample()
    {
        var physics=new JsonObject();physics.addProperty("event","body_dynamics");physics.addProperty("phase",stage.name());physics.addProperty("tick",stageTicks);
        physics.addProperty("eva_mode",com.projectseele.physics.CombatBodyDynamics.phase(eva));physics.addProperty("angel_mode",com.projectseele.physics.CombatBodyDynamics.phase(angel));
        physics.addProperty("eva_bounds_height",eva.getBoundingBox().getYsize());physics.addProperty("angel_bounds_height",angel.getBoundingBox().getYsize());events.add(physics);
        var r=new JsonObject();r.addProperty("phase",stage.name());r.addProperty("tick",stageTicks);r.addProperty("action",EvaCombatR31.action(eva));r.addProperty("ordinary",eva.getOrdinaryAttackStage());r.addProperty("live_phase",eva.combatPhaseR31());r.addProperty("confirmed_airborne",eva.isVisuallyAirborneForRender());r.addProperty("observed_vertical_per_tick",observedVerticalPerTick);r.addProperty("server_velocity_y",eva.getDeltaMovement().y);r.add("eva",vector(eva.position()));r.add("angel",vector(angel.position()));r.addProperty("eva_health",eva.getHealth());r.addProperty("angel_health",angel.getHealth());r.addProperty("eva_ground",eva.onGround());r.addProperty("angel_ground",angel.onGround());r.addProperty("angel_strike",angel.isStrikeActive()?angel.strikeMode():0);r.addProperty("angel_strike_age",angel.strikeAge(0));var eb=CombatFeelR31.beat(eva);var ab=CombatFeelR31.beat(angel);r.addProperty("eva_reaction",eb==null?0:eb.kind());r.addProperty("angel_reaction",ab==null?0:ab.kind());trace.add(r);
    }
    private static void finish(String error)
    {
        jump=false;forward=0;failure=error;
        try
        {
            boolean ids=true;for(var entry:fleetIds.entrySet())ids&=EvaFleetSavedData.get(level.getServer()).canonicalId(entry.getKey()).filter(entry.getValue()::equals).isPresent();
            var r=new JsonObject();r.addProperty("error",error);r.addProperty("fleet_ids_unchanged",ids);r.addProperty("hand_samples",handSamples);r.addProperty("maximum_hand_error_metres",Double.isFinite(maximumHandError)?maximumHandError:-1);r.addProperty("media",mediaFolder);
            int exchangeCases=AWAKENING&&Boolean.getBoolean("projectseele.r42OpticsReview")?2:1;
            boolean all=error.isEmpty()&&ids&&(TempoR43Review.ENABLED?cases.size()==6:OPTICS_R43?cases.size()==1:StanceContactR41Review.ENABLED?cases.size()==1:CLOSE?cases.size()==4:EXCHANGE||RECOVERY?cases.size()==exchangeCases:NORMALS?cases.size()>=6:cases.size()>=7&&handSamples>5&&maximumHandError<.8);
            for(var c:cases)all&=c.getAsJsonObject().get("passed").getAsBoolean();r.addProperty("passed",all);r.add("cases",cases);r.add("contacts",events);r.add("trace",trace);if(StanceContactR41Review.ENABLED)r.add("stance_r41",StanceContactR41Review.details());
            Path out=world.resolve("Review");Files.createDirectories(out);Files.writeString(out.resolve((NORMALS?"r32_normal_":"r31_combat_")+(all?"pass":"failure")+".json"),new GsonBuilder().setPrettyPrinting().create().toJson(r));
        }
        catch(Exception report){ProjectSeele.LOGGER.error("R31 combat report",report);}
        finally
        {
            if(pilot!=null){pilot.stopRiding();pilot.setGameMode(GameType.CREATIVE);pilot.teleportTo(level,X+.5,FLOOR+2,Z-80.5,0,0);}
            if(eva!=null)eva.discard();if(angel!=null)angel.discard();done=true;
        }
    }
    private CombatR31Review() {}
}

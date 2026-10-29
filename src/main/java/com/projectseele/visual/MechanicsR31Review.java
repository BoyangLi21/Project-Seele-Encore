package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import com.projectseele.registry.*;
import com.projectseele.world.*;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.*;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicIntegerArray;

/** Original UN identities only; independent empty scrap fixture never replaces a fleet capsule. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class MechanicsR31Review
{
    public static final boolean ENABLED="r31-mechanics".equals(System.getProperty("projectseele.regionalBuild",""));
    public static final boolean WRECK_PICKUP=Boolean.getBoolean("projectseele.mechanicsWreckPickup");
    public static volatile boolean wreckLeg;
    public static String flightPrefix(){return wreckLeg?"horizontal_wreck_":"horizontal_";}
    public static final boolean TRANSPORT_ONLY=Boolean.getBoolean("projectseele.mechanicsTransportOnly");
    public static final boolean TRANSPORT=TRANSPORT_ONLY||Boolean.getBoolean("projectseele.mechanicsTransport");
    public static final double SOCKET_ERROR_LIMIT=.25;
    public static final String WORLD="SEELE_FIELD_R31_REVIEW";
    public static final UUID[] unitIds=new UUID[2],plugIds=new UUID[2];
    public static final int[] baseRevision={-1,-1},resetRevision={-1,-1};
    public static final AtomicIntegerArray baselineFrames=new AtomicIntegerArray(2),resetFrames=new AtomicIntegerArray(2),visiblePlugFrames=new AtomicIntegerArray(2),modelFrames=new AtomicIntegerArray(2);
    public static final AtomicIntegerArray transportSamples=new AtomicIntegerArray(3);
    public static final AtomicIntegerArray cradleSamples=new AtomicIntegerArray(1),headFacingSamples=new AtomicIntegerArray(1);
    public static volatile double maximumTransportSocketError;
    public static volatile double maximumHeadForwardY=-1;
    public static volatile boolean ready,done,clientFailed;
    public static volatile int serial,actorId,inputEpoch,inputAction,scrapId;
    public static volatile float lookPitch;
    public static volatile String stageName="locate",photo="",mediaFolder="",clientError="",transportPhase="IDLE";
    public static volatile Vec3 observerTarget;
    public static final Set<String> capturedPhotos=java.util.concurrent.ConcurrentHashMap.newKeySet();
    private enum Stage {LOCATE,BASE_RESET,OPEN,BOARD,CROUCH,PRONE,ARMED,DIRTY_RESET,VERIFY_RESET,SCRAP,TRANSPORT,TRANSPORT_RESET,FINISH}
    private static Stage stage=Stage.LOCATE;
    private static ServerLevel level;private static ServerPlayer player;private static Path world;
    private static int ticks,total,phase,observerFrameStart;private static boolean requested;private static EvaPrototypeEntity eva;
    private static EntryPlugCarrierEntity scrap,normal,occupied;private static TrainingPilotEntity occupant;
    private static final JsonObject checks=new JsonObject();private static final JsonArray sockets=new JsonArray();
    private static final Set<String> observed=new HashSet<>();
    private static void check(String name,boolean passed){checks.addProperty(name,passed);if(!passed)throw new IllegalStateException(name);}
    private static void next(Stage next){stage=next;stageName=next.name().toLowerCase(Locale.ROOT);ticks=phase=0;requested=false;lookPitch=0;ProjectSeele.LOGGER.info("R31 MECHANICS phase={} serial={}",next,serial);}
    private static void input(int action){inputAction=action;inputEpoch++;}
    private static void reset(){player.server.getCommands().performPrefixedCommand(player.createCommandSourceStack().withPermission(4),"seele military reset 0"+serial);}
    private static boolean home(){return eva!=null&&eva.position().distanceTo(UNRecoveryR22.home(level,serial))<.05;}
    private static String stateInfo()
    {
        if(eva==null)return "serial="+serial+" eva=unloaded transport="+UNAirLiftR29.phaseName(level,serial);
        var capsule=UNPlugDirector.capsule(eva);var pilot=eva.getPilotEntity();
        return "serial="+serial+" transport="+UNAirLiftR29.phaseName(level,serial)+" plugStage="+(capsule==null?-1:capsule.getInsertionStage())
                +" stance="+eva.rifleStanceLevel(1)+" crouch="+eva.isPilotCrouching()+" prone="+eva.isPilotProne()+" activation="+eva.getActivationTicks()
                +" bow="+EvaDorsalMechanism.bow(eva)+" open="+EvaDorsalMechanism.open(eva)+" pilot="+(pilot==null?"none":pilot.getUUID())
                +" locked="+eva.isNervLogisticsLocked()+" shutdown="+EvaShutdownR30.mode(eva)+" powered="+eva.isPoweredOn();
    }
    private static void observer()
    {
        player.removeAllEffects();
        var inventory=player.getInventory();int empty=-1;
        for(int i=0;i<9;i++)if(inventory.getItem(i).isEmpty()){empty=i;break;}
        if(empty<0)for(int i=9;i<36;i++)if(inventory.getItem(i).isEmpty()){inventory.setItem(i,inventory.getItem(inventory.selected));inventory.setItem(inventory.selected,net.minecraft.world.item.ItemStack.EMPTY);empty=inventory.selected;break;}
        if(empty<0)throw new IllegalStateException("Review observer needs one empty inventory slot; no inventory items were discarded");
        inventory.selected=empty;inventory.setChanged();player.containerMenu.broadcastChanges();player.connection.send(new net.minecraft.network.protocol.game.ClientboundSetCarriedItemPacket(empty));
        var home=UNRecoveryR22.home(level,serial);player.teleportTo(level,home.x+18,home.y+47,home.z+55,135,5);player.getAbilities().flying=true;player.onUpdateAbilities();observerTarget=home.add(0,30,0);
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||!ready||done||event.phase!=TickEvent.Phase.END)return;
        var server=event.getServer();world=server.getWorldPath(LevelResource.ROOT).normalize();
        if(!world.getFileName().toString().equals(WORLD))throw new IllegalStateException("R31 mechanics world boundary");
        if(server.getPlayerList().getPlayers().isEmpty())return;
        try
        {
            if(level==null)
            {
                level=server.getLevel(FacilitySchemaV2.DIMENSION);if(level==null)throw new IllegalStateException("Project dimension missing");player=server.getPlayerList().getPlayers().get(0);player.stopRiding();player.setGameMode(GameType.CREATIVE);player.setInvulnerable(true);player.getInventory().add(new net.minecraft.world.item.ItemStack(ModItems.UN_SATELLITE_PHONE.get()));
                for(int i=0;i<2;i++){unitIds[i]=UNRecoveryR22.identity(level,i);check("registered_original_un"+i,unitIds[i]!=null);}observer();
                level.getGameRules().getRule(net.minecraft.world.level.GameRules.RULE_WEATHER_CYCLE).set(false,server);level.setWeatherParameters(120000,0,false,false);
            }
            ticks++;total++;stageName=stage.name().toLowerCase(Locale.ROOT);level.resetEmptyTime();
            if(total>10500||ticks>(stage==Stage.TRANSPORT?4200:1400))throw new IllegalStateException("Mechanical deadline "+stage+" "+stateInfo());
            if(clientFailed)throw new IllegalStateException("Actual render witness: "+clientError);
            if(ticks%20==1)UNCommandR29.receive(player,"status",serial,0,0);
            eva=level.getEntity(unitIds[serial]) instanceof EvaPrototypeEntity e?e:null;if(eva!=null)actorId=eva.getId();
            var plug=eva==null?null:UNPlugDirector.capsule(eva);
            if(plug!=null){if(plugIds[serial]==null)plugIds[serial]=plug.getUUID();else check("same_original_capsule_"+serial,plugIds[serial].equals(plug.getUUID()));}
            switch(stage)
            {
                case LOCATE->{if(eva!=null&&plug!=null){baseRevision[serial]=eva.mechanicalRevisionR30()+1;reset();next(Stage.BASE_RESET);}}
                case BASE_RESET->{if(home()&&eva.mechanicalRevisionR30()==baseRevision[serial]&&plug!=null&&plug.getInsertionStage()==EntryPlugCarrierEntity.STAGE_SUSPENDED&&baselineFrames.get(serial)>=10&&visiblePlugFrames.get(serial)>2){photo="un"+serial+"_baseline";next(TRANSPORT_ONLY?Stage.TRANSPORT:Stage.OPEN);}}
                case OPEN->
                {
                    if(!requested){UNCommandR29.receive(player,"drain",serial,0,0);requested=true;}
                    var bay=serial==0?MilitaryR07Director.state(level).phase:UNAnnexR20.state(level).phase;
                    if(bay==MilitaryR07Director.Phase.DRY&&ticks%20==0)UNCommandR29.receive(player,"door",serial,0,0);
                    if(bay==MilitaryR07Director.Phase.OPEN&&!eva.isNervLogisticsLocked())
                    {
                        String shot="un"+serial+"_open_model";
                        if(phase==0){observer();photo="";observerFrameStart=modelFrames.get(serial);ticks=0;phase=1;}
                        if(phase==1&&ticks>=30&&modelFrames.get(serial)-observerFrameStart>=3){photo=shot;phase=2;}
                        if(!capturedPhotos.contains(shot))break;
                        var at=UNPlugDirector.dock(eva).transformPoint(EntryPlugKinematics.HATCH_PORTAL_CENTRE_P).add(4,-1.6,0);player.teleportTo(level,at.x,at.y,at.z,90,0);observerTarget=null;UNCommandR29.receive(player,"board",serial,0,0);next(Stage.BOARD);
                    }
                }
                case BOARD->{if(eva.getPilotEntity()==player&&player.getVehicle()==plug&&plug.getVehicle()==eva&&eva.getActivationTicks()==0
                        &&EvaDorsalMechanism.open(eva)<.001F&&EvaDorsalMechanism.bow(eva)<.001F&&!eva.isNervLogisticsLocked()&&!EvaShutdownR30.disabled(eva))
                    {check("real_original_ride_chain_"+serial,true);input(1);next(Stage.CROUCH);}}
                case CROUCH->{if(eva.isPilotCrouching()&&eva.rifleCrouchBlend(1)>.75&&ticks>25){photo="un"+serial+"_crouch_before_reset";input(3);next(Stage.PRONE);}}
                case PRONE->{if(eva.isPilotProne()&&eva.rifleStanceLevel(1)>2.7&&ticks>30){photo="un"+serial+"_prone_before_reset";eva.selectMotionLabWeapon(EvaUnit01Entity.WEAPON_RIFLE);lookPitch=-18;next(Stage.ARMED);lookPitch=-18;}}
                case ARMED->{lookPitch=-18;if(eva.rifleReadyBlend(1)>.75&&ticks>45){photo="un"+serial+"_raised_rifle_before_reset";next(Stage.DIRTY_RESET);}}
                case DIRTY_RESET->{resetRevision[serial]=eva.mechanicalRevisionR30()+1;reset();next(Stage.VERIFY_RESET);}
                case VERIFY_RESET->
                {
                    if(home()&&!player.isPassenger()&&!requested){observer();requested=true;}
                    if(home()&&eva.mechanicalRevisionR30()==resetRevision[serial]&&plug!=null&&plug.getInsertionStage()==EntryPlugCarrierEntity.STAGE_SUSPENDED&&resetFrames.get(serial)>=10)
                    {
                        check("reset_state_cleared_"+serial,!eva.isPilotProne()&&!eva.isPilotCrouching()&&eva.getWeapon()==EvaUnit01Entity.WEAPON_FISTS&&!EvaAirTransportR31.active(eva));
                        check("dock_canonical_"+serial,plug.getCanonicalTransform().translation().distanceTo(UNPlugDirector.dock(eva).translation())<.02);
                        photo="un"+serial+"_after_reset";
                        if(serial==0){serial=1;observer();next(Stage.LOCATE);}else{serial=0;next(Stage.SCRAP);}
                    }
                }
                case SCRAP->scrapCase();
                case TRANSPORT->transportCase(plug);
                case TRANSPORT_RESET->{if(home()&&plug!=null&&plug.getInsertionStage()==EntryPlugCarrierEntity.STAGE_SUSPENDED&&!UNAirLiftR29.active(level,0)&&ticks>60)next(Stage.FINISH);}
                case FINISH->finish("");
            }
        }
        catch(Exception error){ProjectSeele.LOGGER.error("R31 mechanics failed",error);finish(error.toString());}
    }
    private static EntryPlugCarrierEntity fixture(Vec3 position,int stage)
    {
        var p=ModEntities.ENTRY_PLUG_CARRIER.get().create(level);if(p==null)throw new IllegalStateException("Capsule fixture factory");
        var tag=new CompoundTag();p.saveWithoutId(tag);tag.putBoolean("IndependentUN",true);tag.putInt("InsertionStage",stage);tag.putBoolean("ShellVisible",true);p.load(tag);p.addTag("seele_r31_scrap_fixture");p.snapCanonicalTransformR31(new RigidTransform(position,0,0,0,1));
        if(!level.addFreshEntity(p))throw new IllegalStateException("Capsule fixture refused");return p;
    }
    private static void scrapCase()
    {
        if(phase==0)
        {
            Vec3 at=UNAirLiftR29.apron(level,0).add(42,0,12);level.getChunkAt(BlockPos.containing(at));int surfaceY=level.getHeight(net.minecraft.world.level.levelgen.Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,(int)Math.floor(at.x),(int)Math.floor(at.z+5));
            check("scrap_fixture_has_real_floor",!level.getBlockState(new BlockPos((int)Math.floor(at.x),surfaceY-1,(int)Math.floor(at.z+5))).getCollisionShape(level,new BlockPos((int)Math.floor(at.x),surfaceY-1,(int)Math.floor(at.z+5))).isEmpty());at=new Vec3(at.x,surfaceY+EntryPlugKinematics.BODY_OBB_HALF_EXTENTS.y,at.z);
            normal=fixture(at.add(18,0,0),EntryPlugCarrierEntity.STAGE_SUSPENDED);occupied=fixture(at.add(-18,0,0),EntryPlugCarrierEntity.STAGE_FIELD_LANDED);scrap=fixture(at,EntryPlugCarrierEntity.STAGE_FIELD_LANDED);scrapId=scrap.getId();
            occupant=ModEntities.TRAINING_PILOT.get().create(level);if(occupant==null)throw new IllegalStateException("Occupant fixture factory");occupant.addTag("seele_r31_scrap_fixture");occupant.setNoAi(true);occupant.setTrainingStage(TrainingPilotEntity.STAGE_STANDBY);occupant.setPos(at);level.addFreshEntity(occupant);check("occupied_fixture_boarded",occupant.startRiding(occupied,true));
            check("normal_capsule_damage_inhibited",!normal.hurt(player.damageSources().playerAttack(player),100)&&!normal.isRemoved());
            check("occupied_capsule_damage_inhibited",!occupied.hurt(player.damageSources().playerAttack(player),100)&&!occupied.isRemoved());
            Vec3 surface=at.add(1.2,0,5);player.teleportTo(level,surface.x+3,surface.y-player.getEyeHeight(),surface.z,90,0);observerTarget=surface;photo="empty_field_capsule_before_hit";phase=1;ticks=0;return;
        }
        if(phase==1&&ticks>25){input(4);phase=2;}
        if(phase==2&&scrap.isRemoved())
        {
            check("real_lmb_destroyed_only_landed_empty",EntryPlugDisposalR31.destroyed(level,scrap.getUUID())&&!normal.isRemoved()&&!occupied.isRemoved());
            occupant.stopRiding();occupant.discard();normal.discard();occupied.discard();scrap=null;normal=null;occupied=null;occupant=null;observer();next(TRANSPORT?Stage.TRANSPORT:Stage.FINISH);
        }
    }
    private static void transportCase(EntryPlugCarrierEntity plug)
    {
        if(eva==null)return;
        if(!requested){UNCommandR29.receive(player,wreckLeg?"recover":"deliver",0,6400,-5820);requested=true;}
        String phase=UNAirLiftR29.phaseName(level,0);transportPhase=phase;observed.add(phase);check("horizontal_transport_not_faulted",!phase.equals("HOLD"));
        if(ticks%2==0&&!player.isPassenger()){Vec3 at=eva.position().add(105,85,80);player.teleportTo(level,at.x,at.y,at.z,130,5);observerTarget=eva.position().add(0,65,0);}
        if(phase.equals("CLAMP"))photo=flightPrefix()+"00_clamp";
        float pitch=EvaAirTransportR31.pitch(eva,1);if(pitch>38&&pitch<52){observed.add("45_DEGREES");photo=flightPrefix()+"01_45deg";}if(pitch>89){observed.add("90_DEGREES");photo=flightPrefix()+"02_90deg";}
        if(wreckLeg&&EvaAirTransportR31.active(eva)&&!phase.equals("RELEASE"))
        {
            var axis=EvaBodyPose.sample(eva,1).matrix("torso_lower").transformDirection(new org.joml.Vector3f(0,1,0)).normalize();
            check("wreck_not_stood_up_in_transit",Math.abs(axis.y)<.22F);
        }
        if(phase.equals("RELEASE"))photo=flightPrefix()+"03_unload";
        if(plug!=null&&plug.isLockedToEva()&&ticks%4==0)
        {var r=new JsonObject();r.addProperty("phase",phase);r.addProperty("pitch",pitch);r.addProperty("canonical_socket_error",plug.getCanonicalTransform().translation().distanceTo(EntryPlugKinematics.lockedTransform(eva).translation()));sockets.add(r);}
        if(!UNAirLiftR29.active(level,0)&&ticks>200)
        {
            for(String p:List.of("CLAMP","45_DEGREES","90_DEGREES","RELEASE"))check("transport_observed_"+p,observed.contains(p));
            check("actual_transport_socket_sample_count",transportSamples.get(0)>=30);
            check("actual_45_degree_socket_samples",transportSamples.get(1)>=3);
            check("actual_90_degree_socket_samples",transportSamples.get(2)>=3);
            check("actual_transport_socket_aligned",Double.isFinite(maximumTransportSocketError)&&maximumTransportSocketError<=SOCKET_ERROR_LIMIT);
            check("actual_support_geometry_submitted",cradleSamples.get(0)>=30);
            check("horizontal_face_down_sample_count",headFacingSamples.get(0)>=3);
            check("horizontal_face_points_to_ground",maximumHeadForwardY<-.9);
            for(String shot:List.of("horizontal_00_clamp","horizontal_01_45deg","horizontal_02_90deg","horizontal_03_unload"))check("actual_render_photo_"+shot,capturedPhotos.contains(wreckLeg?shot.replace("horizontal_","horizontal_wreck_"):shot));
            check("transport_original_capsule",plug!=null&&plug.getUUID().equals(plugIds[0]));
            if(WRECK_PICKUP&&!wreckLeg)
            {
                eva.hurt(level.damageSources().fellOutOfWorld(),100000);check("wreck_pickup_disabled",EvaShutdownR30.wreck(eva));
                wreckLeg=true;requested=false;ticks=0;observed.clear();maximumHeadForwardY=-1;headFacingSamples.set(0,0);return;
            }
            if(wreckLeg)check("wreck_delivery_keeps_damage",EvaShutdownR30.wreck(eva)&&eva.getHealth()==0);
            reset();next(Stage.TRANSPORT_RESET);
        }
    }
    private static void finish(String error)
    {
        try
        {
            for(int i=0;i<2;i++)if(unitIds[i]!=null)checks.addProperty("original_unit_retained_"+i,unitIds[i].equals(UNRecoveryR22.identity(level,i)));
            checks.addProperty("passed",error.isEmpty()&&!clientFailed);checks.addProperty("error",error);checks.addProperty("media",mediaFolder);checks.addProperty("transport_requested",TRANSPORT);checks.addProperty("scope",TRANSPORT_ONLY?"original_un00_transport_only":TRANSPORT?"both_un_reset_scrap_and_un00_transport":"both_un_reset_and_scrap");checks.addProperty("gate_revision",3);checks.addProperty("transport_orientation","face_down");checks.addProperty("actual_socket_error_limit_metres",SOCKET_ERROR_LIMIT);checks.addProperty("actual_socket_samples",transportSamples.get(0));checks.addProperty("actual_45_degree_samples",transportSamples.get(1));checks.addProperty("actual_90_degree_samples",transportSamples.get(2));checks.addProperty("maximum_actual_socket_error_metres",Double.isFinite(maximumTransportSocketError)?maximumTransportSocketError:-1);checks.addProperty("actual_cradle_draw_samples",cradleSamples.get(0));checks.addProperty("actual_90deg_head_facing_samples",headFacingSamples.get(0));checks.addProperty("maximum_90deg_head_forward_y",maximumHeadForwardY);checks.add("server_socket_samples",sockets);
            Path out=world.resolve("Review");Files.createDirectories(out);Files.writeString(out.resolve((TRANSPORT_ONLY?"r31_mechanics_transport_":"r31_mechanics_")+(error.isEmpty()&&!clientFailed?"pass":"failure")+".json"),new GsonBuilder().setPrettyPrinting().create().toJson(checks));
        }
        catch(Exception reporting){ProjectSeele.LOGGER.error("R31 mechanics report",reporting);}
        finally
        {
            if(occupant!=null){occupant.stopRiding();occupant.discard();}if(scrap!=null)scrap.discard();if(normal!=null)normal.discard();if(occupied!=null)occupied.discard();
            done=true;observerTarget=null;
        }
    }
    private MechanicsR31Review() {}
}

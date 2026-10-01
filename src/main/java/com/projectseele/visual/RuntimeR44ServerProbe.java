package com.projectseele.visual;

import com.google.gson.*;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.projectseele.ProjectSeele;
import com.projectseele.capability.EvaPilotCapability;
import com.projectseele.entity.*;
import com.projectseele.registry.ModEntities;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.player.PlayerEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** Dedicated-server evidence; ordinary actors and actual client packets, with no motion-lab mode. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class RuntimeR44ServerProbe
{
    private static final boolean ENABLED=Boolean.getBoolean("projectseele.r44NetworkReview");
    private static final String WORLD="SEELE_R44_NETWORK_REVIEW";
    private static final Map<UUID,EvaUnit01Entity> ACTORS=new HashMap<>();
    private static final JsonArray SAMPLES=new JsonArray();
    private static int cursor;
    private static boolean ready;
    private static final Set<UUID> FIRST_OWNER_TICK=new HashSet<>();
    private static final Map<UUID,Set<String>> FIRST_AI_STAGES=new HashMap<>();
    private static final Map<UUID,Set<Integer>> PASSENGER_REPLAYS=new HashMap<>();
    public static boolean ownsFixture(EvaUnit01Entity e)
    {
        if(!ENABLED||!e.getTags().contains("seele_r44_network_fixture")||!(e.level() instanceof net.minecraft.server.level.ServerLevel level))return false;
        safe(level.getServer());return true;
    }
    private static void safe(MinecraftServer server)
    {
        if(!server.getWorldPath(LevelResource.ROOT).normalize().getFileName().toString().equals(WORLD)
                ||!"127.0.0.1".equals(server.getLocalIp()))throw new IllegalStateException("R44 network probe refuses non-local or owner server");
    }
    @SubscribeEvent public static void register(RegisterCommandsEvent event)
    {
        if(!ENABLED)return;
        event.getDispatcher().register(Commands.literal("seele").then(Commands.literal("review_r44").requires(s->s.hasPermission(4))
                .then(Commands.literal("actor").then(Commands.argument("variant",IntegerArgumentType.integer(0,4))
                        .executes(c->spawn(c.getSource().getPlayerOrException(),IntegerArgumentType.getInteger(c,"variant")))))
                .then(Commands.literal("finish").executes(c->{safe(c.getSource().getServer());write(c.getSource().getServer());return 1;}))));
    }
    @SubscribeEvent public static void login(PlayerEvent.PlayerLoggedInEvent event)
    {
        if(!ENABLED||!(event.getEntity() instanceof ServerPlayer player))return;
        safe(player.server);player.server.getPlayerList().op(player.getGameProfile());
        player.setGameMode(GameType.CREATIVE);player.teleportTo(player.server.overworld(),12000.5,281,11880.5,0,0);
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||event.phase!=TickEvent.Phase.END)return;
        var server=event.getServer();safe(server);var level=server.overworld();
        if(!ready)
        {
            level.setDayTime(6000);level.setWeatherParameters(6000,0,false,false);
            int width=193,depth=401,total=width*depth;
            for(int count=0;count<1600&&cursor<total;count++,cursor++)
            {
                int x=11904+cursor%width,z=11840+cursor/width;BlockPos p=new BlockPos(x,280,z);
                level.getChunkAt(p);
                if(level.getBlockEntity(p)!=null)throw new IllegalStateException("QA floor intersects a block entity");
                // Full-cube, equal-friction grid makes actual sole motion legible
                // in the guarded QA world; no user-world floor is recoloured.
                var material=Math.floorMod(x,16)==0||Math.floorMod(z,16)==0?Blocks.WHITE_CONCRETE:
                        ((Math.floorDiv(x,16)+Math.floorDiv(z,16))&1)==0?Blocks.LIGHT_GRAY_CONCRETE:Blocks.GRAY_CONCRETE;
                level.setBlock(p,material.defaultBlockState(),2);
            }
            ready=cursor==total;
        }
        if(ready)
        {
            var stale=new ArrayList<net.minecraft.world.entity.Entity>();
            for(var actor:level.getAllEntities())if(actor.getTags().contains("seele_r44_network_fixture")&&!ACTORS.containsValue(actor))stale.add(actor);
            for(var actor:stale){actor.ejectPassengers();actor.discard();}
        }
        if(server.getTickCount()%2!=0)return;
        for(var entry:ACTORS.entrySet())
        {
            var e=entry.getValue();if(e.isRemoved())continue;
            if(Boolean.getBoolean("projectseele.r44PassengerReplay"))
            {
                for(int at:new int[]{20,120,550})if(e.tickCount>=at&&PASSENGER_REPLAYS.computeIfAbsent(e.getUUID(),key->new HashSet<>()).add(at))
                {
                    ownerLifecycle(server,e,"before_repeated_vanilla_passenger_packet_"+at);
                    var pilot=e.getPilotEntity();if(!(pilot instanceof ServerPlayer player))throw new IllegalStateException("Passenger replay lost its real mounted pilot");
                    player.connection.send(new net.minecraft.network.protocol.game.ClientboundSetPassengersPacket(e));
                }
            }
            if(FIRST_OWNER_TICK.add(e.getUUID()))ownerLifecycle(server,e,"first_observed_server_tick");
            JsonObject row=new JsonObject();row.addProperty("tick",level.getGameTime());row.addProperty("variant",EvaGameplayMotionR32.variant(e));
            row.addProperty("entity",e.getId());row.addProperty("ordinary",e.getOrdinaryAttackStage());row.addProperty("phase",e.getOrdinaryAttackProgress(0));
            row.addProperty("gait",e.rifleGaitPhase(0));row.addProperty("run",e.rifleRunBlend(0));row.addProperty("owns",EvaGameplayMotionR32.owns(e,0));row.addProperty("weapon",e.getWeapon());
            row.add("actual_owner_inputs",EvaGameplayMotionR32.ownerDiagnosticR44(e,0));
            int knife=e.getKnifeMotionType(0);row.addProperty("knife_type",knife);row.addProperty("knife_phase",e.getKnifeMotionProgress(knife,0));row.addProperty("kick_active",e.isKickMotionActive(0));row.addProperty("kick_phase",e.getKickAttackProgress(0));
            row.addProperty("shutdown",EvaShutdownR30.mode(e));row.addProperty("activation",e.getActivationTicks());row.addProperty("ground",e.onGround());
            row.addProperty("x",e.getX());row.addProperty("y",e.getY());row.addProperty("z",e.getZ());SAMPLES.add(row);
        }
    }
    private static int spawn(ServerPlayer player,int variant)
    {
        safe(player.server);
        if(!ready){player.sendSystemMessage(Component.literal("R44_QA_WAIT"));return 0;}
        var level=player.server.overworld();var prior=ACTORS.get(player.getUUID());
        if(ACTORS.isEmpty())
        {
            player.stopRiding();var stale=new ArrayList<net.minecraft.world.entity.Entity>();
            for(var actor:level.getAllEntities())if(actor.getTags().contains("seele_r44_network_fixture"))stale.add(actor);
            for(var actor:stale){actor.ejectPassengers();actor.discard();}
            ProjectSeele.LOGGER.info("R44 network fixture retired prior test actors: {}",stale.size());
        }
        if(prior!=null&&!prior.isRemoved()&&EvaGameplayMotionR32.variant(prior)==variant)
        {player.sendSystemMessage(Component.literal("R44_QA_ACTOR "+prior.getId()+" "+variant));return 1;}
        var old=ACTORS.remove(player.getUUID());player.stopRiding();
        if(old!=null){for(var passenger:new ArrayList<>(old.getPassengers()))passenger.discard();old.discard();}
        var e=(variant==0?ModEntities.EVA_UNIT00.get():variant==2?ModEntities.EVA_UNIT02.get():variant>=3?ModEntities.EVA_PROTOTYPE.get():ModEntities.EVA_UNIT01.get()).create(level);
        if(e==null)throw new IllegalStateException("QA actor factory");
        e.addTag("seele_r44_network_fixture");
        if(e instanceof EvaPrototypeEntity un)un.setUNSerial(variant-3);
        // Start with the normal entity defaults. This deliberately does not call
        // prepareForMotionLab(), which changes the live animation path.
        CompoundTag tag=new CompoundTag();e.saveWithoutId(tag);tag.putBoolean("SeeleEntryPlugInserted",true);tag.putInt("SeelePowerTicks",6000);
        tag.putInt("SeeleWeapon","knife".equals(System.getProperty("projectseele.r44NetworkWeapon","fists"))?EvaUnit01Entity.WEAPON_KNIFE:EvaUnit01Entity.WEAPON_FISTS);
        tag.putInt("SeeleActivationTicks",0);tag.putBoolean("SeeleNervLogisticsLocked",false);tag.putInt("R30Shutdown",0);e.load(tag);
        ownerLifecycle(player.server,e,"after_fixture_load_before_mount");
        e.setHealth(e.getMaxHealth());e.setPersistenceRequired();e.moveTo(12000.5,281,11890.5,0,0);e.setOnGround(true);
        if(!level.addFreshEntity(e))throw new IllegalStateException("QA actor was rejected before boarding");
        player.teleportTo(level,12000.5,283,11876.5,0,0);
        player.getCapability(EvaPilotCapability.DATA).ifPresent(c->c.setSynchronization(100));
        if(!e.boardFromExternalPlug(player,100))throw new IllegalStateException("Normal entry-plug boarding failed");
        ownerLifecycle(player.server,e,"after_normal_boarding");
        ACTORS.put(player.getUUID(),e);player.sendSystemMessage(Component.literal("R44_QA_ACTOR "+e.getId()+" "+variant));
        ProjectSeele.LOGGER.info("R44 normal network actor mounted: variant={} entity={} motionLabPreview={}",variant,e.getId(),e.getMotionLabPhysicsPreview());
        return 1;
    }
    private static void write(MinecraftServer server)
    {
        try{Files.writeString(server.getWorldPath(LevelResource.ROOT).resolve("r44_network_server.json"),new Gson().toJson(SAMPLES));}
        catch(Exception failure){throw new IllegalStateException(failure);}
    }
    private static void ownerLifecycle(MinecraftServer server,EvaUnit01Entity e,String stage)
    {
        safe(server);JsonObject row=new JsonObject();row.addProperty("stage",stage);row.addProperty("variant",EvaGameplayMotionR32.variant(e));
        row.addProperty("entity_uuid",e.getUUID().toString());row.addProperty("entity_id",e.getId());row.addProperty("tick",e.level().getGameTime());row.addProperty("entity_tick",e.tickCount);
        row.add("actual_owner_inputs",EvaGameplayMotionR32.ownerDiagnosticR44(e,0));
        try{Files.writeString(server.getWorldPath(LevelResource.ROOT).resolve("r44_actor_owner_lifecycle.jsonl"),row+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);}
        catch(Exception error){throw new IllegalStateException("Could not save actual QA actor owner lifecycle",error);}
    }
    public static void firstActorTick(EvaUnit01Entity e,String stage)
    {
        if(!ENABLED||e.level().isClientSide||!e.getTags().contains("seele_r44_network_fixture"))return;
        if(FIRST_AI_STAGES.computeIfAbsent(e.getUUID(),key->new HashSet<>()).add(stage))
            ownerLifecycle(((net.minecraft.server.level.ServerLevel)e.level()).getServer(),e,stage);
    }
    private RuntimeR44ServerProbe() {}
}

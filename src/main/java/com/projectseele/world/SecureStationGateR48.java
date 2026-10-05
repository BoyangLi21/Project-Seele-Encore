package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.item.NervAccessCardR44;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.util.*;

/** NERV swipes control exactly two native gate bodies, never the public free network. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class SecureStationGateR48
{
    private static final BlockPos READER=new BlockPos(-355,82,700),EXIT=new BlockPos(-355,82,702);
    private static final Map<BlockPos,String> GATES=Map.of(new BlockPos(-361,81,701),"mtr:ticket_barrier_entrance_1",
            new BlockPos(-360,81,701),"mtr:ticket_barrier_exit_1");
    private static final Map<MinecraftServer,Boolean> ENABLED=new WeakHashMap<>();
    private record Swipe(UUID caller,InteractionHand hand,long start) { }
    private static final class State { long until;Swipe swipe; }
    private static final Map<ServerLevel,State> STATES=new WeakHashMap<>();
    private static boolean enabled(ServerLevel level)
    {
        if(!level.dimension().equals(FacilitySchemaV2.DIMENSION))return false;
        return ENABLED.computeIfAbsent(level.getServer(),server->{
            var file=server.getWorldPath(LevelResource.ROOT).resolve("r48_secure_station_gate.json");
            if(!Files.isRegularFile(file))return false;
            try
            {
                var root=JsonParser.parseString(Files.readString(file)).getAsJsonObject();var expected=new HashSet<BlockPos>();
                for(var raw:root.getAsJsonArray("gates")){var a=raw.getAsJsonArray();if(a.size()!=3)return false;expected.add(new BlockPos(a.get(0).getAsInt(),a.get(1).getAsInt(),a.get(2).getAsInt()));}
                return root.get("schema").getAsInt()==48&&root.get("installed").getAsBoolean()
                        &&root.get("dimension").getAsString().equals("projectseele:geofront")
                        &&root.get("clearance").getAsInt()==1&&expected.equals(GATES.keySet());
            }
            catch(Exception failure){ProjectSeele.LOGGER.error("R48 finite subway checkpoint receipt rejected",failure);return false;}
        });
    }
    private static boolean owned(ServerLevel level,BlockPos pos,BlockState state)
    {return enabled(level)&&GATES.getOrDefault(pos,"").equals(BuiltInRegistries.BLOCK.getKey(state.getBlock()).toString());}
    /** Consume the native collision/fare handler only inside this exact secure installation. */
    public static boolean collision(ServerLevel level,BlockPos pos,BlockState block,Entity actor)
    {if(!owned(level,pos,block))return false;maintain(level);return true;}
    public static boolean scheduled(ServerLevel level,BlockPos pos,BlockState block)
    {if(!owned(level,pos,block))return false;maintain(level);return true;}
    private static boolean complete(ServerLevel level)
    {
        if(!(level.getBlockEntity(READER) instanceof NervAccessReaderEntityR44))return false;
        for(var entry:GATES.entrySet())if(!level.hasChunkAt(entry.getKey())||!owned(level,entry.getKey(),level.getBlockState(entry.getKey())))return false;
        return true;
    }
    private static boolean card(ServerPlayer player,InteractionHand hand)
    {return player.getItemInHand(hand).getItem() instanceof NervAccessCardR44 card&&card.clearance()>=1;}
    @SubscribeEvent(priority=EventPriority.HIGHEST)
    public static void use(PlayerInteractEvent.RightClickBlock event)
    {
        if(!(event.getEntity() instanceof ServerPlayer player)||!(event.getLevel() instanceof ServerLevel level)
                ||!enabled(level)||!event.getPos().equals(READER)&&!event.getPos().equals(EXIT))return;
        event.setCanceled(true);event.setCancellationResult(InteractionResult.CONSUME);
        if(player.isSpectator()||player.distanceToSqr(Vec3.atCenterOf(event.getPos()))>16||!complete(level))return;
        var state=STATES.computeIfAbsent(level,key->new State());
        if(event.getPos().equals(EXIT))
        {
            // Release is usable only from the real inside standing buffer.
            if(event.getHand()!=InteractionHand.MAIN_HAND||player.getZ()<702||!level.getBlockState(EXIT).is(Blocks.STONE_BUTTON))return;
            state.until=level.getGameTime()+120;maintain(level);
            event.setCanceled(false);return; // Vanilla button pulse remains the physical acknowledgement.
        }
        InteractionHand hand=event.getHand();
        if(!card(player,hand)&&card(player,InteractionHand.OFF_HAND))hand=InteractionHand.OFF_HAND;
        if(!card(player,hand))
        {player.displayClientMessage(net.minecraft.network.chat.Component.literal("请手持NERV通行证刷卡。"),true);return;}
        if(state.swipe==null)
        {
            state.swipe=new Swipe(player.getUUID(),hand,level.getGameTime());
            visual(level,level.getGameTime(),1,player.getItemInHand(hand).getItem() instanceof NervAccessCardR44 card?card.clearance():0);
            player.startUsingItem(hand);player.swing(hand,true);
        }
    }
    private static void maintain(ServerLevel level)
    {
        if(!complete(level))return;var state=STATES.computeIfAbsent(level,key->new State());long now=level.getGameTime();
        if(state.swipe!=null&&now-state.swipe.start>=6)
        {
            var player=level.getServer().getPlayerList().getPlayer(state.swipe.caller);
            boolean permit=player!=null&&player.serverLevel()==level&&!player.isSpectator()
                    &&player.distanceToSqr(Vec3.atCenterOf(READER))<=16&&card(player,state.swipe.hand);
            if(permit)state.until=now+120;
            if(player!=null)player.displayClientMessage(net.minecraft.network.chat.Component.literal(permit?"NERV · 闸机已开启。":"刷卡中断，请保持通行证和读卡距离。"),true);
            level.playSound(null,READER,permit?net.minecraft.sounds.SoundEvents.NOTE_BLOCK_PLING.value():net.minecraft.sounds.SoundEvents.NOTE_BLOCK_BASS.value(),net.minecraft.sounds.SoundSource.BLOCKS,.35F,permit?1.3F:.75F);
            visual(level,-1,permit?2:3,permit?1:0);state.swipe=null;
        }
        if(state.swipe==null&&level.getBlockEntity(READER) instanceof NervAccessReaderEntityR44 reader
                &&reader.indicator()!=0&&now>reader.saveWithoutMetadata().getLong("IndicateUntil"))visual(level,-1,0,0);
        boolean open=now<state.until;
        boolean wasOpen=GATES.keySet().stream().anyMatch(q->!level.getBlockState(q).equals(PublicStationGatesR44.withOpen(level.getBlockState(q),"closed")));
        if(!open&&wasOpen)
        {
            // Presence prolongs an already opened passage, never admits through a closed one.
            var area=new AABB(-361,81,700.8,-359,83,702.2);
            if(!level.getEntities((Entity)null,area,e->e.isAlive()&&!e.isSpectator()).isEmpty()){state.until=now+10;open=true;}
        }
        for(var q:GATES.keySet())
        {
            var old=level.getBlockState(q);var wanted=PublicStationGatesR44.withOpen(old,open?"open":"closed");
            if(!old.equals(wanted))level.setBlockAndUpdate(q,wanted);
        }
    }
    private static void visual(ServerLevel level,long start,int status,int tier)
    {
        if(!(level.getBlockEntity(READER) instanceof NervAccessReaderEntityR44 reader))return;
        var tag=reader.saveWithoutMetadata();tag.putBoolean("Linked",false);tag.putLong("SwipeAt",start);
        tag.putInt("Status",status);tag.putInt("Presented",tier);tag.putLong("IndicateUntil",level.getGameTime()+32);
        reader.load(tag);reader.setChanged();level.sendBlockUpdated(READER,level.getBlockState(READER),level.getBlockState(READER),2);
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||event.getServer().getTickCount()%2!=0)return;
        var level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level!=null&&enabled(level))maintain(level);
    }
    private SecureStationGateR48() { }
}

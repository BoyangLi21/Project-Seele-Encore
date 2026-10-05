package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.ButtonBlock;
import net.minecraft.world.level.block.LightBlock;
import net.minecraft.world.level.block.state.properties.AttachFace;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.util.*;

/** One room, one actual button, and exact inherited ambient/table light points. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class SeeleLightingR48
{
    private static final BlockPos BUTTON=new BlockPos(17,-363,312);
    private record Circuit(List<BlockPos> ambient,List<BlockPos> table) { }
    private static final Map<MinecraftServer,Optional<Circuit>> CACHE=new WeakHashMap<>();
    private static final class State extends SavedData
    {
        boolean meeting;
        static State load(CompoundTag tag){var state=new State();state.meeting=tag.getBoolean("Meeting");return state;}
        @Override public CompoundTag save(CompoundTag tag){tag.putBoolean("Meeting",meeting);return tag;}
    }
    private static State state(ServerLevel level)
    {return level.getDataStorage().computeIfAbsent(State::load,State::new,"projectseele_seele_lighting_r48");}
    public static boolean meetingModeR48(ServerLevel level)
    {return level.dimension().equals(FacilitySchemaV2.DIMENSION)&&circuit(level).isPresent()&&state(level).meeting;}
    private static Optional<Circuit> circuit(ServerLevel level)
    {
        return CACHE.computeIfAbsent(level.getServer(),server->{
            var path=server.getWorldPath(LevelResource.ROOT).resolve("r48_seele_lighting.json");
            if(!Files.isRegularFile(path))return Optional.empty();
            try
            {
                var root=JsonParser.parseString(Files.readString(path)).getAsJsonObject();
                if(root.get("schema").getAsInt()!=48||!root.get("installed").getAsBoolean()
                        ||!root.get("dimension").getAsString().equals("projectseele:geofront"))return Optional.empty();
                var ambient=new ArrayList<BlockPos>();var table=new ArrayList<BlockPos>();var seen=new HashSet<BlockPos>();
                for(String group:List.of("ambient","table"))for(var raw:root.getAsJsonArray(group))
                {
                    var a=raw.getAsJsonArray();if(a.size()!=3)return Optional.empty();
                    var pos=new BlockPos(a.get(0).getAsInt(),a.get(1).getAsInt(),a.get(2).getAsInt());
                    if(pos.getX()<17||pos.getX()>50||pos.getY()<-364||pos.getY()>-363
                            ||pos.getZ()<301||pos.getZ()>314||!seen.add(pos))return Optional.empty();
                    boolean focus=pos.getX()>=32&&pos.getX()<=36&&pos.getZ()>=307&&pos.getZ()<=309;
                    if(group.equals("table")!=focus)return Optional.empty();
                    (focus?table:ambient).add(pos);
                }
                if(table.size()!=5||ambient.size()!=18)return Optional.empty();
                return Optional.of(new Circuit(List.copyOf(ambient),List.copyOf(table)));
            }
            catch(Exception failure){ProjectSeele.LOGGER.error("R48 finite SEELE lighting receipt rejected",failure);return Optional.empty();}
        });
    }
    @SubscribeEvent public static void use(PlayerInteractEvent.RightClickBlock event)
    {
        if(event.getHand()!=InteractionHand.MAIN_HAND||!event.getPos().equals(BUTTON)
                ||!(event.getEntity() instanceof ServerPlayer player)
                ||!(event.getLevel() instanceof ServerLevel level)||!level.dimension().equals(FacilitySchemaV2.DIMENSION)
                ||!SeeleConferenceAccessR47.enabled(level)||circuit(level).isEmpty())return;
        if(player.isSpectator()||!NervStaffDialogue.authorized(player)||player.distanceToSqr(net.minecraft.world.phys.Vec3.atCenterOf(BUTTON))>36)
        {event.setCanceled(true);return;}
        var button=level.getBlockState(BUTTON);
        if(!button.is(Blocks.POLISHED_BLACKSTONE_BUTTON)||button.getValue(ButtonBlock.POWERED)
                ||button.getValue(ButtonBlock.FACE)!=AttachFace.WALL||button.getValue(ButtonBlock.FACING)!=Direction.EAST
                ||!button.canSurvive(level,BUTTON))return;
        var state=state(level);state.meeting=!state.meeting;state.setDirty();update(level,circuit(level).orElseThrow(),state.meeting);
        player.displayClientMessage(net.minecraft.network.chat.Component.literal(state.meeting?"SEELE · 会议暗场，桌面重点照明。":"SEELE · 日常照明。"),true);
    }
    private static void update(ServerLevel level,Circuit circuit,boolean meeting)
    {
        for(var pos:circuit.ambient)light(level,pos,meeting?0:14);
        for(var pos:circuit.table)light(level,pos,pos.getX()==34?14:12);
    }
    private static void light(ServerLevel level,BlockPos pos,int value)
    {
        if(!level.hasChunkAt(pos))return;var light=level.getBlockState(pos);
        if(light.is(Blocks.LIGHT)&&!light.getValue(LightBlock.WATERLOGGED)&&light.getValue(LightBlock.LEVEL)!=value)
            level.setBlock(pos,light.setValue(LightBlock.LEVEL,value),3);
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||event.getServer().getTickCount()%20!=0)return;
        var level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null||!SeeleConferenceAccessR47.enabled(level))return;
        circuit(level).ifPresent(c->update(level,c,state(level).meeting));
    }
    private SeeleLightingR48() { }
}

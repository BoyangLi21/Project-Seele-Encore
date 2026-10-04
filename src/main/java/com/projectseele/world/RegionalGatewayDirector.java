package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.registry.ModItems;
import com.supermartijn642.movingelevators.MovingElevators;
import com.supermartijn642.movingelevators.blocks.ControllerBlock;
import com.supermartijn642.movingelevators.blocks.ControllerBlockEntity;
import com.supermartijn642.movingelevators.elevator.ElevatorGroup;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.util.Map;
import java.util.WeakHashMap;
import java.util.Comparator;

/** The regional gate owns its new shaft only; native Moving Elevators carries the whole car. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class RegionalGatewayDirector
{
    public static final int X = -360, Z = 750, LOWER = -466, UPPER = 81;
    private static final Map<ServerLevel, Runtime> RUNTIMES = new WeakHashMap<>();
    private static final BlockState CLOSED = Blocks.GRAY_STAINED_GLASS.defaultBlockState();
    private static final BlockState AIR = Blocks.AIR.defaultBlockState();
    private static final TicketType<ChunkPos> ATTACH = TicketType.create(
            "projectseele_regional_gate_attach", Comparator.comparingLong(ChunkPos::toLong), 100);

    private static final class Runtime
    {
        boolean ready, checked, active;
        long gateUntil, doorsClosedUntil;
        final long[] carSensorTimes={Long.MIN_VALUE,Long.MIN_VALUE};
        final boolean[] carSensorResults=new boolean[2];
    }

    public static boolean active(ServerLevel level)
    {
        Runtime state = RUNTIMES.computeIfAbsent(level, key -> new Runtime());
        if (!state.checked)
        {
            state.checked = true;
            var file = level.getServer().getWorldPath(LevelResource.ROOT).resolve("regional_plan.json");
            try
            {
                if (Files.isRegularFile(file))
                {
                    var plan = JsonParser.parseString(Files.readString(file)).getAsJsonObject();
                    state.active = plan.has("geometry_ready") && plan.get("geometry_ready").getAsBoolean();
                }
            }
            catch (Exception exception) { throw new IllegalStateException("Invalid regional gate configuration", exception); }
        }
        return state.active && level.dimension().equals(FacilitySchemaV2.DIMENSION);
    }

    public static BlockPos controllerPos(int y) { return new BlockPos(X - 8, y, Z); }

    public static ElevatorGroup group(ServerLevel level)
    {
        var entity = level.getBlockEntity(controllerPos(LOWER));
        return entity instanceof ControllerBlockEntity controller && controller.hasGroup() ? controller.getGroup() : null;
    }

    public static boolean commission(ServerLevel level)
    {
        if (!active(level)) return false;
        ChunkPos anchor = new ChunkPos(controllerPos(UPPER));
        level.getChunkSource().addRegionTicket(ATTACH, anchor, 2, anchor);
        for (int cx = -24; cx <= -22; cx++) for (int cz = 46; cz <= 47; cz++) level.getChunk(cx, cz);
        for (int y : new int[]{LOWER, UPPER})
        {
            BlockPos pos = controllerPos(y);
            if (!level.getBlockState(pos).is(MovingElevators.elevator_block))
                level.setBlock(pos, MovingElevators.elevator_block.defaultBlockState().setValue(ControllerBlock.FACING, Direction.EAST), 18);
            if (level.getBlockEntity(pos) instanceof ControllerBlockEntity controller)
                controller.setFloorName(y == UPPER ? "NERV 地面入口" : "地下都市 · 入构站");
        }
        ElevatorGroup group = group(level);
        if (group == null || group.getFloorCount() != 2 || group.isMoving()) return false;
        while (group.getCageWidth() < 15 && group.canIncreaseCageWidth()) group.increaseCageWidth();
        while (group.getCageDepth() < 15 && group.canIncreaseCageDepth()) group.increaseCageDepth();
        while (group.getCageHeight() < 9 && group.canIncreaseCageHeight()) group.increaseCageHeight();
        while (group.getCageHeightOffset() > -1 && group.canDecreaseCageHeightOffset()) group.decreaseCageHeightOffset();
        if (group.getCageWidth() != 15 || group.getCageDepth() != 15 || group.getCageHeight() != 9)
            throw new IllegalStateException("Regional lift requires Moving Elevators maxCabinHorizontalSize=15");
        group.setTargetSpeed(0.85);
        for(int y:new int[]{LOWER,UPPER})
        {
            installWallButton(level,new BlockPos(-355,y+1,740),Direction.NORTH);
            if(carAt(level,y))
                for(int z:new int[]{747,750})installWallButton(level,new BlockPos(-366,y+1,z),Direction.EAST);
        }
        RUNTIMES.get(level).ready = true;
        ProjectSeele.LOGGER.info("REGIONAL GATE READY nativeCar={}x{}x{} anchor={} floors={}",
                group.getCageSizeX(), group.getCageSizeY(), group.getCageSizeZ(), group.getCageAnchorBlockPos(UPPER), group.getFloorCount());
        return true;
    }

    private static void installWallButton(ServerLevel level,BlockPos pos,Direction facing)
    {
        // Controls sit on fixed jamb/cabin walls, outside both moving doors.
        var backing=level.getBlockState(pos.relative(facing.getOpposite()));
        var current=level.getBlockState(pos);
        if(!backing.isCollisionShapeFullBlock(level,pos.relative(facing.getOpposite()))
                ||!current.isAir()&&!(current.getBlock() instanceof net.minecraft.world.level.block.ButtonBlock))return;
        set(level,pos,Blocks.POLISHED_BLACKSTONE_BUTTON.defaultBlockState()
                .setValue(net.minecraft.world.level.block.ButtonBlock.FACE,net.minecraft.world.level.block.state.properties.AttachFace.WALL)
                .setValue(net.minecraft.world.level.block.ButtonBlock.FACING,facing));
    }

    public static boolean validCard(ItemStack stack)
    {
        return stack.is(ModItems.NERV_EMPLOYEE_CARD.get()) || stack.is(ModItems.TERMINAL_DOGMA_ACCESS_CARD.get());
    }

    public static boolean swipe(ServerPlayer player)
    {
        ServerLevel level = player.serverLevel();
        if (!validCard(player.getMainHandItem()) && !validCard(player.getOffhandItem()))
        {
            player.displayClientMessage(Component.literal("NERV：请手持职员证刷卡 / CARD REQUIRED"), true);
            return false;
        }
        RUNTIMES.get(level).gateUntil = level.getGameTime() + 160;
        player.displayClientMessage(Component.literal("NERV：权限确认，请进入 / ACCESS GRANTED"), true);
        return true;
    }

    @SubscribeEvent(priority = EventPriority.HIGHEST)
    public static void use(PlayerInteractEvent.RightClickBlock event)
    {
        if (!(event.getEntity() instanceof ServerPlayer player) || !active(player.serverLevel())) return;
        ServerLevel level = player.serverLevel();
        BlockPos pos = event.getPos();
        boolean handled = false;
        if(level.getBlockEntity(new BlockPos(-354,82,732)) instanceof NervAccessReaderEntityR44 reader
                &&(pos.equals(new BlockPos(-354,82,732))||pos.equals(new BlockPos(-354,82,734))))
        {return;}
        if (pos.equals(new BlockPos(-354, 82, 732))) { swipe(player); handled = true; }
        else if (pos.equals(new BlockPos(-354, 82, 734)))
        { RUNTIMES.get(level).gateUntil = level.getGameTime() + 160; handled = true; }
        else if (pos.getX() == -355 && pos.getZ() == 740 && (pos.getY() == LOWER + 1 || pos.getY() == UPPER + 1))
        { request(level, pos.getY() - 1, player); handled = true; }
        else if (pos.getX() == -366 && (pos.getZ() == 747 || pos.getZ() == 750)
                && (pos.getY() == LOWER + 1 || pos.getY() == UPPER + 1))
        { request(level, pos.getZ() == 747 ? LOWER : UPPER, player); handled = true; }
        if (handled) { event.setCanceled(true); event.setCancellationResult(InteractionResult.SUCCESS); }
    }

    public static boolean request(ServerLevel level, int target, ServerPlayer player)
    {
        if(!active(level)||(target!=LOWER&&target!=UPPER))return false;
        if(!controllersReadyR43(level))
        {
            commission(level);
            if(!controllersReadyR43(level))
            {NativeLiftCallRetryR43.gateway(player,target);return true;}
        }
        ElevatorGroup group = group(level);
        if (group == null || group.isMoving()) return rejected(target,"group unavailable or moving");
        Runtime state = RUNTIMES.get(level);
        if(!state.ready&&!commission(level))return rejected(target,"native controller configuration incomplete");
        if (carAt(level, target)){state.doorsClosedUntil=0;return true;}
        int source=target==LOWER?UPPER:LOWER;
        for(int cz=46;cz<=47;cz++)
        {ChunkPos at=new ChunkPos(-23,cz);level.getChunkSource().addRegionTicket(ATTACH,at,2,at);level.getChunk(-23,cz);}
        if(!carAt(level,source))return rejected(target,"source car sensors not ready");
        state.doorsClosedUntil = level.getGameTime() + 40;
        for (int y : new int[]{LOWER, UPPER})
        {
            door(level, y, 741, false);
            if (carAt(level, y)) door(level, y, 743, false);
        }
        if(Boolean.getBoolean("projectseele.r40LiftDebug"))
            for(int y:new int[]{LOWER,UPPER})
            {
                var anchor=group.getCageAnchorBlockPos(y);int index=group.getFloorNumber(y);
                boolean valid=S20MovingElevatorsAdapter.validCommandCageSource(level,group,anchor);
                boolean capture=com.supermartijn642.movingelevators.elevator.ElevatorCage.canCreateCage(level,anchor,group.getCageSizeX(),group.getCageSizeY(),group.getCageSizeZ(),null);
                var fromController=level.getBlockEntity(controllerPos(y));var destination=level.getBlockEntity(controllerPos(target));
                boolean place=fromController instanceof ControllerBlockEntity a&&destination instanceof ControllerBlockEntity b&&group.canCageBePlacedAt(b,a,null);
                ProjectSeele.LOGGER.info("R40 GATE DIAGNOSTIC floor={} target={} index={} physicalCar={} validSource={} nativeCapture={} nativeAvailable={} destinationClear={} size={}x{}x{} anchor={} facing={}",y,target,index,carAt(level,y),valid,capture,index>=0&&group.isCageAvailableAt(index,true,null),place,group.getCageSizeX(),group.getCageSizeY(),group.getCageSizeZ(),anchor,group.facing);
                if(!capture)for(var q:BlockPos.betweenClosed(anchor,anchor.offset(group.getCageSizeX()-1,group.getCageSizeY()-1,group.getCageSizeZ()-1)))
                    if(!com.supermartijn642.movingelevators.elevator.ElevatorCage.canBlockBeIgnored(level,q)&&!com.supermartijn642.movingelevators.elevator.ElevatorCage.canBlockBeInCage(level,q))ProjectSeele.LOGGER.info("R40 GATE IMMOBILE {} {}",q,level.getBlockState(q));
            }
        // Select the positively identified full car, rather than asking the
        // dependency to infer a source from all cached floor candidates.
        int from=group.getFloorNumber(source),to=group.getFloorNumber(target);
        if(from<0||to<0)return rejected(target,"floor indices not ready");
        if(!group.isCageAvailableAt(from,true,player))return rejected(target,"native source availability");
        var a=level.getBlockEntity(controllerPos(source));var b=level.getBlockEntity(controllerPos(target));
        if(!(a instanceof ControllerBlockEntity origin)||!(b instanceof ControllerBlockEntity destination)
                ||!group.canCageBePlacedAt(destination,origin,player))return rejected(target,"destination controller or native placement");
        group.onDisplayPress(source,to-from,player);
        return group.isMoving()||rejected(target,"native display did not start capture");
    }
    private static boolean rejected(int target,String stage)
    {ProjectSeele.LOGGER.warn("NERV GATE request rejected: target={} stage={}",target,stage);return false;}

    static boolean controllersReadyR43(ServerLevel level)
    {
        for(int y:new int[]{LOWER,UPPER})
            if(!(level.getBlockEntity(controllerPos(y)) instanceof ControllerBlockEntity controller)||!controller.hasGroup())return false;
        return true;
    }

    public static boolean carAt(ServerLevel level, int y)
    {
        if(y!=LOWER&&y!=UPPER)return false;
        var runtime=RUNTIMES.computeIfAbsent(level,key->new Runtime());
        int index=y==LOWER?0:1;long time=level.getGameTime();
        if(runtime.carSensorTimes[index]==time)return runtime.carSensorResults[index];
        boolean present=completeCarAt(level,y);
        runtime.carSensorTimes[index]=time;runtime.carSensorResults[index]=present;
        return present;
    }

    private static boolean completeCarAt(ServerLevel level,int y)
    {
        // The R45 utility finish replaced this car's original roof. Check
        // the complete original footprint with its finite finish contract;
        // a centre tile or an arbitrary solid landing is not a parked car.
        for(int dx=-7;dx<=7;dx++)for(int dz=-7;dz<=7;dz++)
        {
            var floor=new BlockPos(X+dx,y-1,Z+dz);
            var roof=new BlockPos(X+dx,y+7,Z+dz);
            if(!level.hasChunkAt(floor)||!level.hasChunkAt(roof)
                    ||!level.getBlockState(floor).is(Blocks.SMOOTH_STONE)
                    ||!TvLiftFinishR45.recognizedGatewayRoof(level,level.getBlockState(roof))
                    ||level.getBlockEntity(floor)!=null||level.getBlockEntity(roof)!=null)return false;
        }
        return true;
    }

    private static void set(ServerLevel level, BlockPos pos, BlockState state)
    { if (!level.getBlockState(pos).equals(state)) level.setBlock(pos, state, 18); }

    private static void door(ServerLevel level, int y, int z, boolean open)
    {
        for (int x = X - 3; x <= X + 3; x++) for (int dy = 0; dy < 5; dy++)
            set(level, new BlockPos(x, y + dy, z), open ? AIR : CLOSED);
    }

    public static java.util.Set<BlockPos> arrivalDoorCells(int y)
    {
        if(y!=LOWER && y!=UPPER)return java.util.Set.of();
        var cells=new java.util.LinkedHashSet<BlockPos>();
        for(int z:new int[]{741,743})for(int x=X-3;x<=X+3;x++)for(int dy=0;dy<5;dy++)
            cells.add(new BlockPos(x,y+dy,z));
        return java.util.Collections.unmodifiableSet(cells);
    }

    @SubscribeEvent
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END) return;
        ServerLevel level = event.getServer().getLevel(FacilitySchemaV2.DIMENSION);
        if (level == null || !active(level) || !level.hasChunkAt(controllerPos(UPPER))) return;
        Runtime state = RUNTIMES.get(level);
        if (!state.ready && event.getServer().getTickCount() % 20 == 0) commission(level);
        ElevatorGroup group = group(level);
        if (group == null || !state.ready) return;
        long time = level.getGameTime();
        if(!(level.getBlockEntity(new BlockPos(-354,82,732)) instanceof NervAccessReaderEntityR44))
        {
            if (!level.getEntitiesOfClass(ServerPlayer.class, new AABB(-364,81,733,-356,85,737)).isEmpty())
                state.gateUntil = time + 40;
            boolean gateOpen = state.gateUntil > time;
            for (int x = X - 3; x <= X + 3; x++) for (int y = 81; y <= 85; y++)
                set(level, new BlockPos(x,y,733), gateOpen ? AIR : CLOSED);
        }
        for (int y : new int[]{LOWER, UPPER})
        {
            boolean present = !group.isMoving() && carAt(level,y);
            boolean open = present && state.doorsClosedUntil <= time;
            door(level,y,741,open);
            if (present) door(level,y,743,open);
        }
    }
}

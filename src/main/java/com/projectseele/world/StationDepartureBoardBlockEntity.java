package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.registry.ModBlockEntities;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.protocol.game.ClientboundBlockEntityDataPacket;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import java.util.List;

public final class StationDepartureBoardBlockEntity extends BlockEntity
{
    private BlockPos platform = BlockPos.ZERO;
    private String station = "", route = "";
    private List<String> rows = List.of("正在读取运行信息");
    private List<String> rearRows = List.of();
    private boolean rearGuideBound;
    private boolean warned;
    private boolean wayfinding;
    private boolean routeMap;
    private boolean airService;
    private long linkedPlatformId = -1, nativeClock;
    private long preferredPlatformId = -1;
    private List<Long> departures = List.of();
    public StationDepartureBoardBlockEntity(BlockPos pos, BlockState state) { super(ModBlockEntities.STATION_DEPARTURE_BOARD.get(),pos,state); }
    public String title() { return wayfinding ? route : route + (airService?"  航班动态 · 北京时间":"  发车信息 · 北京时间"); }
    public String station() { return station; }
    public List<String> rows() { return rows; }
    public List<String> rearRows() { return rearRows; }
    public boolean rearGuideBound() { return rearGuideBound; }
    public boolean routeMap() { return routeMap; }
    public long linkedPlatformId() { return linkedPlatformId; }
    public long nativeClock() { return nativeClock; }
    public List<Long> departureTimes() { return departures; }
    public void tickServer()
    {
        if (wayfinding || level == null || level.getGameTime() % 20 != Math.floorMod(worldPosition.asLong(),20)) return;
        try
        {
            var snapshot = NativeStationDepartures.read(platform,preferredPlatformId);
            linkedPlatformId = snapshot.platformId();nativeClock = snapshot.clock();departures = snapshot.departures();
            if (!rows.equals(snapshot.rows()))
            {
                rows = snapshot.rows();setChanged();
                level.sendBlockUpdated(worldPosition,getBlockState(),getBlockState(),Block.UPDATE_CLIENTS);
            }
        }
        catch (ReflectiveOperationException failure)
        {
            if (!warned) { warned = true;ProjectSeele.LOGGER.warn("Station board could not read native MTR departures at {}",worldPosition,failure); }
        }
    }
    @Override protected void saveAdditional(CompoundTag tag)
    {
        super.saveAdditional(tag);tag.putLong("PlatformCentre",platform.asLong());tag.putString("Station",station);tag.putString("Route",route);
        tag.putString("Row0",rows.isEmpty()?"":rows.get(0));tag.putString("Row1",rows.size()>1?rows.get(1):"");
        tag.putBoolean("Wayfinding",wayfinding);tag.putString("Row2",rows.size()>2?rows.get(2):"");
        tag.putLong("NativePlatformId",preferredPlatformId);
        tag.putBoolean("AirService",airService);
        if(rearGuideBound)
        {
            tag.putBoolean("RearGuideBoundR47",true);
            var rear=new net.minecraft.nbt.ListTag();
            rearRows.forEach(row->rear.add(net.minecraft.nbt.StringTag.valueOf(row)));
            tag.put("RearRowsR47",rear);
        }
        if (routeMap)
        {
            var map = new net.minecraft.nbt.ListTag();
            rows.forEach(row -> map.add(net.minecraft.nbt.StringTag.valueOf(row)));
            tag.put("MapRows", map);
        }
    }
    @Override public void load(CompoundTag tag)
    {
        super.load(tag);platform=BlockPos.of(tag.getLong("PlatformCentre"));station=tag.getString("Station");route=tag.getString("Route");
        wayfinding=tag.getBoolean("Wayfinding");
        rearGuideBound=wayfinding&&tag.getBoolean("RearGuideBoundR47");
        var rear=tag.getList("RearRowsR47",net.minecraft.nbt.Tag.TAG_STRING);
        rearRows=rearGuideBound?java.util.stream.IntStream.range(0,Math.min(3,rear.size())).mapToObj(rear::getString).toList():List.of();
        airService=tag.getBoolean("AirService");
        preferredPlatformId=tag.contains("NativePlatformId")?tag.getLong("NativePlatformId"):-1;
        rows=wayfinding&&!tag.getString("Row2").isEmpty()?List.of(tag.getString("Row0"),tag.getString("Row1"),tag.getString("Row2")):tag.getString("Row1").isEmpty()?List.of(tag.getString("Row0")):List.of(tag.getString("Row0"),tag.getString("Row1"));
        routeMap = wayfinding && tag.contains("MapRows", net.minecraft.nbt.Tag.TAG_LIST);
        if (routeMap)
        {
            var map = tag.getList("MapRows", net.minecraft.nbt.Tag.TAG_STRING);
            rows = java.util.stream.IntStream.range(0, Math.min(18,map.size())).mapToObj(map::getString).toList();
        }
    }
    @Override public CompoundTag getUpdateTag() { return saveWithoutMetadata(); }
    @Override public ClientboundBlockEntityDataPacket getUpdatePacket() { return ClientboundBlockEntityDataPacket.create(this); }
    @Override public net.minecraft.world.phys.AABB getRenderBoundingBox() { return new net.minecraft.world.phys.AABB(worldPosition).inflate(2); }
}

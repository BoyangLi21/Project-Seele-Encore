package com.projectseele.world;

import com.projectseele.ProjectSeele;
import java.io.DataOutputStream;
import java.io.File;
import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.dimension.DimensionType;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.level.storage.LevelResource;

/** Complete immutable wall/artwork images and a separately durable chamber lease. */
public final class DeadSeaChamberSavedDataR45 extends SavedData
{
    static final String NAME="projectseele_dead_sea_chamber_r45";
    static final String KEY="r45/dead_sea/highest_tree_chamber";
    String world="",key="",mode="CLOSED",fault="";
    boolean configured,safetyHeld;
    BlockPos gate=BlockPos.ZERO;
    int width,height,openTicks;
    long openUntil,lastTick=Long.MIN_VALUE;
    final List<Image> images=new ArrayList<>();
    final List<Reader> readers=new ArrayList<>();
    private CompoundTag extra=new CompoundTag();
    private DeadSeaChamberSavedDataR45() {}
    static DeadSeaChamberSavedDataR45 get(ServerLevel level)
    {return level.getDataStorage().computeIfAbsent(DeadSeaChamberSavedDataR45::load,DeadSeaChamberSavedDataR45::new,NAME);}
    static DeadSeaChamberSavedDataR45 load(CompoundTag tag)
    {
        if(tag.getInt("Version")!=1)throw new IllegalStateException("Unknown complete chamber protocol");
        var data=new DeadSeaChamberSavedDataR45();data.extra=tag.copy();
        data.configured=tag.getBoolean("Configured");data.world=tag.getString("WorldUUID");data.key=tag.getString("ChamberId");
        data.gate=BlockPos.of(tag.getLong("Gate"));data.width=tag.getInt("Width");data.height=tag.getInt("Height");data.openTicks=tag.getInt("OpenTicks");
        data.mode=tag.getString("Mode");data.openUntil=tag.getLong("OpenUntil");data.fault=tag.getString("Fault");data.safetyHeld=tag.getBoolean("SafetyHeld");
        for(Tag raw:tag.getList("Images",Tag.TAG_COMPOUND))
        {
            var row=(CompoundTag)raw;data.images.add(new Image(BlockPos.of(row.getLong("Pos")),
                    NbtUtils.readBlockState(BuiltInRegistries.BLOCK.asLookup(),row.getCompound("State")),
                    row.contains("NBT",Tag.TAG_COMPOUND)?row.getCompound("NBT").copy():null));
        }
        for(Tag raw:tag.getList("Readers",Tag.TAG_COMPOUND))
        {var row=(CompoundTag)raw;data.readers.add(new Reader(BlockPos.of(row.getLong("Pos")),row.getString("Role"),row.getString("Facing")));}
        data.validate();return data;
    }
    void validate()
    {
        if(!configured)return;
        if(!KEY.equals(key)||world.isBlank()||!gate.equals(new BlockPos(32,-329,340))||width!=3||height!=3||openTicks!=200
                ||!java.util.Set.of("CLOSED","OPENING","OPEN","CLOSING","FAULT").contains(mode))
            throw new IllegalStateException("Foreign or incomplete highest-room chamber authority");
        var positions=new java.util.HashSet<BlockPos>();
        for(Image image:images)if(!positions.add(image.pos))throw new IllegalStateException("Duplicate chamber image");
        for(int x=32;x<=34;x++)for(int y=-329;y<=-327;y++)
        {
            BlockPos cell=new BlockPos(x,y,340);
            var image=images.stream().filter(i->i.pos.equals(cell)).findFirst().orElseThrow();
            if(!image.state.is(Blocks.WHITE_CONCRETE)||image.nbt!=null)throw new IllegalStateException("Foreign portal image");
        }
        var art=images.stream().filter(i->i.pos.equals(new BlockPos(30,-322,339))).findFirst().orElseThrow();
        if(images.size()!=10||art.nbt==null||!"tree".equals(art.nbt.getString("Artwork"))
                ||!"projectseele:wall_artwork".equals(art.nbt.getString("id"))
                ||!"projectseele:wall_artwork".equals(BuiltInRegistries.BLOCK.getKey(art.state.getBlock()).toString())
                ||art.nbt.getInt("x")!=30||art.nbt.getInt("y")!=-322||art.nbt.getInt("z")!=339)
            throw new IllegalStateException("Original complete Tree artwork image is missing");
        if(readers.size()!=2||readers.stream().noneMatch(r->r.equals(new Reader(new BlockPos(36,-328,339),"outside_left","north")))
                ||readers.stream().noneMatch(r->r.equals(new Reader(new BlockPos(35,-328,341),"inside_exit","south"))))
            throw new IllegalStateException("Exact external/internal reader authority missing");
    }
    @Override public CompoundTag save(CompoundTag output)
    {
        for(String field:extra.getAllKeys())output.put(field,extra.get(field).copy());
        output.putInt("Version",1);output.putBoolean("Configured",configured);output.putString("WorldUUID",world);output.putString("ChamberId",key);
        output.putLong("Gate",gate.asLong());output.putInt("Width",width);output.putInt("Height",height);output.putInt("OpenTicks",openTicks);
        output.putString("Mode",mode);output.putLong("OpenUntil",openUntil);output.putString("Fault",fault);output.putBoolean("SafetyHeld",safetyHeld);
        ListTag all=new ListTag();for(Image image:images)
        {var row=new CompoundTag();row.putLong("Pos",image.pos.asLong());row.put("State",NbtUtils.writeBlockState(image.state));if(image.nbt!=null)row.put("NBT",image.nbt.copy());all.add(row);}output.put("Images",all);
        ListTag bound=new ListTag();for(Reader reader:readers)
        {var row=new CompoundTag();row.putLong("Pos",reader.pos.asLong());row.putString("Role",reader.role);row.putString("Facing",reader.facing);bound.add(row);}output.put("Readers",bound);return output;
    }
    void durable(ServerLevel level)
    {
        setDirty();Path file=DimensionType.getStorageFolder(level.dimension(),level.getServer().getWorldPath(LevelResource.ROOT)).resolve("data").resolve(NAME+".dat");
        save(file.toFile());
    }
    @Override public void save(File file)
    {
        if(!isDirty())return;
        try
        {
            Path target=file.toPath();Files.createDirectories(target.getParent());Path temporary=Files.createTempFile(target.getParent(),NAME,".pending");
            try
            {
                CompoundTag wrapper=new CompoundTag();wrapper.put("data",save(new CompoundTag()));NbtUtils.addCurrentDataVersion(wrapper);
                try(var out=new DataOutputStream(new java.util.zip.GZIPOutputStream(Files.newOutputStream(temporary)))){NbtIo.write(wrapper,out);}
                try(var channel=FileChannel.open(temporary,StandardOpenOption.WRITE)){channel.force(true);}
                Files.move(temporary,target,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);setDirty(false);
            }
            finally{Files.deleteIfExists(temporary);}
        }
        catch(IOException failure){setDirty();ProjectSeele.LOGGER.error("Complete Tree/chamber transaction remains uncommitted",failure);throw new IllegalStateException(failure);}
    }
    record Reader(BlockPos pos,String role,String facing) {}
    record Image(BlockPos pos,BlockState state,CompoundTag nbt)
    {
        boolean matches(ServerLevel level,boolean opened)
        {
            BlockState wanted=opened?Blocks.AIR.defaultBlockState():state;
            if(!level.getBlockState(pos).equals(wanted))return false;
            var actual=level.getBlockEntity(pos);if(opened||nbt==null)return actual==null;
            if(actual==null)return false;
            CompoundTag complete=actual.saveWithFullMetadata();
            if(complete.equals(nbt))return true;
            // Explicit region packing envelope; no arbitrary field is dropped.
            if(!complete.contains("keepPacked")&&nbt.contains("keepPacked",Tag.TAG_BYTE)&&nbt.getByte("keepPacked")==0)
            {complete.putByte("keepPacked",(byte)0);return complete.equals(nbt);}
            return false;
        }
        void write(ServerLevel level,boolean opened)
        {
            if(matches(level,opened))return;
            level.removeBlockEntity(pos);level.setBlock(pos,opened?Blocks.AIR.defaultBlockState():state,2|16|32);
            if(!opened&&nbt!=null)
            {
                BlockEntity restored=BlockEntity.loadStatic(pos,state,nbt.copy());
                if(restored==null)throw new IllegalStateException("Original complete artwork BE could not be restored");
                level.setBlockEntity(restored);restored.setChanged();level.sendBlockUpdated(pos,state,state,2);
            }
        }
    }
}

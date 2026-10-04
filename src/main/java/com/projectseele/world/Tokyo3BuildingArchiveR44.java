package com.projectseele.world;

import java.io.DataOutputStream;
import java.io.File;
import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.HashSet;
import java.util.zip.Deflater;
import java.util.zip.GZIPOutputStream;

import it.unimi.dsi.fastutil.longs.Long2ObjectMap;
import it.unimi.dsi.fastutil.longs.Long2ObjectOpenHashMap;
import it.unimi.dsi.fastutil.longs.LongOpenHashSet;
import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.NbtUtils;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.level.dimension.DimensionType;
import net.minecraft.world.level.storage.LevelResource;

/**
 * Per-world cargo and exact write-ahead transactions for generated city buildings.
 * Original coordinates index the cargo; absolute coordinates index the journal.
 * No process-global snapshot can leak inventory or geometry to another save.
 */
public final class Tokyo3BuildingArchiveR44 extends SavedData
{
    private static final String NAME = "projectseele_tokyo3_building_archive_r44";
    private static final int FLAGS = Block.UPDATE_CLIENTS | Block.UPDATE_KNOWN_SHAPE;
    public static final int WRITE_BUDGET = Math.max(192,Math.min(4096,
            Integer.getInteger("projectseele.tokyo3WriteBudgetR44",2048)));
    private final Map<Long, Cargo> buildings = new LinkedHashMap<>();
    private String worldUUID="";
    private boolean loadedLegacy;
    private Path archiveFile;

    public static Tokyo3BuildingArchiveR44 get(ServerLevel level,BlockPos centre)
    {
        Tokyo3BuildingArchiveR44 data=level.getDataStorage().computeIfAbsent(
                Tokyo3BuildingArchiveR44::load, Tokyo3BuildingArchiveR44::new,
                NAME+"_"+Long.toUnsignedString(centre.asLong()));
        data.archiveFile = DimensionType.getStorageFolder(level.dimension(),
                level.getServer().getWorldPath(LevelResource.ROOT)).resolve("data")
                .resolve(NAME+"_"+Long.toUnsignedString(centre.asLong())+".dat");
        String expected=Tokyo3BuildingWorldIdentityR44.get(level);
        if(data.loadedLegacy&&!Boolean.getBoolean("projectseele.r44BindLegacyCityArchives"))
            throw new IllegalStateException("Legacy cargo archive needs a backed-up explicit WorldUUID/core-mask migration");
        if(data.worldUUID.isEmpty())
        {
            data.worldUUID=expected;data.setDirty();
        }
        if(!data.worldUUID.equals(expected))throw new IllegalStateException("Cargo archive belongs to another WorldUUID");
        return data;
    }

    public static Tokyo3BuildingArchiveR44 load(CompoundTag root)
    {
        if (root.getInt("Version") != 1)
            throw new IllegalStateException("Unknown Tokyo-3 building archive version");
        Tokyo3BuildingArchiveR44 data = new Tokyo3BuildingArchiveR44();
        data.worldUUID=root.getString("WorldUUID");data.loadedLegacy=data.worldUUID.isEmpty();
        ListTag entries = root.getList("Buildings", Tag.TAG_COMPOUND);
        for (Tag raw : entries)
        {
            CompoundTag tag = (CompoundTag) raw;
            Cargo cargo = new Cargo(tag.getLong("Origin"), tag.getInt("Height"), tag.getInt("Half"));
            cargo.fixedCore=tag.getBoolean("FixedStreetCore");cargo.coreKnown=tag.contains("FixedStreetCore");
            if(!cargo.coreKnown)data.loadedLegacy=true;
            ListTag cells = tag.getList("Cargo", Tag.TAG_COMPOUND);
            for (Tag cell : cells)
            {
                CompoundTag value = (CompoundTag) cell;
                cargo.cells.put(value.getLong("Pos"), Cell.load(value));
            }
            if (tag.contains("Transaction", Tag.TAG_COMPOUND))
                cargo.transaction = Transaction.load(tag.getCompound("Transaction"));
            for(long p:tag.getLongArray("NegativeDomeAnchorMask"))cargo.fixedAnchors.add(p);
            data.buildings.put(tag.getLong("Centre"), cargo);
        }
        return data;
    }

    @Override
    public CompoundTag save(CompoundTag root)
    {
        root.putInt("Version", 1);
        root.putString("WorldUUID",worldUUID);
        // BlockState is immutable. Share its read-only serialized tag only
        // within this synchronous save; full per-cell BE NBT stays separate.
        Map<BlockState, CompoundTag> stateTags = new HashMap<>();
        ListTag entries = new ListTag();
        buildings.forEach((key, cargo) ->
        {
            CompoundTag tag = new CompoundTag();
            tag.putLong("Centre", key);
            tag.putLong("Origin", cargo.origin);
            tag.putInt("Height", cargo.height);
            tag.putInt("Half", cargo.half);
            tag.putBoolean("FixedStreetCore",cargo.fixedCore);
            ListTag cells = new ListTag();
            cargo.cells.forEach((pos, cell) ->
            {
                CompoundTag value = cell.save(stateTags); value.putLong("Pos", pos); cells.add(value);
            });
            tag.put("Cargo", cells);
            tag.putLongArray("NegativeDomeAnchorMask",cargo.fixedAnchors.stream().mapToLong(Long::longValue).toArray());
            if (cargo.transaction != null) tag.put("Transaction", cargo.transaction.save(stateTags));
            entries.add(tag);
        });
        root.put("Buildings", entries);
        return root;
    }

    public TravelStep step(ServerLevel level, BlockPos origin,
                           ThirdTokyoSurfaceBuilder.TowerSpec tower,
                           int oldDepth, int newDepth, int cursor)
    {
        BlockPos centre = origin.offset(tower.x(), 0, tower.z());
        Cargo cargo = buildings.get(centre.asLong());
        int roof = origin.getY() + ThirdTokyoSurfaceBuilder.ceilingRoofRelativeY(tower, origin);
        Set<Long> fixed;
        try{fixed=fixedAnchors(level,centre,tower,roof);}
        catch(IllegalStateException error){return new TravelStep(false,true,cursor,0,error.getMessage());}
        if (cargo == null)
        {
            int ceilingVisible = visibleBelow(tower, origin, oldDepth);
            if (oldDepth != 0 && ceilingVisible != tower.height())
                return new TravelStep(false, true, cursor, 0,
                        "Legacy tower is partially hidden; a complete measured cargo source is required");
            cargo = new Cargo(origin.asLong(), tower.height(), tower.halfSize());
            cargo.fixedCore=level.getBlockState(centre).is(com.projectseele.registry.ModBlocks.RETRACTABLE_BUILDING_CORE.get());cargo.coreKnown=true;
            cargo.fixedAnchors.addAll(fixed);
            try{capture(level, centre, tower, oldDepth, roof, cargo);}
            catch(IllegalStateException error){return new TravelStep(false,true,0,0,error.getMessage());}
            buildings.put(centre.asLong(), cargo);
            setDirty();
        }
        if (cargo.origin != origin.asLong() || cargo.height != tower.height() || cargo.half != tower.halfSize())
            return new TravelStep(false, true, cursor, 0, "Cargo envelope changed without an explicit migration");
        if(!cargo.fixedAnchors.equals(fixed))
            return new TravelStep(false,true,cursor,0,"Fixed dome anchor mask changed without a measured migration");
        boolean currentCore=level.getBlockState(centre).is(com.projectseele.registry.ModBlocks.RETRACTABLE_BUILDING_CORE.get());
        if(!cargo.coreKnown)
        {cargo.fixedCore=currentCore;cargo.coreKnown=true;setDirty();}
        if(cargo.fixedCore!=currentCore)return new TravelStep(false,true,cursor,0,"Immutable street controller ownership changed; preserve complete current state/NBT");
        Transaction previous = cargo.transaction;
        if (previous != null && !previous.complete && (previous.oldDepth != oldDepth || previous.newDepth != newDepth))
        {
            // Saved chunk and SavedData flushes can finish at different times.
            // Retain the last journal until its actual after states are present.
            TravelStep replay = apply(level, previous, 0, WRITE_BUDGET);
            if (!replay.complete || replay.failed) return replay;
        }
        if (previous == null || previous.oldDepth != oldDepth || previous.newDepth != newDepth)
        {
            try{capture(level, centre, tower, oldDepth, roof, cargo);}
            catch(IllegalStateException error){return new TravelStep(false,true,0,0,error.getMessage());}
            Long2ObjectMap<Cell> beforeOwned = representation(centre, tower, oldDepth, roof, cargo);
            Long2ObjectMap<Cell> afterOwned = representation(centre, tower, newDepth, roof, cargo);
            int visible=visibleBelow(tower,origin,newDepth);
            for(var entry:cargo.cells.entrySet())
            {
                BlockPos local=BlockPos.of(entry.getKey());int y=local.getY();
                if(visible>0&&y>=tower.height()-visible+1)
                {
                    BlockPos target=new BlockPos(centre.getX()+local.getX(),roof-tower.height()-1+y,centre.getZ()+local.getZ());
                    if(cargo.fixedAnchors.contains(target.asLong())&&!entry.getValue().state.isAir())
                        return new TravelStep(false,true,0,0,"Cargo roof component collides with fixed dome anchor at "+target.toShortString());
                }
            }
            LongOpenHashSet union = new LongOpenHashSet(beforeOwned.keySet());
            union.addAll(afterOwned.keySet());
            long[] ordered = union.toLongArray();
            Arrays.sort(ordered);
            List<Write> writes = new ArrayList<>();
            for (long key : ordered)
            {
                BlockPos target = BlockPos.of(key);
                if (target.equals(centre) && level.getBlockState(target)
                        .is(com.projectseele.registry.ModBlocks.RETRACTABLE_BUILDING_CORE.get())) continue;
                Cell before = Cell.read(level, target);
                Cell after = afterOwned.getOrDefault(key, Cell.AIR).at(target);
                if (!beforeOwned.containsKey(key) && !before.state.isAir())
                    return new TravelStep(false, true, 0, 0,
                            "Unowned destination collision at " + target.toShortString() + " " + before.state);
                if (!before.equals(after)) writes.add(new Write(target, before, after));
            }
            cargo.transaction = new Transaction(oldDepth, newDepth, writes);
            setDirty();
            // Make the inverse durable before the first native placement.
            try
            {
                persistWriteAhead();
            }
            catch (IOException error)
            {
                // This transaction has made no placements. Rebuild and retry
                // it only after an explicit maintenance request repairs IO.
                cargo.transaction = previous;
                setDirty();
                return new TravelStep(false, true, 0, 0,
                        "Cannot persist complete cargo write-ahead archive: " + error);
            }
            cursor = 0;
        }
        TravelStep step = apply(level, cargo.transaction, cursor, WRITE_BUDGET);
        if (step.complete() && !cargo.transaction.complete)
        {
            cargo.transaction.complete = true;
            setDirty();
        }
        // The journal is immutable while a slice is applied; its cursor lives
        // in Tokyo3RetractionSavedData. Do not reserialize cargo for each slice.
        return step;
    }

    private void persistWriteAhead() throws IOException
    {
        if (archiveFile == null) throw new IOException("Missing per-tower archive path");
        persistAtomic(archiveFile);
    }

    @Override
    public void save(File file)
    {
        if (!isDirty()) return;
        try
        {
            // Autosave/close must not overwrite the durable inverse in place.
            persistAtomic(file.toPath());
        }
        catch (IOException error)
        {
            setDirty();
            ProjectSeele.LOGGER.error("Cannot atomically save Tokyo-3 cargo archive {}", file, error);
        }
    }

    private void persistAtomic(Path target) throws IOException
    {
        CompoundTag root = new CompoundTag();
        root.put("data", save(new CompoundTag()));
        NbtUtils.addCurrentDataVersion(root);
        Files.createDirectories(target.getParent());
        Path pending = Files.createTempFile(target.getParent(),
                target.getFileName().toString(), ".pending");
        try
        {
            // Same v1 NBT and gzip container as SavedData, with a faster lossless
            // compression level. Compression is synchronous before placement.
            try (DataOutputStream output = new DataOutputStream(
                    new FastGzipOutputStream(Files.newOutputStream(pending))))
            {
                NbtIo.write(root, output);
            }
            try (FileChannel file = FileChannel.open(pending, StandardOpenOption.WRITE))
            {
                file.force(true);
            }
            // Do not fall back to a non-atomic overwrite of the last inverse.
            Files.move(pending, target, StandardCopyOption.ATOMIC_MOVE,
                    StandardCopyOption.REPLACE_EXISTING);
            setDirty(false);
        }
        finally
        {
            Files.deleteIfExists(pending);
        }
    }

    private static final class FastGzipOutputStream extends GZIPOutputStream
    {
        FastGzipOutputStream(java.io.OutputStream output) throws IOException
        {
            super(output, 64 * 1024);
            def.setLevel(Deflater.BEST_SPEED);
        }
    }

    private static TravelStep apply(ServerLevel level, Transaction transaction, int cursor, int budget)
    {
        int index = Math.max(0, Math.min(cursor, transaction.writes.size()));
        int writes = 0;
        // A replay scans committed after states for free, but only a bounded
        // number of changed blocks is sent to clients in any invocation.
        for (; index < transaction.writes.size() && writes < budget; index++)
        {
            Write operation = transaction.writes.get(index);
            Cell actual = Cell.read(level, operation.pos);
            if (actual.equals(operation.after)) continue;
            if (!actual.equals(operation.before))
                return new TravelStep(false, true, index, writes,
                        "State/NBT precondition changed at " + operation.pos.toShortString());
            operation.after.write(level, operation.pos);
            writes++;
        }
        return new TravelStep(index == transaction.writes.size(), false,
                index == transaction.writes.size() ? 0 : index, writes, "");
    }

    private static int visibleBelow(ThirdTokyoSurfaceBuilder.TowerSpec tower, BlockPos origin, int depth)
    {
        int travel = Math.max(tower.height(), -ThirdTokyoSurfaceBuilder.ceilingRoofRelativeY(tower, origin));
        return Math.max(0, Math.min(tower.height(), depth - travel));
    }

    private static void capture(ServerLevel level, BlockPos centre,
                                ThirdTokyoSurfaceBuilder.TowerSpec tower,
                                int depth, int roof, Cargo cargo)
    {
        int surface = Math.max(0, tower.height() - depth);
        int below = visibleBelow(tower, BlockPos.of(cargo.origin), depth);
        for (int y = 0; y <= tower.height() + 3; y++)
        {
            Integer actualY = null;
            if (depth == 0 || surface > 0 && y - depth >= 1) actualY = centre.getY() + y - depth;
            else if (below > 0 && y >= tower.height() - below + 1 && y <= tower.height() + 3)
                actualY = roof - tower.height() - 1 + y;
            else if (below == tower.height() && y == 0) actualY = roof - tower.height() - 1;
            if (actualY == null) continue;
            for (int x = -tower.halfSize(); x <= tower.halfSize(); x++)
                for (int z = -tower.halfSize(); z <= tower.halfSize(); z++)
                {
                    BlockPos local = new BlockPos(x, y, z);
                    BlockPos actual=new BlockPos(centre.getX()+x,actualY,centre.getZ()+z);
                    if(x==0&&y==0&&z==0&&cargo.fixedCore)
                    {
                        boolean expected=depth==0?level.getBlockState(actual).is(com.projectseele.registry.ModBlocks.RETRACTABLE_BUILDING_CORE.get()):level.getBlockState(actual).equals(Blocks.SEA_LANTERN.defaultBlockState());
                        if(!expected||level.getBlockEntity(actual)!=null)
                            throw new IllegalStateException("Immutable controller/underside-light mask differs at "+actual.toShortString()+"; preserve user state and full NBT for explicit migration");
                        continue;
                    }
                    if(cargo.fixedAnchors.contains(actual.asLong()))continue;
                    Cell cell = Cell.read(level, actual);
                    if (cell.state.isAir() && cell.nbt == null) cargo.cells.remove(local.asLong());
                    else cargo.cells.put(local.asLong(), cell);
                }
        }
        // Capture is an exact observation. Missing roof equipment remains
        // missing; a separately reviewed migration must supply its own inverse.
    }

    private static Long2ObjectMap<Cell> representation(BlockPos centre,
                ThirdTokyoSurfaceBuilder.TowerSpec tower, int depth, int roof, Cargo cargo)
    {
        Long2ObjectMap<Cell> result = new Long2ObjectOpenHashMap<>();
        int surface = Math.max(0, tower.height() - depth);
        int below = visibleBelow(tower, BlockPos.of(cargo.origin), depth);
        if (surface > 0)
            planeRange(result, centre, tower.halfSize(), 1, surface + 3, Cell.AIR);
        if (below > 0)
            planeRange(result, new BlockPos(centre.getX(), roof, centre.getZ()), tower.halfSize(), -below-1, 2, Cell.AIR);
        // The fixed street cover is owned in every state. Its core remains a
        // separate, immobile controller and is excluded from the write mask.
        for (int x = -tower.halfSize(); x <= tower.halfSize(); x++)
            for (int z = -tower.halfSize(); z <= tower.halfSize(); z++)
                result.put(centre.offset(x, 0, z).asLong(), depth == 0
                        ? cargo.cells.getOrDefault(new BlockPos(x,0,z).asLong(), Cell.AIR)
                        : new Cell(ThirdTokyoSurfaceBuilder.retractedHatchStateR44(x,z,tower),null));
        for (Map.Entry<Long,Cell> entry : cargo.cells.entrySet())
        {
            BlockPos p = BlockPos.of(entry.getKey()); int y = p.getY();
            if (surface > 0 && y-depth >= 1)
                result.put(centre.offset(p.getX(),y-depth,p.getZ()).asLong(),entry.getValue());
            if (below > 0 && y >= tower.height()-below+1 && y <= tower.height()+3)
                result.put(new BlockPos(centre.getX()+p.getX(),roof-tower.height()-1+y,centre.getZ()+p.getZ()).asLong(),entry.getValue());
            if (below == tower.height() && y == 0)
                result.put(new BlockPos(centre.getX()+p.getX(),roof-tower.height()-1,centre.getZ()+p.getZ()).asLong(),entry.getValue());
        }
        if (below > 0 && below < tower.height())
        {
            BlockPos underside = new BlockPos(centre.getX(),roof-below-1,centre.getZ());
            planeRange(result, underside, tower.halfSize(),0,0,new Cell(Blocks.POLISHED_DEEPSLATE.defaultBlockState(),null));
            result.put(underside.asLong(),new Cell(Blocks.SEA_LANTERN.defaultBlockState(),null));
        }
        else if(below==tower.height()&&cargo.fixedCore)
        {
            // The fixed surface controller never becomes cargo. Retain the
            // established underside inspection light at its complete endpoint.
            result.put(new BlockPos(centre.getX(),roof-tower.height()-1,centre.getZ()).asLong(),
                    new Cell(Blocks.SEA_LANTERN.defaultBlockState(),null));
        }
        cargo.fixedAnchors.forEach(p -> result.remove(p.longValue()));
        return result;
    }

    private static Set<Long> fixedAnchors(ServerLevel level,BlockPos centre,
            ThirdTokyoSurfaceBuilder.TowerSpec tower,int roof)
    {
        Set<Long> mask=new HashSet<>();
        if(!tower.tv())return mask;
        for(int x:new int[]{-tower.halfSize(),tower.halfSize()})
            for(int z:new int[]{-tower.halfSize(),tower.halfSize()})
                for(int y=roof+1;y<=TvWorldPreviewTerrain.ROOF_Y;y++)
                {
                    BlockPos p=new BlockPos(centre.getX()+x,y,centre.getZ()+z);
                    if(!level.getBlockState(p).equals(Blocks.IRON_BLOCK.defaultBlockState())||level.getBlockEntity(p)!=null)
                        throw new IllegalStateException("Fixed dome anchor template differs at "+p.toShortString()+" "+level.getBlockState(p));
                    mask.add(p.asLong());
                }
        return mask;
    }

    private static void planeRange(Long2ObjectMap<Cell> target, BlockPos centre, int half, int first, int last, Cell cell)
    {
        for (int y = first; y <= last; y++)
            for (int x = -half; x <= half; x++)
                for (int z = -half; z <= half; z++) target.put(centre.offset(x,y,z).asLong(),cell);
    }

    private static final class Cargo
    {
        final long origin; final int height, half;
        final Map<Long, Cell> cells = new LinkedHashMap<>();
        final Set<Long> fixedAnchors=new HashSet<>();
        boolean fixedCore,coreKnown;
        Transaction transaction;
        Cargo(long origin, int height, int half) { this.origin=origin; this.height=height; this.half=half; }
    }

    private record Cell(BlockState state, CompoundTag nbt)
    {
        static final Cell AIR = new Cell(Blocks.AIR.defaultBlockState(),null);
        static Cell read(ServerLevel level, BlockPos pos)
        {
            BlockEntity entity = level.getBlockEntity(pos);
            return new Cell(level.getBlockState(pos),entity==null?null:entity.saveWithFullMetadata().copy());
        }
        Cell at(BlockPos pos)
        {
            if (nbt==null) return this;
            CompoundTag tag=nbt.copy();tag.putInt("x",pos.getX());tag.putInt("y",pos.getY());tag.putInt("z",pos.getZ());
            return new Cell(state,tag);
        }
        void write(ServerLevel level, BlockPos pos)
        {
            // Removing the old BE before setBlock prevents onRemove from
            // dropping container contents while their exact NBT is in cargo.
            level.removeBlockEntity(pos);
            if (!level.getBlockState(pos).equals(state)) level.setBlock(pos,state,FLAGS);
            if (nbt!=null)
            {
                BlockEntity entity=BlockEntity.loadStatic(pos,state,at(pos).nbt.copy());
                if (entity==null) throw new IllegalStateException("Cannot restore complete block entity at "+pos);
                level.setBlockEntity(entity);entity.setChanged();
                level.sendBlockUpdated(pos,state,state,Block.UPDATE_CLIENTS);
            }
            else if (state.hasBlockEntity())
            {
                BlockEntity entity=((net.minecraft.world.level.block.EntityBlock)state.getBlock()).newBlockEntity(pos,state);
                if (entity!=null) level.setBlockEntity(entity);
            }
            PerformanceCounters.recordWorldBlockWrites(1);
        }
        CompoundTag save(Map<BlockState, CompoundTag> stateTags)
        {
            CompoundTag tag=new CompoundTag();tag.put("State",stateTags.computeIfAbsent(state,NbtUtils::writeBlockState));
            if(nbt!=null)tag.put("NBT",nbt.copy());return tag;
        }
        static Cell load(CompoundTag tag)
        {
            return new Cell(NbtUtils.readBlockState(BuiltInRegistries.BLOCK.asLookup(),tag.getCompound("State")),
                    tag.contains("NBT",Tag.TAG_COMPOUND)?tag.getCompound("NBT").copy():null);
        }
    }

    private record Write(BlockPos pos, Cell before, Cell after)
    {
        CompoundTag save(Map<BlockState, CompoundTag> stateTags)
        {
            CompoundTag tag=new CompoundTag();tag.putLong("Pos",pos.asLong());
            tag.put("Before",before.save(stateTags));tag.put("After",after.save(stateTags));return tag;
        }
        static Write load(CompoundTag tag)
        {
            return new Write(BlockPos.of(tag.getLong("Pos")),Cell.load(tag.getCompound("Before")),Cell.load(tag.getCompound("After")));
        }
    }

    private static final class Transaction
    {
        final int oldDepth,newDepth;final List<Write> writes;boolean complete;
        Transaction(int oldDepth,int newDepth,List<Write> writes)
        {this.oldDepth=oldDepth;this.newDepth=newDepth;this.writes=List.copyOf(writes);}
        CompoundTag save(Map<BlockState, CompoundTag> stateTags)
        {
            CompoundTag tag=new CompoundTag();tag.putInt("OldDepth",oldDepth);tag.putInt("NewDepth",newDepth);
            tag.putBoolean("Complete",complete);
            ListTag list=new ListTag();writes.forEach(w->list.add(w.save(stateTags)));tag.put("Writes",list);return tag;
        }
        static Transaction load(CompoundTag tag)
        {
            List<Write> list=new ArrayList<>();for(Tag item:tag.getList("Writes",Tag.TAG_COMPOUND))list.add(Write.load((CompoundTag)item));
            Transaction transaction=new Transaction(tag.getInt("OldDepth"),tag.getInt("NewDepth"),list);
            transaction.complete=tag.getBoolean("Complete");return transaction;
        }
    }

    public record TravelStep(boolean complete, boolean failed, int cursor, int writes, String fault) {}
}

package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.registry.ModBlocks;
import java.nio.file.Files;
import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtIo;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.GlazedTerracottaBlock;
import net.minecraft.world.level.block.LeverBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.level.storage.LevelResource;

/** The order of the surveyed cells is physical: both outer gates open before the deck retracts. */
public final class DogmaInterlocks extends SavedData
{
    private static final BlockPos CONSOLE = new BlockPos(-10,-1229,116);
    private int cursor;
    private boolean opening;
    private boolean dead;
    private boolean tankLoaded;
    private long recover = -1;
    private int[] cells;
    private BlockState[] palette;
    private boolean tried;

    public static DogmaInterlocks get(ServerLevel level)
    {
        return level.getDataStorage().computeIfAbsent(DogmaInterlocks::load,DogmaInterlocks::new,"seele_dogma_interlocks");
    }

    private static DogmaInterlocks load(CompoundTag tag)
    {
        var state = new DogmaInterlocks();
        state.cursor = tag.getInt("Cursor");
        state.opening = tag.getBoolean("Opening");
        state.dead = tag.getBoolean("Dead");
        state.recover = tag.contains("Recover") ? tag.getLong("Recover") : -1;
        return state;
    }

    @Override public CompoundTag save(CompoundTag tag)
    {
        tag.putInt("Cursor",cursor);
        tag.putBoolean("Opening",opening);
        tag.putBoolean("Dead",dead);
        tag.putLong("Recover",recover);
        return tag;
    }

    private boolean geometry(ServerLevel level)
    {
        if (tried) return cells != null;
        tried = true;
        var file = level.getServer().getWorldPath(LevelResource.ROOT).resolve("r52/dogma_interlocks.nbt");
        if (!Files.isRegularFile(file)) return false;
        try
        {
            var root = NbtIo.readCompressed(file.toFile());
            var names = root.getList("Palette",8);
            var states = new BlockState[names.size()];
            for (int i=0;i<states.length;i++)
                states[i]=BlockStateParser.parseForBlock(BuiltInRegistries.BLOCK.asLookup(),names.getString(i),false).blockState();
            int[] rows = root.getIntArray("Cells");
            if (rows.length%5!=0 || cursor<0 || cursor>rows.length/5) throw new IllegalArgumentException("Invalid gate geometry");
            palette=states;
            cells=rows;
            return true;
        }
        catch (Exception e) { ProjectSeele.LOGGER.error("Cannot read Dogma interlock geometry",e); return false; }
    }

    public static String order(ServerLevel level, boolean open)
    {
        var data=get(level);
        if(!data.geometry(level)) return "ops.projectseele.dogma.unavailable";
        data.opening=open;
        data.setDirty();
        return open ? "ops.projectseele.dogma.open" : "ops.projectseele.dogma.close";
    }

    public static boolean released(ServerLevel level)
    {
        var data=get(level);
        return data.opening && data.geometry(level) && data.cursor==data.cells.length/5;
    }

    public static void tick(ServerLevel level)
    {
        var data=get(level);
        if ((data.opening || data.cursor>0) && data.geometry(level))
        {
            int limit=data.cells.length/5;
            int target=data.opening ? limit : 0;
            var pos=new BlockPos.MutableBlockPos();
            for(int budget=0;budget<180 && data.cursor!=target;budget++)
            {
                int row=5*(data.opening ? data.cursor : data.cursor-1);
                var p=pos.set(data.cells[row],data.cells[row+1],data.cells[row+2]);
                var want=data.palette[data.cells[row+(data.opening?4:3)]];
                if (level.getBlockState(p)!=want) level.setBlock(p,want,2);
                data.cursor+=data.opening?1:-1;
                data.setDirty();
                if(data.cursor==limit && data.opening) HeavensDoor.alignLowerLeaves(level);
            }
        }
        data.monitorTank(level);
    }

    private void monitorTank(ServerLevel level)
    {
        if (!level.hasChunkAt(CONSOLE))
        {
            tankLoaded = false;
            return;
        }
        var lever=level.getBlockState(CONSOLE);
        if (!lever.is(Blocks.LEVER)) return;
        if (!tankLoaded)
        {
            setFigures(level, dead);
            tankLoaded = true;
        }
        if (lever.getValue(LeverBlock.POWERED))
        {
            if (!dead) { setFigures(level,true); dead=true; setDirty(); }
            if (recover!=-1) { recover=-1; setDirty(); }
        }
        else if (dead)
        {
            if (recover<0) { recover=level.getGameTime()+5999; setDirty(); }
            if (level.getGameTime()>=recover) { setFigures(level,false); dead=false; recover=-1; setDirty(); }
        }
    }

    private static void setFigures(ServerLevel level,boolean collapsed)
    {
        var living=ModBlocks.DUMMY_TANK_FIGURE.get();
        var fallen=ModBlocks.DUMMY_TANK_REMAINS.get();
        for(int i=0;i<9;i++)
        {
            int x=-25+5*i;
            int z=102+(int)Math.round(7*Math.pow((x+6)/24.0,2));
            for(int row=0;row<2;row++)
            {
                var pos=new BlockPos(x+row,-1229+(i*3)%4+row*5,z-1-row);
                var state=level.getBlockState(pos);
                var target = collapsed ? fallen : living;
                if (state.is(target)) continue;
                var facing = i % 5 == 2 && row != 0 ? net.minecraft.core.Direction.WEST : net.minecraft.core.Direction.SOUTH;
                if (state.is(living) || state.is(fallen)) facing = state.getValue(GlazedTerracottaBlock.FACING);
                else if (!state.is(ModBlocks.LCL_BLOCK.get())) continue;
                level.setBlock(pos, target.defaultBlockState().setValue(GlazedTerracottaBlock.FACING, facing), 2);
            }
        }
    }
}

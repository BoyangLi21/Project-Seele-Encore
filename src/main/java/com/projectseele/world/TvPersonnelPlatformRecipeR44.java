package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.registry.ModBlocks;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.DoubleBlockHalf;
import net.minecraft.world.level.block.state.properties.DoorHingeSide;
import java.util.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/** Finite declared three-bed recipe; construction and operation have distinct preflights. */
public final class TvPersonnelPlatformRecipeR44
{
    private record Cell(BlockPos position, String before, BlockState after) { }
    private static final Set<BlockPos> OWNERS = new HashSet<>();
    static
    {
        for (String token : "-29:-394:-263;-29:-394:-262;-29:-394:-261;-29:-393:-260;-29:-393:-259;-29:-393:-258;-29:-393:-257;-29:-392:-256;-29:-392:-255;-29:-392:-254;-29:-392:-253;-29:-391:-252;-29:-391:-251;-29:-391:-250;-29:-391:-249;-29:-390:-248;-29:-390:-247;-28:-395:-263;-28:-395:-262;-28:-395:-261;-28:-394:-264;-28:-394:-260;-28:-394:-259;-28:-394:-258;-28:-394:-257;-28:-393:-264;-28:-393:-256;-28:-393:-255;-28:-393:-254;-28:-393:-253;-28:-392:-252;-28:-392:-251;-28:-392:-250;-28:-392:-249;-28:-391:-248;-28:-391:-247;-28:-390:-246;-27:-395:-263;-27:-395:-262;-27:-395:-261;-27:-394:-264;-27:-394:-260;-27:-394:-259;-27:-394:-258;-27:-394:-257;-27:-393:-264;-27:-393:-256;-27:-393:-255;-27:-393:-254;-27:-393:-253;-27:-392:-252;-27:-392:-251;-27:-392:-250;-27:-392:-249;-27:-391:-248;-27:-391:-247;-27:-390:-246;-26:-394:-263;-26:-394:-262;-26:-394:-261;-26:-393:-260;-26:-393:-259;-26:-393:-258;-26:-393:-257;-26:-392:-254;-26:-392:-253;-26:-391:-252;-26:-391:-251;-26:-391:-250;-26:-391:-249;-26:-390:-248;-26:-390:-247;2:-394:-263;2:-394:-262;2:-394:-261;2:-393:-260;2:-393:-259;2:-393:-258;2:-393:-257;2:-392:-254;2:-392:-253;2:-391:-252;2:-391:-251;2:-391:-250;2:-391:-249;2:-390:-248;2:-390:-247;3:-395:-263;3:-395:-262;3:-395:-261;3:-394:-264;3:-394:-260;3:-394:-259;3:-394:-258;3:-394:-257;3:-393:-264;3:-393:-256;3:-393:-255;3:-393:-254;3:-393:-253;3:-392:-252;3:-392:-251;3:-392:-250;3:-392:-249;3:-391:-248;3:-391:-247;3:-390:-246;4:-395:-263;4:-395:-262;4:-395:-261;4:-394:-264;4:-394:-260;4:-394:-259;4:-394:-258;4:-394:-257;4:-393:-264;4:-393:-256;4:-393:-255;4:-393:-254;4:-393:-253;4:-392:-252;4:-392:-251;4:-392:-250;4:-392:-249;4:-391:-248;4:-391:-247;4:-390:-246;5:-394:-263;5:-394:-262;5:-394:-261;5:-393:-260;5:-393:-259;5:-393:-258;5:-393:-257;5:-392:-256;5:-392:-255;5:-392:-254;5:-392:-253;5:-391:-252;5:-391:-251;5:-391:-250;5:-391:-249;5:-390:-248;5:-390:-247;13:-394:-263;13:-394:-262;13:-394:-261;13:-393:-260;13:-393:-259;13:-393:-258;13:-393:-257;13:-392:-256;13:-392:-255;13:-392:-254;13:-392:-253;13:-391:-252;13:-391:-251;13:-391:-250;13:-391:-249;13:-390:-248;13:-390:-247;14:-395:-263;14:-395:-262;14:-395:-261;14:-394:-264;14:-394:-260;14:-394:-259;14:-394:-258;14:-394:-257;14:-393:-264;14:-393:-256;14:-393:-255;14:-393:-254;14:-393:-253;14:-392:-252;14:-392:-251;14:-392:-250;14:-392:-249;14:-391:-248;14:-391:-247;14:-390:-246;15:-395:-263;15:-395:-262;15:-395:-261;15:-394:-264;15:-394:-260;15:-394:-259;15:-394:-258;15:-394:-257;15:-393:-264;15:-393:-256;15:-393:-255;15:-393:-254;15:-393:-253;15:-392:-252;15:-392:-251;15:-392:-250;15:-392:-249;15:-391:-248;15:-391:-247;15:-390:-246;16:-394:-263;16:-394:-262;16:-394:-261;16:-393:-260;16:-393:-259;16:-393:-258;16:-393:-257;16:-392:-254;16:-392:-253;16:-391:-252;16:-391:-251;16:-391:-250;16:-391:-249;16:-390:-248;16:-390:-247;44:-394:-263;44:-394:-262;44:-394:-261;44:-393:-260;44:-393:-259;44:-393:-258;44:-393:-257;44:-392:-254;44:-392:-253;44:-391:-252;44:-391:-251;44:-391:-250;44:-391:-249;44:-390:-248;44:-390:-247;45:-395:-263;45:-395:-262;45:-395:-261;45:-394:-264;45:-394:-260;45:-394:-259;45:-394:-258;45:-394:-257;45:-393:-264;45:-393:-256;45:-393:-255;45:-393:-254;45:-393:-253;45:-392:-252;45:-392:-251;45:-392:-250;45:-392:-249;45:-391:-248;45:-391:-247;45:-390:-246;46:-395:-263;46:-395:-262;46:-395:-261;46:-394:-264;46:-394:-260;46:-394:-259;46:-394:-258;46:-394:-257;46:-393:-264;46:-393:-256;46:-393:-255;46:-393:-254;46:-393:-253;46:-392:-252;46:-392:-251;46:-392:-250;46:-392:-249;46:-391:-248;46:-391:-247;46:-390:-246;47:-394:-263;47:-394:-262;47:-394:-261;47:-393:-260;47:-393:-259;47:-393:-258;47:-393:-257;47:-392:-256;47:-392:-255;47:-392:-254;47:-392:-253;47:-391:-252;47:-391:-251;47:-391:-250;47:-391:-249;47:-390:-248;47:-390:-247;55:-394:-263;55:-394:-262;55:-394:-261;55:-393:-260;55:-393:-259;55:-393:-258;55:-393:-257;55:-392:-256;55:-392:-255;55:-392:-254;55:-392:-253;55:-391:-252;55:-391:-251;55:-391:-250;55:-391:-249;55:-390:-248;55:-390:-247;56:-395:-263;56:-395:-262;56:-395:-261;56:-394:-264;56:-394:-260;56:-394:-259;56:-394:-258;56:-394:-257;56:-393:-264;56:-393:-256;56:-393:-255;56:-393:-254;56:-393:-253;56:-392:-252;56:-392:-251;56:-392:-250;56:-392:-249;56:-391:-248;56:-391:-247;56:-390:-246;57:-395:-263;57:-395:-262;57:-395:-261;57:-394:-264;57:-394:-260;57:-394:-259;57:-394:-258;57:-394:-257;57:-393:-264;57:-393:-256;57:-393:-255;57:-393:-254;57:-393:-253;57:-392:-252;57:-392:-251;57:-392:-250;57:-392:-249;57:-391:-248;57:-391:-247;57:-390:-246;58:-394:-263;58:-394:-262;58:-394:-261;58:-393:-260;58:-393:-259;58:-393:-258;58:-393:-257;58:-392:-254;58:-392:-253;58:-391:-252;58:-391:-251;58:-391:-250;58:-391:-249;58:-390:-248;58:-390:-247;82:-392:-256;82:-392:-255;82:-392:-252;82:-392:-251;82:-392:-250;82:-392:-249;82:-392:-248;82:-392:-247;82:-392:-246;82:-392:-245;83:-393:-256;83:-393:-255;83:-393:-254;83:-393:-253;83:-393:-252;83:-393:-251;83:-393:-250;83:-393:-249;83:-393:-248;83:-393:-247;83:-393:-246;83:-393:-245;83:-392:-257;83:-392:-244;84:-393:-256;84:-393:-255;84:-393:-254;84:-393:-253;84:-393:-252;84:-393:-251;84:-393:-250;84:-393:-249;84:-393:-248;84:-393:-247;84:-393:-246;84:-393:-245;84:-392:-257;84:-392:-256;84:-392:-255;84:-392:-254;84:-392:-253;84:-392:-252;84:-392:-251;84:-392:-250;84:-392:-249;84:-392:-248;84:-392:-244;85:-393:-246;85:-393:-245;85:-392:-247;85:-392:-244;86:-393:-246;86:-393:-245;86:-392:-247;86:-392:-244;87:-394:-246;87:-394:-245;87:-392:-247;87:-392:-244;88:-394:-246;88:-394:-245;88:-393:-247;88:-393:-244;89:-394:-246;89:-394:-245;89:-393:-246;89:-393:-245".split(";"))
        {
            String[] q=token.split(":");
            OWNERS.add(new BlockPos(Integer.parseInt(q[0]),Integer.parseInt(q[1]),Integer.parseInt(q[2])));
        }
        if (OWNERS.size()!=427) throw new IllegalStateException("Incomplete finite personnel recipe");
    }
    public static boolean owns(ServerLevel level, BlockPos position)
    {
        return TvPersonnelPlatformInterlockR44.enabled(level) && OWNERS.contains(position);
    }
    static boolean ownsPosition(BlockPos position) { return OWNERS.contains(position); }
    static Set<BlockPos> ownerPositions() { return Collections.unmodifiableSet(OWNERS); }
    private static int variant(BlockPos bed)
    {
        for(int v=0;v<3;v++) if(bed.equals(new BlockPos(-12+42*v,-443,-240)))return v;
        return -1;
    }
    static String stateKey(BlockState state)
    {
        String name=net.minecraft.core.registries.BuiltInRegistries.BLOCK.getKey(state.getBlock()).toString();
        if(state.getValues().isEmpty())return name;
        var props=new TreeMap<String,String>();
        state.getValues().forEach((p,v)->props.put(p.getName(),propertyName(p,v)));
        return name+"["+String.join(",",props.entrySet().stream().map(e->e.getKey()+"="+e.getValue()).toList())+"]";
    }
    @SuppressWarnings({"rawtypes","unchecked"})
    private static String propertyName(net.minecraft.world.level.block.state.properties.Property p,Comparable v)
    {return p.getName(v);}
    static BlockState parse(String key)
    {
        String name=key.substring(0,key.indexOf('['));
        var p=new HashMap<String,String>();
        for(String part:key.substring(key.indexOf('[')+1,key.length()-1).split(","))
        {String[] pair=part.split("=");p.put(pair[0],pair[1]);}
        if(name.equals("projectseele:tv_personnel_deck_r44"))
            return ModBlocks.NERV_TV_PERSONNEL_DECK_R44.get().defaultBlockState()
                .setValue(TvPersonnelDeckR44.FACING,Direction.valueOf(p.get("facing").toUpperCase(Locale.ROOT)))
                .setValue(TvPersonnelDeckR44.LEVEL,Integer.parseInt(p.get("level")))
                .setValue(TvPersonnelDeckR44.PROFILE,TvPersonnelDeckR44.Profile.valueOf(p.get("profile").toUpperCase(Locale.ROOT)));
        if(name.equals("projectseele:tv_personnel_guard_r44"))
            return ModBlocks.NERV_TV_PERSONNEL_GUARD_R44.get().defaultBlockState()
                .setValue(TvPersonnelGuardR44.DROP,Integer.parseInt(p.get("drop")))
                .setValue(TvPersonnelGuardR44.NORTH,Boolean.parseBoolean(p.get("north")))
                .setValue(TvPersonnelGuardR44.EAST,Boolean.parseBoolean(p.get("east")))
                .setValue(TvPersonnelGuardR44.SOUTH,Boolean.parseBoolean(p.get("south")))
                .setValue(TvPersonnelGuardR44.WEST,Boolean.parseBoolean(p.get("west")));
        if(name.equals("projectseele:city_personnel_door"))
            return ModBlocks.CITY_PERSONNEL_DOOR.get().defaultBlockState()
                .setValue(DoorBlock.FACING,Direction.valueOf(p.get("facing").toUpperCase(Locale.ROOT)))
                .setValue(DoorBlock.HALF,p.get("half").equals("lower")?DoubleBlockHalf.LOWER:DoubleBlockHalf.UPPER)
                .setValue(DoorBlock.HINGE,p.get("hinge").equals("left")?DoorHingeSide.LEFT:DoorHingeSide.RIGHT)
                .setValue(DoorBlock.OPEN,Boolean.parseBoolean(p.get("open")))
                .setValue(DoorBlock.POWERED,Boolean.parseBoolean(p.get("powered")));
        throw new IllegalArgumentException("Unknown recipe block "+name);
    }
    static boolean alreadyOwned(BlockState actual,BlockState expected)
    {
        if(actual.equals(expected))return true;
        return expected.getBlock() instanceof CityPersonnelDoorR44 && actual.is(expected.getBlock())
            && actual.setValue(DoorBlock.OPEN,false).setValue(DoorBlock.POWERED,false)
                .equals(expected.setValue(DoorBlock.OPEN,false).setValue(DoorBlock.POWERED,false));
    }
    public static Optional<String> ensure(ServerLevel level,BlockPos bed)
    {
        if(!TvPersonnelPlatformInterlockR44.enabled(level))return Optional.empty();
        int v=variant(bed);
        if(v<0)return Optional.of("Unknown personnel recipe bed");
        var entry=EvaFleetSavedData.get(level.getServer()).entry(v);
        if(entry.isPresent()&&entry.get().phase()!=EvaFleetSavedData.Phase.PARKED)
            return Optional.of("Personnel recipe cannot generate during equipment motion");
        var fault=TvPersonnelPlatformInterlockR44.constructionFault(level,v);
        if(fault.isPresent())return fault;
        try
        {
            if(!TvPersonnelPlatformInterlockR44.semanticReadyR47(level))return Optional.of("Personnel finite semantic epoch unavailable");
            var document=TvPersonnelSemanticEpochR47.recipe();
            var rows=document.getAsJsonArray("operations");
            if(rows.size()!=427)return Optional.of("Personnel recipe incomplete");
            var cells=new ArrayList<Cell>();var seen=new HashSet<BlockPos>();
            var gateOpen=new HashMap<BlockPos,Boolean>();
            for(var gateValue:document.getAsJsonArray("entry_gate_pairs"))
            {
                var gate=gateValue.getAsJsonObject();if(gate.get("variant").getAsInt()!=v)continue;
                Boolean open=null;var leaves=new ArrayList<BlockPos>();
                for(var value:gate.getAsJsonArray("lower_positions"))
                {
                    var q=value.getAsJsonArray();var lower=new BlockPos(q.get(0).getAsInt(),q.get(1).getAsInt(),q.get(2).getAsInt());
                    leaves.add(lower);leaves.add(lower.above());
                }
                for(var pos:leaves)
                {
                    var actual=level.getBlockState(pos);
                    if(actual.getBlock() instanceof CityPersonnelDoorR44)
                    {
                        boolean flag=actual.getValue(DoorBlock.OPEN);
                        if(open!=null&&open!=flag)return Optional.of("Personnel pair has inconsistent existing open state");
                        open=flag;
                    }
                }
                for(var pos:leaves)gateOpen.put(pos,open!=null&&open);
            }
            for(var value:rows)
            {
                var row=value.getAsJsonObject();var xyz=row.getAsJsonArray("position");
                var pos=new BlockPos(xyz.get(0).getAsInt(),xyz.get(1).getAsInt(),xyz.get(2).getAsInt());
                if(!OWNERS.contains(pos)||!seen.add(pos))return Optional.of("Unknown/duplicate recipe owner");
                if(pos.getX()<bed.getX()-21||pos.getX()>bed.getX()+21)continue;
                if(!level.hasChunkAt(pos)||level.getBlockEntity(pos)!=null)return Optional.of("Unknown section or protected block entity "+pos);
                var after=parse(row.get("after").getAsString());String before=row.get("before").getAsString();
                if(after.getBlock() instanceof CityPersonnelDoorR44)
                    after=after.setValue(DoorBlock.OPEN,gateOpen.getOrDefault(pos,false));
                var actual=level.getBlockState(pos);
                if(!alreadyOwned(actual,after)&&!actual.isAir()&&!stateKey(actual).equals(before))
                    return Optional.of("Human/source state changed at "+pos);
                if(after.getBlock() instanceof CityPersonnelDoorR44&&!alreadyOwned(actual,after)
                    &&!level.getEntitiesOfClass(net.minecraft.world.entity.LivingEntity.class,
                        new net.minecraft.world.phys.AABB(pos).expandTowards(0,1,0),e->e.isAlive()&&!e.isSpectator()).isEmpty())
                    return Optional.of("Personnel gate installation leaf is occupied "+pos);
                cells.add(new Cell(pos,before,after));
            }
            // Completepreflight occurs before the first mutation. Every block
            // has finite ownership, a matching prior or air, and no BE.
            for(var cell:cells)
                if(!alreadyOwned(level.getBlockState(cell.position),cell.after))
                    level.setBlock(cell.position,cell.after,Block.UPDATE_CLIENTS);
            return Optional.empty();
        }
        catch(Exception error){return Optional.of("Personnel recipe rejected: "+error.getMessage());}
    }
    private TvPersonnelPlatformRecipeR44() { }
}

package com.projectseele.world;

import com.projectseele.entity.EvaUnit01Entity;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.BlockTags;
import net.minecraft.world.level.GameRules;
import net.minecraft.world.level.block.LeavesBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;
import net.minecraftforge.event.ForgeEventFactory;

/** Natural canopy compression by an actual recovery load, never a route clearer. */
final class NervRescueVegetationR53
{
    static final int BLOCKS_PER_TICK=4;
    private static final Map<EvaUnit01Entity,long[]> BUDGETS=new WeakHashMap<>();
    private final ServerLevel level;
    private final EvaUnit01Entity eva;
    private final long tick;
    private final LinkedHashMap<BlockPos,BlockState> contacts=new LinkedHashMap<>();
    private final boolean allowed;

    NervRescueVegetationR53(ServerLevel level,EvaUnit01Entity eva)
    {
        this.level=level;this.eva=eva;tick=level.getGameTime();
        allowed=level.getGameRules().getBoolean(GameRules.RULE_MOBGRIEFING)
                &&ForgeEventFactory.getMobGriefingEvent(level,eva);
    }

    /** Called only after actual body or cradle surfaces meet this native shape.
     * Aircraft, capsule and pilot must already have passed strictly. */
    boolean contact(AABB obstacle)
    {
        if(!allowed||level.getGameTime()!=tick)return false;
        var pos=BlockPos.containing(obstacle.minX+.000001,obstacle.minY+.000001,obstacle.minZ+.000001);
        if(obstacle.minX<pos.getX()||obstacle.minY<pos.getY()||obstacle.minZ<pos.getZ()
                ||obstacle.maxX>pos.getX()+1||obstacle.maxY>pos.getY()+1||obstacle.maxZ>pos.getZ()+1
                ||!level.hasChunkAt(pos))return false;
        var state=level.getBlockState(pos);
        if(!naturalCanopy(pos,state))return false;
        contacts.putIfAbsent(pos.immutable(),state);
        return true;
    }

    private boolean naturalCanopy(BlockPos pos,BlockState state)
    {
        if(!vanillaLeaf(state)||!state.is(BlockTags.LEAVES)||state.hasBlockEntity()
                ||state.getDestroySpeed(level,pos)<0||!state.canEntityDestroy(level,pos,eva))return false;
        if(level.getChunkSource().getGenerator().getBiomeSource() instanceof RegionalEcologyBiomeSourceR44 source
                &&!source.permitsVegetationAt(pos))return false;
        return true;
    }
    // Persistent controls natural decay, not permission to crush a planted crown.
    static boolean vanillaLeaf(BlockState state)
    {return state.getBlock() instanceof LeavesBlock&&state.hasProperty(LeavesBlock.PERSISTENT)
            &&BuiltInRegistries.BLOCK.getKey(state.getBlock()).getNamespace().equals("minecraft");}

    boolean empty(){return contacts.isEmpty();}

    /** The caller first validates the entire current-tick group against every
     * other obstacle, then retries the ordinary strict proof after compression.
     * A rejected hook leaves the block and payload in place. */
    boolean compress()
    {
        if(!allowed||level.getGameTime()!=tick||!eva.isAlive()
                ||!level.getGameRules().getBoolean(GameRules.RULE_MOBGRIEFING)
                ||!ForgeEventFactory.getMobGriefingEvent(level,eva))return false;
        var budget=BUDGETS.computeIfAbsent(eva,key->new long[]{tick,0});
        if(budget[0]!=tick){budget[0]=tick;budget[1]=0;}
        for(var entry:contacts.entrySet())
        {
            if(budget[1]>=BLOCKS_PER_TICK)return false;
            var pos=entry.getKey();var state=level.getBlockState(pos);
            if(!state.equals(entry.getValue())||!naturalCanopy(pos,state)
                    ||!ForgeEventFactory.onEntityDestroyBlock(eva,pos,state))return false;
            if(!eva.isAlive()||!level.getGameRules().getBoolean(GameRules.RULE_MOBGRIEFING)
                    ||!level.getBlockState(pos).equals(state))return false;
            if(!level.destroyBlock(pos,true,eva))return false;
            budget[1]++;
        }
        return true;
    }
}

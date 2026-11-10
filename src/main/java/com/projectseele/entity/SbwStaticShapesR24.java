package com.projectseele.entity;

import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.tags.*;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.EmptyBlockGetter;
import net.minecraft.world.level.block.*;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.shapes.*;
import net.minecraftforge.event.TagsUpdatedEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.*;
import java.util.concurrent.atomic.LongAdder;

/** Exact static-shape fast path for the pinned SBW BlockState collision hook. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class SbwStaticShapesR24
{
    public static final ThreadLocal<Boolean> VANILLA=ThreadLocal.withInitial(()->false);
    public static final LongAdder hits=new LongAdder(),fallbacks=new LongAdder();
    private static final boolean DISABLED=Boolean.getBoolean("projectseele.vanillaVehicleShapes");
    private static final TagKey<Block> PASS=TagKey.create(Registries.BLOCK,new ResourceLocation("superbwarfare","vehicle_pass_through"));
    private static final java.util.concurrent.atomic.AtomicInteger EPOCH=new java.util.concurrent.atomic.AtomicInteger();
    private static final class Cache{int epoch=-1;final IdentityHashMap<BlockState,Integer> states=new IdentityHashMap<>();}
    private static final ThreadLocal<Cache> CACHES=ThreadLocal.withInitial(Cache::new);
    private static final ClassValue<Boolean> VEHICLE=new ClassValue<>()
    {
        @Override protected Boolean computeValue(Class<?> type)
        {for(Class<?> c=type;c!=null;c=c.getSuperclass())if(c.getName().equals("com.atsuishio.superbwarfare.entity.vehicle.base.VehicleEntity"))return true;return false;}
    };
    @SubscribeEvent public static void reload(TagsUpdatedEvent event){EPOCH.incrementAndGet();}
    public static int epoch(){return EPOCH.get();}
    public static boolean vehicle(Entity entity){return entity!=null&&VEHICLE.get(entity.getClass());}
    /** The UN base's parking ground on the reclaimed land; the client cannot read the saved site offset. */
    public static boolean unFleetArea(double x,double z)
    {return x>=3600&&x<=4800&&z>=136&&z<=1636;}
    /** Null means use the untouched original contextual lookup. */
    public static VoxelShape shape(BlockState state,CollisionContext context)
    {
        if(DISABLED||VANILLA.get()||!(context instanceof EntityCollisionContext ec)||!vehicle(ec.getEntity()))return null;
        if(state.is(Blocks.AIR)||state.is(Blocks.CAVE_AIR)||state.is(Blocks.VOID_AIR)){hits.increment();return Shapes.empty();}
        // Exact Block has no position/entity-dependent shape override. Slabs,
        // fences, dragon teeth, doors, fluids, custom machinery and moving
        // platforms always retain the original implementation.
        if(state.getBlock().getClass()!=Block.class||!state.getFluidState().isEmpty()){fallbacks.increment();return null;}
        Cache cache=CACHES.get();int epoch=EPOCH.get();if(cache.epoch!=epoch){cache.states.clear();cache.epoch=epoch;}
        Integer known=cache.states.get(state);
        if(known==null)
        {
            VoxelShape base=state.getCollisionShape(EmptyBlockGetter.INSTANCE,BlockPos.ZERO,CollisionContext.empty());
            known=state.is(PASS)&&!state.is(BlockTags.MINEABLE_WITH_AXE)||base.isEmpty()?1:Block.isShapeFullBlock(base)?2:3;
            cache.states.put(state,known);
        }
        if(known==3){fallbacks.increment();return null;}
        hits.increment();return known==1?Shapes.empty():Shapes.block();
    }
    private SbwStaticShapesR24(){}
}

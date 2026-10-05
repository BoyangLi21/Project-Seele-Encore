package com.projectseele.world;

import com.google.gson.JsonObject;
import com.projectseele.compat.CityUnionActivationR45;
import com.projectseele.compat.CityUnionPortableBootstrapR45;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.Tag;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.levelgen.structure.templatesystem.StructureTemplate.StructureBlockInfo;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.shapes.BooleanOp;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

/** Instance-local exact OR; Create retains all future/registration/invalidation lifecycle. */
public final class CityExactShapeUnionR45
{
    public static final String MARKER="R45FullFrameShapeUnion";
    private static final boolean ENABLED=CityUnionPortableBootstrapR45.requested();
    private static final ThreadLocal<Boolean> NATIVE_STOCK_PROBE=ThreadLocal.withInitial(()->false);
    private static final ThreadLocal<Boolean> LAST_BALANCED_CALL=ThreadLocal.withInitial(()->false);
    private static final java.util.concurrent.atomic.LongAdder balancedCalls=new java.util.concurrent.atomic.LongAdder();
    private static final java.util.concurrent.atomic.LongAdder stockCalls=new java.util.concurrent.atomic.LongAdder();
    private static final java.util.concurrent.atomic.LongAdder unchangedCalls=new java.util.concurrent.atomic.LongAdder();
    private CityExactShapeUnionR45() {}
    public static boolean enabled(){return ENABLED&&CityUnionActivationR45.backendEligible();}
    public static boolean nativeStockProbeR47(){return NATIVE_STOCK_PROBE.get();}
    public static boolean consumeBalancedCallR47()
    {boolean result=LAST_BALANCED_CALL.get();LAST_BALANCED_CALL.remove();return result;}

    /** One opt-in witness invokes the genuine transformed method's original body. */
    static List<AABB> actualOriginalSupplierR47(Object contraption)throws Exception
    {
        boolean previous=NATIVE_STOCK_PROBE.get();NATIVE_STOCK_PROBE.set(true);
        try{return actualSupplierR47(contraption);}
        finally{if(previous)NATIVE_STOCK_PROBE.set(true);else NATIVE_STOCK_PROBE.remove();}
    }
    static List<AABB> actualSupplierR47(Object contraption)throws Exception
    {
        var method=Class.forName("com.simibubi.create.content.contraptions.Contraption")
                .getDeclaredMethod("lambda$gatherBBsOffThread$24");method.setAccessible(true);
        @SuppressWarnings("unchecked") List<AABB> boxes=(List<AABB>)method.invoke(contraption);return boxes;
    }

    /** Reject before a new city transaction if the actual required ABI/mixins are unavailable. */
    public static String requiredActivationFailure()
    {
        if(!CityUnionActivationR45.required())return null;
        try
        {
            ClassLoader loader=CityExactShapeUnionR45.class.getClassLoader();
            Class.forName("com.simibubi.create.content.contraptions.Contraption",false,loader);
            Class.forName("com.simibubi.create.content.contraptions.AbstractContraptionEntity",false,loader);
            net.minecraftforge.fml.util.ObfuscationReflectionHelper.findMethod(VoxelShape.class,"m_7700_",Direction.Axis.class);
        }
        catch(ReflectiveOperationException|RuntimeException unavailable){return "Required native city input ABI unavailable: "+unavailable;}
        return CityUnionActivationR45.requiredFailure(enabled());
    }

    /** Null executes stock. All compatibility checks finish before any shape query. */
    public static List<AABB> calculate(Object contraption)throws Exception
    {
        LAST_BALANCED_CALL.set(false);
        if(!enabled())return null;
        Map<BlockPos,StructureBlockInfo> blocks;BlockGetter view;java.lang.reflect.Method coordinateGetter;
        try
        {
            Class<?> base=Class.forName("com.simibubi.create.content.contraptions.Contraption");
            var getter=base.getMethod("getBlocks");var originalMap=base.getDeclaredField("blocks");originalMap.setAccessible(true);
            var collision=base.getDeclaredField("collisionLevel");collision.setAccessible(true);
            coordinateGetter=net.minecraftforge.fml.util.ObfuscationReflectionHelper.findMethod(VoxelShape.class,"m_7700_",Direction.Axis.class);
            Object rawBlocks=originalMap.get(contraption),rawView=collision.get(contraption);
            if(getter.invoke(contraption)!=rawBlocks){unchangedCalls.increment();return null;}
            if(!(rawBlocks instanceof Map<?,?>)||!(rawView instanceof BlockGetter)){unchangedCalls.increment();return null;}
            @SuppressWarnings("unchecked") Map<BlockPos,StructureBlockInfo> checked=(Map<BlockPos,StructureBlockInfo>)rawBlocks;
            blocks=checked;view=(BlockGetter)rawView;
        }
        catch(java.lang.reflect.InvocationTargetException genuineGetterFailure){throw genuineGetterFailure;}
        catch(ReflectiveOperationException|SecurityException|java.lang.reflect.InaccessibleObjectException
                |net.minecraftforge.fml.util.ObfuscationReflectionHelper.UnableToFindMethodException compatibilityFailure)
        {unchangedCalls.increment();return null;}
        for(var entry:blocks.entrySet())if(!entry.getKey().equals(entry.getValue().pos()))
        {unchangedCalls.increment();return null;}
        List<VoxelShape> shapes=new ArrayList<>();
        @SuppressWarnings("unchecked") TreeSet<Double>[] coordinates=new TreeSet[]{new TreeSet<Double>(),new TreeSet<Double>(),new TreeSet<Double>()};
        for(var entry:blocks.entrySet())
        {
            BlockPos position=entry.getKey();StructureBlockInfo info=entry.getValue();
            VoxelShape original=info.state().getCollisionShape(view,position,CollisionContext.empty());
            if(original.isEmpty())continue;
            // Same complete native map, BE collision view, context, one query,
            // original iteration order and local move as the stock supplier.
            VoxelShape moved=original.move(position.getX(),position.getY(),position.getZ());shapes.add(moved);
            for(Direction.Axis axis:Direction.Axis.values())
            {
                var values=(it.unimi.dsi.fastutil.doubles.DoubleList)coordinateGetter.invoke(moved,axis);
                for(int i=0;i<values.size();i++)coordinates[axis.ordinal()].add(values.getDouble(i));
            }
        }
        double epsilon=Shapes.EPSILON;boolean separated=Double.isFinite(epsilon)&&epsilon>0;
        for(var axis:coordinates)
        {
            Double previous=null;
            for(double value:axis)
            {
                if(!Double.isFinite(value)||previous!=null&&value!=previous&&value-previous<=2*epsilon)separated=false;
                previous=value;
            }
        }
        if(!separated)
        {
            // Epsilon merging of nearby unequal coordinates is order-dependent.
            // Fold the same captured native inputs in their original order.
            VoxelShape stock=Shapes.empty();for(VoxelShape shape:shapes)stock=Shapes.joinUnoptimized(stock,shape,BooleanOp.OR);
            stockCalls.increment();return stock.optimize().toAabbs();
        }
        List<AABB> result=ExactBalancedUnionCandidateR45.balanced(shapes).toAabbs();
        balancedCalls.increment();LAST_BALANCED_CALL.set(true);return result;
    }
    public static boolean legacyCityOwner(CompoundTag entity)
    {
        if(!entity.getCompound("ForgeData").hasUUID("R45CityJourney"))return false;
        for(var tag:entity.getList("Tags",Tag.TAG_STRING))if(tag.getAsString().startsWith("r45_city_rigid/"))return true;
        return false;
    }
    public static long balancedCallsR47(){return balancedCalls.sum();}
    public static JsonObject diagnostics()
    {
        JsonObject r=new JsonObject();r.addProperty("opt_in_requested",ENABLED);r.addProperty("native_input_abi_accepted",CityUnionActivationR45.backendEligible());
        r.addProperty("balanced_calls",balancedCalls.sum());r.addProperty("original_left_fold_calls",stockCalls.sum());
        r.addProperty("original_supplier_fallback_calls",unchangedCalls.sum());r.addProperty("cross_instance_geometry_cache",false);
        r.addProperty("original_provider_lifecycle_retained",true);r.addProperty("required_release_mode",CityUnionActivationR45.required());
        r.addProperty("activation_policy",CityUnionPortableBootstrapR45.ACTIVATION);
        r.addProperty("runtime_scope",CityUnionPortableBootstrapR45.runtimeScope());
        r.addProperty("actual_create_class_resource",CityUnionActivationR45.actualCreateResource());
        r.addProperty("backend_eligible",CityUnionActivationR45.backendEligible());r.addProperty("backend_reason",CityUnionActivationR45.backendReason());
        var applied=new com.google.gson.JsonArray();CityUnionActivationR45.appliedMixins().forEach(applied::add);r.add("actual_mixin_post_apply",applied);
        r.addProperty("historical_full96_used_as_runtime_admission",false);return r;
    }
}

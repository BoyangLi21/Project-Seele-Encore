package com.projectseele.world;

import com.google.gson.JsonObject;
import com.projectseele.compat.CityUnionActivationR45;
import com.google.gson.JsonParser;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HexFormat;
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

/** Instance-local union only. Original Create future creation/publication/invalidation/removal stays untouched. */
public final class CityExactShapeUnionR45
{
    public static final String MARKER = "R45FullFrameShapeUnion";
    private static final boolean ENABLED = Boolean.getBoolean("projectseele.r45CityBalancedUnion");
    private static final Map<String,String> producers = new HashMap<>();
    private static final Map<Class<?>,Boolean> verifiedClasses = new java.util.concurrent.ConcurrentHashMap<>();
    private static volatile boolean proofChecked, proofValid;
    private static final java.util.concurrent.atomic.LongAdder balancedCalls=new java.util.concurrent.atomic.LongAdder();
    private static final java.util.concurrent.atomic.LongAdder stockCalls=new java.util.concurrent.atomic.LongAdder();
    private static final java.util.concurrent.atomic.LongAdder unchangedCalls=new java.util.concurrent.atomic.LongAdder();
    private CityExactShapeUnionR45() {}

    public static boolean enabled() { return ENABLED && proofValid(); }

    /** Required release mode rejects a new trip before context/WAL/world work. */
    public static String requiredActivationFailure()
    {
        if (!CityUnionActivationR45.required()) return null;
        boolean valid=enabled();
        if (valid)
        {
            try
            {
                Class.forName("com.simibubi.create.content.contraptions.AbstractContraptionEntity",false,CityExactShapeUnionR45.class.getClassLoader());
                for (String name:producers.keySet())
                    if (!classVerified(Class.forName(name,false,CityExactShapeUnionR45.class.getClassLoader())))
                        return "Current full96 producer resource changed: "+name;
            }
            catch (ReflectiveOperationException unavailable) { return "Required producer unavailable: "+unavailable; }
        }
        return CityUnionActivationR45.requiredFailure(valid);
    }

    private static synchronized boolean proofValid()
    {
        if (proofChecked) return proofValid;
        proofChecked = true;
        if (!ENABLED) return false;
        try
        {
            Path declared=Path.of(System.getProperty("projectseele.r45CityBalancedUnionProof", ""));
            if (!declared.isAbsolute()) return false;
            Path file=declared.normalize();
            String expected=System.getProperty("projectseele.r45CityBalancedUnionProofSHA256", "");
            if (!expected.matches("[0-9a-f]{64}")
                    || !expected.equals(hash(Files.readAllBytes(file)))) return false;
            JsonObject proof=JsonParser.parseString(Files.readString(file)).getAsJsonObject();
            if (!proof.get("passed").getAsBoolean() || !proof.get("full96_passed").getAsBoolean() || proof.get("cells").getAsInt()!=749242
                    || proof.get("complete_BE").getAsInt()!=1471 || !proof.get("actual_stock_supplier_invoked").getAsBoolean()
                    || !proof.get("per_original_shape_repeat_XOR_empty").getAsBoolean() || proof.get("world_written").getAsBoolean()
                    || proof.get("stock_provider_modified").getAsBoolean() || proof.getAsJsonArray("complete_plan_results").size()!=96) return false;
            java.util.Set<Integer> indexes=new java.util.HashSet<>();
            for (var raw:proof.getAsJsonArray("complete_plan_results"))
            {
                JsonObject row=raw.getAsJsonObject(); int index=row.get("index").getAsInt();
                if (index<0 || index>=96 || !indexes.add(index) || !row.get("per_original_shape_repeat_XOR_empty").getAsBoolean()
                        || !row.get("actual_stock_vs_balanced_XOR_empty").getAsBoolean() || !row.get("axis_answers_exact_equal").getAsBoolean()) return false;
                for (var entry:row.getAsJsonObject("actual_class_resource_SHA256s").entrySet())
                {
                    String old=producers.putIfAbsent(entry.getKey(),entry.getValue().getAsString());
                    if (old!=null && !old.equals(entry.getValue().getAsString())) return false;
                }
            }
            for (String name:new String[]{"com.simibubi.create.content.contraptions.Contraption", Shapes.class.getName(),VoxelShape.class.getName(),CollisionContext.class.getName()})
                if (!classVerified(Class.forName(name))) return false;
            proofValid=true;return true;
        }
        catch (Exception failure)
        {
            System.getLogger("Project SEELE city union").log(System.Logger.Level.WARNING,"Exact union proof unavailable; original stock union retained",failure);
            return false;
        }
    }

    private static boolean classVerified(Class<?> type)
    {
        return verifiedClasses.computeIfAbsent(type,key ->
        {
            try (var stream=key.getResourceAsStream('/'+key.getName().replace('.','/')+".class"))
            { return stream!=null && producers.containsKey(key.getName()) && producers.get(key.getName()).equals(hash(stream.readAllBytes())); }
            catch (Exception failure) { return false; }
        });
    }

    /** Null means execute the original supplier body; no collider provider or block map is changed. */
    public static List<AABB> calculate(Object contraption) throws Exception
    {
        if (!enabled()) return null;
        Map<BlockPos,StructureBlockInfo> blocks; BlockGetter view; java.lang.reflect.Method coordinateGetter;
        try
        {
            Class<?> base=Class.forName("com.simibubi.create.content.contraptions.Contraption");
            var getter=base.getMethod("getBlocks");
            var collision=base.getDeclaredField("collisionLevel"); collision.setAccessible(true);
            coordinateGetter=net.minecraftforge.fml.util.ObfuscationReflectionHelper.findMethod(VoxelShape.class,"m_7700_",Direction.Axis.class);
            Object rawBlocks=getter.invoke(contraption),rawView=collision.get(contraption);
            if (!(rawBlocks instanceof Map<?,?>) || !(rawView instanceof BlockGetter)) { unchangedCalls.increment();return null; }
            @SuppressWarnings("unchecked") Map<BlockPos,StructureBlockInfo> checked=(Map<BlockPos,StructureBlockInfo>)rawBlocks;
            blocks=checked;view=(BlockGetter)rawView;
        }
        catch (java.lang.reflect.InvocationTargetException genuineGetterFailure) { throw genuineGetterFailure; }
        catch (ReflectiveOperationException | SecurityException | java.lang.reflect.InaccessibleObjectException
                | net.minecraftforge.fml.util.ObfuscationReflectionHelper.UnableToFindMethodException compatibilityFailure)
        { unchangedCalls.increment();return null; }
        // All reflective setup/access/type and producer checks finish before any shape query.
        for (var entry:blocks.entrySet()) if (!entry.getKey().equals(entry.getValue().pos()) || !classVerified(entry.getValue().state().getBlock().getClass()))
        { unchangedCalls.increment();return null; }
        if (!classVerified(view.getClass())) { unchangedCalls.increment();return null; }
        List<VoxelShape> shapes=new ArrayList<>();
        @SuppressWarnings("unchecked") TreeSet<Double>[] coordinates=new TreeSet[]{new TreeSet<Double>(),new TreeSet<Double>(),new TreeSet<Double>()};
        for (var entry:blocks.entrySet())
        {
            BlockPos position=entry.getKey();StructureBlockInfo info=entry.getValue();
            VoxelShape original=info.state().getCollisionShape(view,position,CollisionContext.empty());
            if (original.isEmpty()) continue;
            // Shape inputs are the same full block/BE/view and local coordinates used by stock, queried once in native iteration order.
            VoxelShape moved=original.move(position.getX(),position.getY(),position.getZ());shapes.add(moved);
            for (Direction.Axis axis:Direction.Axis.values())
            {
                var values=(it.unimi.dsi.fastutil.doubles.DoubleList)coordinateGetter.invoke(moved,axis);
                for (int i=0;i<values.size();i++) coordinates[axis.ordinal()].add(values.getDouble(i));
            }
        }
        double epsilon=Shapes.EPSILON; // Actual public compile-time constant; no runtime field-name lookup.
        boolean separated=Double.isFinite(epsilon) && epsilon>0;
        for (var axis:coordinates)
        {
            Double previous=null;
            for (double value:axis)
            {
                if (!Double.isFinite(value) || previous!=null && value!=previous && value-previous<=2*epsilon) separated=false;
                previous=value;
            }
        }
        if (!separated)
        {
            // Nearby non-identical coordinates can make epsilon-merging order dependent. Preserve the original left fold of these actual inputs.
            VoxelShape stock=Shapes.empty();for (VoxelShape shape:shapes)stock=Shapes.joinUnoptimized(stock,shape,BooleanOp.OR);
            stockCalls.increment();return stock.optimize().toAabbs();
        }
        balancedCalls.increment();return ExactBalancedUnionCandidateR45.balanced(shapes).toAabbs();
    }

    public static boolean legacyCityOwner(CompoundTag entity)
    {
        if (!entity.getCompound("ForgeData").hasUUID("R45CityJourney")) return false;
        for (var tag:entity.getList("Tags",Tag.TAG_STRING)) if (tag.getAsString().startsWith("r45_city_rigid/")) return true;
        return false;
    }

    private static String hash(byte[] bytes) throws Exception
    { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)); }

    public static JsonObject diagnostics()
    {
        JsonObject report=new JsonObject();report.addProperty("opt_in_requested",ENABLED);report.addProperty("proof_valid",proofValid);
        report.addProperty("balanced_calls",balancedCalls.sum());report.addProperty("original_left_fold_calls",stockCalls.sum());
        report.addProperty("original_supplier_fallback_calls",unchangedCalls.sum());report.addProperty("cross_instance_geometry_cache",false);
        report.addProperty("original_provider_lifecycle_retained",true);
        report.addProperty("required_release_mode",CityUnionActivationR45.required());
        report.addProperty("actual_create_class_sha256",CityUnionActivationR45.actualCreateSHA256());
        report.addProperty("backend_eligible",CityUnionActivationR45.backendEligible());
        report.addProperty("backend_reason",CityUnionActivationR45.backendReason());
        com.google.gson.JsonArray applied=new com.google.gson.JsonArray();CityUnionActivationR45.appliedMixins().forEach(applied::add);report.add("actual_mixin_post_apply",applied);
        return report;
    }
}

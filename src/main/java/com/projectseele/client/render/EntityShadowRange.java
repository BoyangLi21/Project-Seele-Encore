package com.projectseele.client.render;

import com.projectseele.ProjectSeele;
import com.projectseele.config.SeeleConfig;
import com.projectseele.world.SbwIdlePause;
import java.lang.invoke.MethodHandle;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.phys.AABB;

/**
 * Which entities a shader pack's shadow pass leaves out: small ones far from the camera.
 *
 * The shadow pass draws every entity a second time. For a dropped item or a parked vehicle a hundred blocks away
 * that second drawing buys a shadow of a few pixels. Vanilla's own entity shadows stop at 16 blocks.
 *
 * Never left out: anything 12 blocks or more across (the Evangelions and the Angels), every entity of this mod
 * (doors and platforms are small boxes that draw large), and entities that opt out of culling. Vehicles get the
 * longer of the two distances whatever their box. The distances are client settings, and 0 turns a rule off.
 */
public final class EntityShadowRange
{
    /** Longest side of the culling box, in blocks: below SMALL the short distance applies, below LARGE the long one. */
    private static final double SMALL = 4, LARGE = 12;
    private static final MethodHandle SHADOW_PASS;
    private static final ClassValue<Boolean> OURS = new ClassValue<>()
    {
        @Override protected Boolean computeValue(Class<?> type) { return type.getName().startsWith("com.projectseele."); }
    };
    private static boolean reported;
    private static long leftOut;

    static
    {
        MethodHandle pass = null;
        try
        {
            pass = MethodHandles.publicLookup().findStatic(Class.forName("net.irisshaders.iris.shadows.ShadowRenderingState"),
                    "areShadowsCurrentlyBeingRendered", MethodType.methodType(boolean.class));
        }
        catch (ReflectiveOperationException | LinkageError absent) { pass = null; }
        SHADOW_PASS = pass;
    }

    private EntityShadowRange() {}

    /** True while Oculus draws its shadow map; false without Oculus. */
    public static boolean shadowPass()
    {
        if (SHADOW_PASS == null) return false;
        try { return (boolean) SHADOW_PASS.invokeExact(); }
        catch (Throwable changed) { return false; }
    }

    public static boolean leftOut(Entity entity, double cameraX, double cameraY, double cameraZ)
    {
        if (entity.noCulling || OURS.get(entity.getClass())) return false;
        AABB box = entity.getBoundingBoxForCulling();
        double size = Math.max(box.maxX - box.minX, Math.max(box.maxY - box.minY, box.maxZ - box.minZ));
        if (size >= LARGE) return false;
        // An aircraft's box is its cabin, a few blocks, under wings five times as wide: no vehicle counts as small.
        if (entity instanceof SbwIdlePause.Vehicle) size = Math.max(size, SMALL);
        double limit = size < SMALL ? SeeleConfig.SMALL_ENTITY_SHADOW_DISTANCE.get() : SeeleConfig.MEDIUM_ENTITY_SHADOW_DISTANCE.get();
        if (limit <= 0) return false;
        double dx = Math.max(0, Math.max(box.minX - cameraX, cameraX - box.maxX));
        double dy = Math.max(0, Math.max(box.minY - cameraY, cameraY - box.maxY));
        double dz = Math.max(0, Math.max(box.minZ - cameraZ, cameraZ - box.maxZ));
        if (dx * dx + dy * dy + dz * dz <= limit * limit) return false;
        leftOut++;
        if (!reported)
        {
            reported = true;
            ProjectSeele.LOGGER.info("Entity shadow range active: under {} blocks across no shadow beyond {} blocks, under {} beyond {}",
                    (int) SMALL, SeeleConfig.SMALL_ENTITY_SHADOW_DISTANCE.get(), (int) LARGE, SeeleConfig.MEDIUM_ENTITY_SHADOW_DISTANCE.get());
        }
        return true;
    }

    /** Entities left out of shadow passes so far, for measurements. */
    public static long leftOutCount() { return leftOut; }
}

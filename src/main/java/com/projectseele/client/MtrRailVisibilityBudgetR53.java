package com.projectseele.client;

import java.lang.reflect.Field;

/** Large diagonal rail bounds contain mostly air; scanning every voxel costs
 * more than submitting the rail to the normal depth-tested renderer. */
public final class MtrRailVisibilityBudgetR53
{
    private record VectorFields(Field x, Field y, Field z) { }
    private record RailFields(Field start, Field end, Field visible) { }
    private static final ClassValue<VectorFields> VECTORS = new ClassValue<>()
    {
        @Override protected VectorFields computeValue(Class<?> type)
        {
            try { return new VectorFields(type.getField("x"), type.getField("y"), type.getField("z")); }
            catch (ReflectiveOperationException error) { throw new IllegalStateException(error); }
        }
    };
    private static final ClassValue<RailFields> RAILS = new ClassValue<>()
    {
        @Override protected RailFields computeValue(Class<?> type)
        {
            try { return new RailFields(type.getField("startVector"), type.getField("endVector"), type.getField("shouldRender")); }
            catch (ReflectiveOperationException error) { throw new IllegalStateException(error); }
        }
    };
    private static volatile long oversizedBounds;

    public static Runnable retainLargeRail(Object rail)
    {
        try
        {
            var fields = RAILS.get(rail.getClass());
            Object start = fields.start.get(rail), end = fields.end.get(rail);
            var vector = VECTORS.get(start.getClass());
            double x = Math.abs(vector.x.getDouble(end) - vector.x.getDouble(start)) + 2;
            double y = Math.abs(vector.y.getDouble(end) - vector.y.getDouble(start)) + 2;
            double z = Math.abs(vector.z.getDouble(end) - vector.z.getDouble(start)) + 2;
            if (x * y * z <= 32768) return null;
            oversizedBounds++;
            // This is a conservative visible result, never an occlusion claim.
            // Native range, geometry, depth testing and simulation stay intact.
            return () ->
            {
                try { fields.visible.setBoolean(rail, true); }
                catch (IllegalAccessException error) { throw new IllegalStateException(error); }
            };
        }
        catch (IllegalAccessException error) { throw new IllegalStateException(error); }
    }

    public static long oversizedBounds() { return oversizedBounds; }
    private MtrRailVisibilityBudgetR53() { }
}

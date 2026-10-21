package com.projectseele.compat;

import it.unimi.dsi.fastutil.longs.LongArrayList;
import java.lang.reflect.Field;

/** A merged DH column cannot contain a sample above all four source columns. */
public final class DhColumnExtentR53
{
    private static final ClassValue<Field> COLUMNS = new ClassValue<>()
    {
        @Override protected Field computeValue(Class<?> type)
        {
            try { return type.getField("dataPoints"); }
            catch (ReflectiveOperationException error)
            { throw new IllegalStateException("DH full-column layout changed", error); }
        }
    };

    public static void trimMerged(Object source, int x, int z, LongArrayList merged)
    {
        try
        {
            LongArrayList[] columns = (LongArrayList[]) COLUMNS.get(source.getClass()).get(source);
            int maximum = 0;
            for (int dx = 0; dx < 2; dx++)
                for (int dz = 0; dz < 2; dz++)
                {
                    LongArrayList column = columns[(x + dx) * 64 + z + dz];
                    if (column == null || column.isEmpty()) continue;
                    // FullDataSourceV2 requires descending, non-overlapping spans.
                    long top = column.getLong(0);
                    maximum = Math.max(maximum, bottom(top) + height(top));
                }
            trim(merged, maximum);
        }
        catch (IllegalAccessException error)
        { throw new IllegalStateException("Cannot read DH source-column extent", error); }
    }

    public static void trim(LongArrayList column, int exclusiveMaximum)
    {
        for (int i = column.size() - 1; i >= 0; i--)
        {
            long value = column.getLong(i);
            int bottom = bottom(value);
            if (bottom >= exclusiveMaximum) column.removeLong(i);
            else if (bottom + height(value) > exclusiveMaximum)
                column.set(i, (value & ~(4095L << 32))
                        | ((long) (exclusiveMaximum - bottom) << 32));
        }
    }

    private static int bottom(long value) { return (int) ((value >>> 44) & 4095); }
    private static int height(long value) { return (int) ((value >>> 32) & 4095); }
    private DhColumnExtentR53() {}
}

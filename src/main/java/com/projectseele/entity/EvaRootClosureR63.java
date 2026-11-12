package com.projectseele.entity;

import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.Map;
import java.util.function.Supplier;

/**
 * Where an attack clip's root path stops being the attack.
 * <p>
 * A captured clip often ends by taking its root back to where it began, within its last frames,
 * so that it loops. Played as the body's travel, that return is a snap: Unit-02's heavy sword
 * strike lunges 54 blocks and was then carried all 54 back in six ticks, its two lighter strikes
 * 15 blocks back in one tick each, and the kick 4.9 blocks back in its last tick. The body is
 * left where the strike took it: from the point where such a closing return begins, the path is
 * held.
 * <p>
 * A closing return is the last stretch of the path that only draws back, when it takes no more
 * than a fifth of the clip and covers at least four blocks. A clip that backs away through most
 * of its length (the heavy punch settling, an evasion) is the action itself and is untouched.
 */
public final class EvaRootClosureR63
{
    private static final double LAST=.2,FAR=4;
    private static final Map<Object,Integer> HELD=Collections.synchronizedMap(new IdentityHashMap<>());

    /**
     * The index from which the path is held: its last point, or the point where a closing return
     * begins. {@code forward[i]} is how far point i lies ahead of the first, in blocks.
     */
    public static int holdFrom(double[] forward)
    {
        int last=forward.length-1,from=last;
        while(from>0&&forward[from-1]>=forward[from])from--;
        if(from==last||from==0)return last;
        return last-from<=LAST*last&&forward[from]-forward[last]>=FAR?from:last;
    }

    /** {@link #holdFrom(double[])} once per clip object. */
    public static int holdFrom(Object clip,Supplier<double[]> forward)
    {
        return HELD.computeIfAbsent(clip,key->holdFrom(forward.get()));
    }

    /** Clip metres to blocks of the drawn unit. */
    public static double blocks(double metres){return metres*112.0D*EvaScale.RENDER_SCALE/16.0D;}

    private EvaRootClosureR63(){}
}

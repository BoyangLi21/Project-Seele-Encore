package com.projectseele.client.render;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;

import org.joml.Matrix4f;

import com.projectseele.client.AircraftRenderClockR21;
import com.projectseele.entity.EvaUnit01Entity;

/**
 * R63: how far the drawn surface of a part lies under its rigid outline while a unit lies prone.
 * <p>
 * The grounding sets a body down by the rigid outline of each part. A part's rim is drawn by its neighbour's bone
 * (the belly's by the thighs'), and with the thighs drawn up in a crawl the belly's drawn surface lies 0.6 to 2.1
 * blocks under its outline: a body set down by the outlines lay that far in the ground. The mesh layer has the
 * skinned vertices in hand as it draws a part and measures the difference there; the grounding of the next frame
 * takes it off. Over a crawl's stroke it moves 0.1 to 0.2 blocks from one frame to the next.
 */
final class EvaProneSkinR63
{
    private record Gap(float value,long time) {}
    private static final Map<EvaUnit01Entity,Map<String,Gap>> GAPS=new java.util.WeakHashMap<>();
    /** What a prone body can lie on: trunk and legs. Arms are raised to the ground after the body is set down. */
    private static final Set<String> PARTS=Set.of("torso_lower","torso_upper","leg_l","leg_r","shin_l","shin_r");
    /** A measurement older than this is not used (nanoseconds): the part is not being drawn. */
    private static final long FRESH=250_000_000L;
    /** The most a measurement is taken for (blocks); beyond it something other than a rim is being read. */
    private static final float MOST=3F;
    static final boolean ENABLED=!"false".equals(System.getProperty("projectseele.proneSkinR63"));
    /** -Dprojectseele.poseDiag=true: the time the measuring takes and the largest gap, once a second, in the log. */
    private static final boolean TOLD=Boolean.getBoolean("projectseele.poseDiag");
    private static long spent,toldAt;
    private static int calls,vertices;
    private static float largest;

    static boolean wanted(EvaUnit01Entity eva,String part){return ENABLED&&eva.isPilotProne()&&PARTS.contains(part);}

    /**
     * The mesh layer, drawing a part of a prone unit: its vertices as they rest and as they are drawn, in the same
     * layout, and the transform that takes the layer's points to the world. Only heights matter, so only the row of
     * the transform that makes a height is used; the part's pivot and place cancel between the two.
     */
    static void measure(EvaUnit01Entity eva,String part,float[] rest,float[] drawn,int stride,Matrix4f world)
    {
        long began=TOLD?System.nanoTime():0;
        float gap=0;
        if(rest!=drawn)
        {
            // The layer's point is (-x, y, z) / 16 of the vertex.
            float a=-world.m01()/16,b=world.m11()/16,c=world.m21()/16,outline=Float.POSITIVE_INFINITY,surface=Float.POSITIVE_INFINITY;
            int end=Math.min(rest.length,drawn.length);
            for(int i=0;i+2<end;i+=stride)
            {
                outline=Math.min(outline,a*rest[i]+b*rest[i+1]+c*rest[i+2]);
                surface=Math.min(surface,a*drawn[i]+b*drawn[i+1]+c*drawn[i+2]);
            }
            if(Float.isFinite(outline)&&Float.isFinite(surface))gap=Math.max(-MOST,Math.min(MOST,outline-surface));
        }
        long now=AircraftRenderClockR21.frameNanos();
        var parts=GAPS.computeIfAbsent(eva,id->new HashMap<>());
        var old=parts.get(part);
        // Drawn more than once in a frame (a second layer of the same part): the lowest surface counts.
        parts.put(part,new Gap(old!=null&&old.time()==now?Math.max(old.value(),gap):gap,now));
        if(TOLD)
        {
            spent+=System.nanoTime()-began;calls++;vertices+=rest.length/Math.max(1,stride);largest=Math.max(largest,gap);
            if(now-toldAt>1_000_000_000L)
            {
                com.projectseele.ProjectSeele.LOGGER.info("R63PRONESKIN {} parts measured in the last second, {} vertices, {} ms; largest gap {}",
                        calls,vertices,String.format(java.util.Locale.ROOT,"%.2f",spent/1e6),String.format(java.util.Locale.ROOT,"%.2f",largest));
                spent=0;calls=0;vertices=0;largest=0;toldAt=now;
            }
        }
    }

    /** How far under its rigid outline the part was last drawn (blocks, 0 when not known). */
    static float gap(EvaUnit01Entity eva,String part)
    {
        if(!ENABLED)return 0;
        var parts=GAPS.get(eva);var gap=parts==null?null:parts.get(part);
        return gap==null||AircraftRenderClockR21.frameNanos()-gap.time()>FRESH?0:gap.value();
    }

    private EvaProneSkinR63() {}
}

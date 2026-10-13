package com.projectseele.world;

/** Measured original rail elevation: flat lead, cosine-rounded grade, flat tail. */
public record NervRampProfileR52(double flatBefore,double slopeRun,double blend)
{
    public NervRampProfileR52
    {
        if(!Double.isFinite(flatBefore)||!Double.isFinite(slopeRun)||!Double.isFinite(blend)
                ||flatBefore<0||slopeRun<=0||blend<=0||2*blend>slopeRun)
            throw new IllegalArgumentException("Finite original ramp profile required");
    }
    public void checkLength(double horizontal)
    {if(!Double.isFinite(horizontal)||horizontal<flatBefore+slopeRun)throw new IllegalArgumentException("Original grade leaves its measured route");}
    private double rounded(double distance)
    {return distance*.5-blend/(2*Math.PI)*Math.sin(Math.PI*distance/blend);}
    public double heightFraction(double horizontal,double fraction)
    {
        checkLength(horizontal);
        if(!Double.isFinite(fraction)||fraction<0||fraction>1)throw new IllegalArgumentException("Ramp fraction outside original route");
        double d=Math.max(0,Math.min(slopeRun,horizontal*fraction-flatBefore)),effective=slopeRun-blend;
        return(d<blend?rounded(d):d>slopeRun-blend?effective-rounded(slopeRun-d):d-blend*.5)/effective;
    }
    public NervRampProfileR52 reversed(double horizontal)
    {checkLength(horizontal);return new NervRampProfileR52(horizontal-flatBefore-slopeRun,slopeRun,blend);}
    public boolean sameGeometry(NervRampProfileR52 other)
    {return other!=null&&Math.abs(flatBefore-other.flatBefore)<1e-9&&Math.abs(slopeRun-other.slopeRun)<1e-9&&Math.abs(blend-other.blend)<1e-9;}
    /** Upper bound of |p''(t)| on a requested fraction interval. */
    public double secondDerivativeBound(double horizontal,double rise,double fractionSpan)
    {checkLength(horizontal);return Math.abs(rise)*Math.PI/(2*blend*(slopeRun-blend))*horizontal*horizontal*fractionSpan*fractionSpan;}
}

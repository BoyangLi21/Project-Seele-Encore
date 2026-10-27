package com.projectseele.world;

import com.google.gson.*;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Explicit Root world-space foot centres. No World, actor, pose or clock.
 * Arc-length brackets use Bezier chord/control-polygon bounds, including
 * subdivision roundoff. Inverse arc length is never treated as exact. */
public final class NervCentrelineCurveR52
{
    public enum Type { LINE, QUINTIC_BEZIER }
    public record Segment(Type type,List<Vec3> controls)
    {
        public Segment {
            Objects.requireNonNull(type);controls=List.copyOf(controls);
            require(controls.size()==(type==Type.LINE?2:6),"LINE needs2 / QUINTIC_BEZIER needs6 actual controls");
            for(var p:controls)finite(p);
            require(controls.get(1).distanceToSqr(controls.get(0))>0
                    &&controls.get(controls.size()-1).distanceToSqr(controls.get(controls.size()-2))>0,
                    "Zero endpoint derivative is not a continuous running path");
        }
    }
    private record Leaf(int segment,double from,double to,Vec3[] controls,double length,double error,double speedUpper,double curvature){}
    private record Evaluation(Vec3 point,Vec3 tangent){}
    private static final double LENGTH_GAP=1e-6;
    private static final int INVERSE_BITS=48;
    private final List<Segment> segments;
    private final List<Leaf> leaves=new ArrayList<>();
    private final double[] prefix;
    private final double length,lengthError,curvatureBound,pointError;
    private double builtCurvature,builtPointRoundoff;
    private final Map<Long,Evaluation> evaluated=new LinkedHashMap<>();

    public NervCentrelineCurveR52(List<Segment> source)
    {
        segments=List.copyOf(source);require(!segments.isEmpty(),"Explicit nonempty centre curve required");
        for(int i=1;i<segments.size();i++) {
            var a=segments.get(i-1).controls();var b=segments.get(i).controls();
            require(a.get(a.size()-1).equals(b.get(0)),"Disconnected actual centre-curve segments");
            require(unit(a.get(a.size()-1).subtract(a.get(a.size()-2))).distanceTo(unit(b.get(1).subtract(b.get(0))))<=1e-7,
                    "Centre-curve tangent changes instantaneously at segment join");
        }
        for(int i=0;i<segments.size();i++)build(i,segments.get(i).controls().toArray(Vec3[]::new),0,1,0);
        prefix=new double[leaves.size()+1];double errors=0,speed=0;
        for(int i=0;i<leaves.size();i++){var leaf=leaves.get(i);prefix[i+1]=prefix[i]+leaf.length;errors+=leaf.error;speed=Math.max(speed,leaf.speedUpper);}
        length=prefix[prefix.length-1];require(Double.isFinite(length)&&length>0,"Finite positive actual curve length required");
        lengthError=errors+Math.ulp(length)*(leaves.size()+4);
        curvatureBound=builtCurvature;
        // A target f*L and its inverse cumulative arc each contribute at most
        // the full length bracket error. The residual bisection width and
        // evaluated point rounding remain explicit as well.
        pointError=2*lengthError+speed*Math.scalb(1D,-INVERSE_BITS)+2*builtPointRoundoff+Math.ulp(length)*64;
        require(Double.isFinite(pointError)&&Double.isFinite(curvatureBound),"Unbounded actual centre curve");
    }
    private void build(int segment,Vec3[] c,double from,double to,int depth)
    {
        int degree=c.length-1;double scale=1;
        for(var p:c)scale=Math.max(scale,Math.max(Math.abs(p.x),Math.max(Math.abs(p.y),Math.abs(p.z))));
        // Each midpoint subdivision has degree successive half/add levels.
        // Eight coordinate ulps per depth dominate all five levels here.
        double vertexError=Math.sqrt(3)*Math.ulp(scale)*16*(depth+2);
        double chord=c[0].distanceTo(c[degree]),polygon=0,maxSpeed=0,minSpeed=Double.POSITIVE_INFINITY;
        for(int i=0;i<degree;i++)polygon+=c[i].distanceTo(c[i+1]);
        Vec3 axis=chord>0?unit(c[degree].subtract(c[0])):Vec3.ZERO;
        for(int i=0;i<degree;i++) {
            var d=c[i+1].subtract(c[i]).scale(degree);maxSpeed=Math.max(maxSpeed,d.length());
            minSpeed=Math.min(minSpeed,d.dot(axis));
        }
        double derivativeError=2*degree*vertexError+Math.ulp(Math.max(1,maxSpeed))*64;
        minSpeed-=derivativeError;
        double gap=Math.max(0,polygon-chord);
        if(minSpeed<=0||gap>LENGTH_GAP*(to-from)/segments.size()) {
            require(depth<24&&leaves.size()<65536,"Actual curve regularity/length bound exceeds admitted subdivisions");
            var split=split(c,.5);double mid=(from+to)*.5;
            build(segment,split[0],from,mid,depth+1);build(segment,split[1],mid,to,depth+1);return;
        }
        double normError=Math.ulp(Math.max(1,polygon))*64;
        double low=Math.max(0,chord-2*vertexError-normError);
        double high=polygon+2*degree*vertexError+degree*normError;
        double second=0;
        for(int i=0;i+2<c.length;i++)second=Math.max(second,c[i+2].subtract(c[i+1].scale(2)).add(c[i]).scale(degree*(degree-1)).length());
        second+=4*degree*(degree-1)*vertexError+Math.ulp(Math.max(1,second))*64;
        builtCurvature=Math.max(builtCurvature,second/(minSpeed*minSpeed));
        builtPointRoundoff=Math.max(builtPointRoundoff,vertexError);
        leaves.add(new Leaf(segment,from,to,c,(low+high)*.5,(high-low)*.5,maxSpeed+derivativeError,second/(minSpeed*minSpeed)));
    }
    private static Vec3[][] split(Vec3[] points,double t)
    {
        int n=points.length;var work=points.clone();var left=new Vec3[n];var right=new Vec3[n];left[0]=work[0];right[n-1]=work[n-1];
        for(int k=1;k<n;k++){for(int i=0;i<n-k;i++)work[i]=work[i].lerp(work[i+1],t);left[k]=work[0];right[n-k-1]=work[n-k-1];}
        return new Vec3[][]{left,right};
    }
    private static Vec3 evaluate(Vec3[] controls,double t)
    {if(t==0)return controls[0];if(t==1)return controls[controls.length-1];var p=controls.clone();for(int k=p.length-1;k>0;k--)for(int i=0;i<k;i++)p[i]=p[i].lerp(p[i+1],t);return p[0];}
    private static double partialLength(Vec3[] controls,double t)
    {
        if(t==0)return 0;var c=t==1?controls:split(controls,t)[0];double polygon=0;for(int i=1;i<c.length;i++)polygon+=c[i].distanceTo(c[i-1]);return(c[0].distanceTo(c[c.length-1])+polygon)*.5;
    }
    private synchronized Evaluation evaluation(double fraction)
    {
        require(Double.isFinite(fraction)&&fraction>=0&&fraction<=1,"Arc fraction outside [0,1]");
        long key=Double.doubleToLongBits(fraction);var cached=evaluated.get(key);if(cached!=null)return cached;
        int index;double parameter;
        if(fraction==0){index=0;parameter=0;}
        else if(fraction==1){index=leaves.size()-1;parameter=1;}
        else {
            double target=fraction*length;int low=0,high=leaves.size();while(low+1<high){int mid=(low+high)>>>1;if(prefix[mid]<=target)low=mid;else high=mid;}index=low;
            var leaf=leaves.get(index);double local=Math.max(0,Math.min(leaf.length,target-prefix[index])),a=0,b=1;
            // Partial control-polygon/chord midpoint stays inside that leaf's
            // existing length bracket; no Simpson error estimate is assumed.
            for(int i=0;i<INVERSE_BITS;i++){double mid=(a+b)*.5;if(partialLength(leaf.controls,mid)<local)a=mid;else b=mid;}
            parameter=(a+b)*.5;
        }
        var leaf=leaves.get(index);double u=leaf.from+(leaf.to-leaf.from)*parameter;
        var c=segments.get(leaf.segment).controls().toArray(Vec3[]::new);var derivatives=new Vec3[c.length-1];
        for(int i=0;i<derivatives.length;i++)derivatives[i]=c[i+1].subtract(c[i]).scale(c.length-1);
        var result=new Evaluation(evaluate(c,u),unit(evaluate(derivatives,u)));
        if(evaluated.size()>=256)evaluated.clear();evaluated.put(key,result);return result;
    }
    public Vec3 point(double arcFraction){return evaluation(arcFraction).point;}
    public Vec3 tangent(double arcFraction){return evaluation(arcFraction).tangent;}
    public double length(){return length;}
    public double lengthErrorBound(){return lengthError;}
    public double pointErrorBound(){return pointError;}
    public double curvatureBound(){return curvatureBound;}
    public double curvatureBound(double from,double to)
    {
        require(Double.isFinite(from)&&Double.isFinite(to)&&from>=0&&to<=1&&to>=from,"Actual monotone arc interval required");
        double low=from*length-pointError,high=to*length+pointError,bound=0;
        // Bracket expansion includes target-length and inverse-arc errors;
        // no leaf can be skipped solely because its estimated arc endpoint
        // lies on the other side of a floating-point interval boundary.
        int a=0,b=leaves.size();while(a<b){int mid=(a+b)>>>1;if(prefix[mid+1]<low)a=mid+1;else b=mid;}
        for(int i=a;i<leaves.size()&&prefix[i]<=high;i++)bound=Math.max(bound,leaves.get(i).curvature);
        return bound;
    }
    public double secondDerivativeBound(double from,double to)
    {double upper=length+lengthError,span=to-from;return curvatureBound(from,to)*upper*upper*span*span;}

    /** Arc-metre bounds for the projected transverse/normal/tangent basis.
     * These cover independent guide rotation, which a Root translation
     * certificate alone cannot enclose. */
    public Vec3 transportedFrameSecondDerivativeBound(double from,double to,Vec3 transverse)
    {
        curvatureBound(from,to);
        require(Math.abs(transverse.lengthSqr()-1)<1e-8,"Unit fixed transverse axis required");
        for(int i=1;i<segments.size();i++)
            require(endpointTangentDerivative(segments.get(i-1),true).distanceTo(
                endpointTangentDerivative(segments.get(i),false))<1e-7,"Guide frame derivative jumps at curve join");
        double low=from*length-pointError,high=to*length+pointError,X=0,Y=0,Z=0;
        int first=Arrays.binarySearch(prefix,Math.max(0,low));if(first<0)first=Math.max(0,-first-2);
        for(int i=first;i<leaves.size()&&prefix[i]<=high;i++)
        {
            var leaf=leaves.get(i);var c=segments.get(leaf.segment()).controls().toArray(Vec3[]::new);int degree=c.length-1;
            if(degree==1)continue;
            var velocity=derivativeControls(c);var acceleration=derivativeControls(velocity);var jerk=derivativeControls(acceleration);
            velocity=restrictedControls(velocity,leaf.from(),leaf.to());
            acceleration=restrictedControls(acceleration,leaf.from(),leaf.to());
            jerk=restrictedControls(jerk,leaf.from(),leaf.to());
            var axis=velocity[0].normalize();
            double minSpeed=Double.POSITIVE_INFINITY,along=0,second=0,third=0,scale=1;
            for(var p:c)scale=Math.max(scale,Math.max(Math.abs(p.x),Math.max(Math.abs(p.y),Math.abs(p.z))));
            double epsilon=Math.ulp(scale)*8192;
            for(var v:velocity)
            {
                minSpeed=Math.min(minSpeed,v.dot(axis));along=Math.max(along,Math.abs(v.dot(transverse)));
            }
            for(var v:acceleration)second=Math.max(second,v.length());
            for(var v:jerk)third=Math.max(third,v.length());
            minSpeed-=epsilon;along+=epsilon;second+=epsilon;third+=epsilon;
            require(minSpeed>0,"Guide tangent has no positive derivative bound");
            double ratio=along/minSpeed,q=Math.sqrt(Math.max(0,1-ratio*ratio));
            require(q>.1,"Projected guide frame has no finite separation from its singularity");
            double d1=second/(minSpeed*minSpeed);
            double d2=third/(minSpeed*minSpeed*minSpeed)+6*d1*d1;
            double x1=2*d1/q,x2=(2*d2+2*d1*d1)/q+12*d1*d1/(q*q);
              X=Math.max(X,x2);Y=Math.max(Y,d2+2*d1*x1+x2);Z=Math.max(Z,d2);
        }
        return new Vec3(X,Y,Z);
    }

    private static Vec3[] derivativeControls(Vec3[] source)
    {var result=new Vec3[source.length-1];for(int i=0;i<result.length;i++)result[i]=source[i+1].subtract(source[i]).scale(result.length);return result;}

    private static Vec3[] restrictedControls(Vec3[] source,double from,double to)
    {var left=to==1?source:split(source,to)[0];return from==0?left:split(left,from/to)[1];}

    private static Vec3 endpointTangentDerivative(Segment segment,boolean end)
    {
        var c=segment.controls();int n=c.size()-1;if(n==1)return Vec3.ZERO;
        int a=end?n-2:0;var v=(end?c.get(n).subtract(c.get(n-1)):c.get(1).subtract(c.get(0))).scale(n);
        var acceleration=c.get(a+2).subtract(c.get(a+1).scale(2)).add(c.get(a)).scale(n*(n-1));
        var tangent=v.normalize();return acceleration.subtract(tangent.scale(tangent.dot(acceleration))).scale(1/v.lengthSqr());
    }
    public double secondDerivativeBound(double fractionSpan)
    {require(Double.isFinite(fractionSpan)&&fractionSpan>=0&&fractionSpan<=1,"Actual bounded arc span required");double upper=length+lengthError;return curvatureBound*upper*upper*fractionSpan*fractionSpan;}
    public List<Segment> segments(){return segments;}
    public boolean isReverseOf(NervCentrelineCurveR52 other)
    {
        if(other==null||segments.size()!=other.segments.size())return false;
        for(int i=0;i<segments.size();i++){var a=segments.get(i);var b=other.segments.get(segments.size()-1-i);if(a.type!=b.type||a.controls.size()!=b.controls.size())return false;for(int k=0;k<a.controls.size();k++)if(!a.controls.get(k).equals(b.controls.get(b.controls.size()-1-k)))return false;}return true;
    }
    public NervCentrelineCurveR52 reversed()
    {var result=new ArrayList<Segment>();for(int i=segments.size()-1;i>=0;i--){var s=segments.get(i);var controls=new ArrayList<>(s.controls);Collections.reverse(controls);result.add(new Segment(s.type,controls));}return new NervCentrelineCurveR52(result);}
    /** Portable original controls for the same client-side analytic sampler. */
    public JsonObject toJson()
    {
        var object=new JsonObject();var rows=new JsonArray();for(var segment:segments){var row=new JsonObject();row.addProperty("type",segment.type().name());var controls=new JsonArray();for(var p:segment.controls()){var xyz=new JsonArray();xyz.add(p.x);xyz.add(p.y);xyz.add(p.z);controls.add(xyz);}row.add("controls",controls);rows.add(row);}object.add("segments",rows);return object;
    }
    public static NervCentrelineCurveR52 parse(JsonObject object)
    {
        require(object.keySet().equals(Set.of("segments"))&&object.get("segments").isJsonArray(),"Explicit centre_curve segments required");var result=new ArrayList<Segment>();
        for(var raw:object.getAsJsonArray("segments")) {
            require(raw.isJsonObject(),"Explicit curve segment required");var row=raw.getAsJsonObject();
            require(row.has("controls")&&row.get("controls").isJsonArray()&&row.keySet().stream().allMatch(k->Set.of("type","kind","controls").contains(k))&&!(row.has("type")&&row.has("kind")),"Explicit segment type/controls required");
            var controls=new ArrayList<Vec3>();for(var value:row.getAsJsonArray("controls")){require(value.isJsonArray()&&value.getAsJsonArray().size()==3,"World-space XYZ control required");var v=value.getAsJsonArray();for(var x:v)require(x.isJsonPrimitive()&&x.getAsJsonPrimitive().isNumber(),"Numeric Root control required");controls.add(new Vec3(v.get(0).getAsDouble(),v.get(1).getAsDouble(),v.get(2).getAsDouble()));}
            String kind=row.has("type")?row.get("type").getAsString():row.has("kind")?row.get("kind").getAsString():controls.size()==2?"LINE":"QUINTIC_BEZIER";
            result.add(new Segment(Type.valueOf(kind),controls));
        }
        return new NervCentrelineCurveR52(result);
    }
    private static Vec3 unit(Vec3 p){double n=p.length();require(Double.isFinite(n)&&n>0,"Nonzero continuous curve derivative required");return p.scale(1/n);}
    private static void finite(Vec3 p){require(p!=null&&Double.isFinite(p.x)&&Double.isFinite(p.y)&&Double.isFinite(p.z),"Finite actual world-space control required");}
    private static void require(boolean ok,String reason){if(!ok)throw new IllegalArgumentException(reason);}
}

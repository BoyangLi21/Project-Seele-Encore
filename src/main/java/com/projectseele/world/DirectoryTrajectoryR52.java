package com.projectseele.world;

import java.util.*;
import com.google.gson.*;
import net.minecraft.nbt.*;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;

/** A certified curve is the actual Root directory sample, not a callback or
 * the linear interpolation of two coupled EVA root positions. */
public final class DirectoryTrajectoryR52
{
    private final NervRouteDirectoryR52 directory;
    private final NervRouteDirectoryR52.Leg leg;
    private final FootSupportFrameR52.Binding binding;
    private final double from,to,angularTravel,translationCurvature,samplingError;
    public DirectoryTrajectoryR52(NervRouteDirectoryR52 directory,NervRouteDirectoryR52.Leg leg,FootSupportFrameR52.Binding binding,double from,double to)
    {
        this.directory=Objects.requireNonNull(directory);this.leg=Objects.requireNonNull(leg);this.binding=Objects.requireNonNull(binding);
        if(!directory.installed()||!leg.equals(directory.leg(leg.id()))||!Double.isFinite(from)||!Double.isFinite(to)||from<0||to>1||to<from)
            throw new IllegalArgumentException("Actual installed leg and monotone fractions required");
        this.from=from;this.to=to;
        angularTravel=(angle(directory.node(leg.from()).footFrame().rotation(),directory.node(leg.to()).footFrame().rotation())
                +angle(leg.evaFrom().quaternion(),leg.evaTo().quaternion()))*(to-from);
        translationCurvature=directory.translationSecondDerivativeBound(leg,from,to);
        samplingError=directory.translationSamplingError(leg);
        sample(0);sample(1);
    }
    /** Actual-source portable windows for the accepted client/server frame.
     * Only fixed-orientation paths are admitted; no Hermite/chord substitute. */
    public static CompoundTag encodePortableR52(List<DirectoryTrajectoryR52> paths)
    {
        if(paths.isEmpty())throw new IllegalArgumentException("Actual source window required");var tag=new CompoundTag();tag.putString("Type","r52-centre-window-v1");var rows=new ListTag();RigidTransform previous=null;
        for(var path:paths){if(!path.pureTranslation())throw new IllegalArgumentException("Portable window requires a fixed original root orientation");var start=path.sample(0).evaRoot();var end=path.sample(1).evaRoot();if(previous!=null&&(previous.translation().distanceToSqr(start.translation())>1e-10||previous.rotationErrorDegrees(start)>.0001))throw new IllegalArgumentException("Disconnected actual source window");previous=end;
            var row=new CompoundTag();var leg=path.leg();row.putString("Directory",path.directory().fingerprint());row.putString("Leg",leg.id());row.putDouble("From",path.fromFraction());row.putDouble("To",path.toFraction());row.putDouble("FromMetres",path.directory().legDistance(leg,path.fromFraction()));row.putDouble("ToMetres",path.directory().legDistance(leg,path.toFraction()));row.putDouble("LegLength",path.directory().legLength(leg));var directions=path.directory().routes().values().stream().filter(r->r.legs().contains(leg.id())).map(NervRouteDirectoryR52.Route::recovery).distinct().toList();if(directions.size()!=1)throw new IllegalArgumentException("Actual canonical route direction required for portable guide tangent");row.putBoolean("CanonicalReverse",directions.get(0));
            point(row,"Start",path.directory().node(leg.from()).footFrame().translation());point(row,"End",path.directory().node(leg.to()).footFrame().translation());point(row,"RootOffset",start.translation().subtract(path.directory().centrePoint(leg,path.fromFraction())));
            row.putFloat("Qx",start.qx());row.putFloat("Qy",start.qy());row.putFloat("Qz",start.qz());row.putFloat("Qw",start.qw());
            if(leg.centreCurve()!=null)row.putString("Curve",leg.centreCurve().toJson().toString());else if(leg.rampProfile()!=null){var r=leg.rampProfile();var ramp=new CompoundTag();ramp.putDouble("FlatBefore",r.flatBefore());ramp.putDouble("SlopeRun",r.slopeRun());ramp.putDouble("Blend",r.blend());row.put("Ramp",ramp);}rows.add(row);
        }
        tag.put("Parts",rows);return tag;
    }
    private static void point(CompoundTag tag,String key,Vec3 value){tag.putDouble(key+"X",value.x);tag.putDouble(key+"Y",value.y);tag.putDouble(key+"Z",value.z);}
    private static Vec3 point(CompoundTag tag,String key){var value=new Vec3(tag.getDouble(key+"X"),tag.getDouble(key+"Y"),tag.getDouble(key+"Z"));if(!Double.isFinite(value.lengthSqr()))throw new IllegalArgumentException("Finite original window point required");return value;}
    private record RampKey(Vec3 start,Vec3 end,NervRampProfileR52 profile){}
    private static final Map<String,NervCentrelineCurveR52> PORTABLE_CURVES=new LinkedHashMap<>();
    private static final Map<RampKey,NervRouteDirectoryR52.RampArc> PORTABLE_RAMPS=new LinkedHashMap<>();
    private static synchronized NervCentrelineCurveR52 portableCurve(String source){var curve=PORTABLE_CURVES.get(source);if(curve==null){curve=NervCentrelineCurveR52.parse(JsonParser.parseString(source).getAsJsonObject());if(PORTABLE_CURVES.size()>=64)PORTABLE_CURVES.remove(PORTABLE_CURVES.keySet().iterator().next());PORTABLE_CURVES.put(source,curve);}return curve;}
    private static synchronized NervRouteDirectoryR52.RampArc portableRamp(Vec3 start,Vec3 end,NervRampProfileR52 profile){var key=new RampKey(start,end,profile);var arc=PORTABLE_RAMPS.get(key);if(arc==null){arc=new NervRouteDirectoryR52.RampArc(start,end,profile);if(PORTABLE_RAMPS.size()>=64)PORTABLE_RAMPS.remove(PORTABLE_RAMPS.keySet().iterator().next());PORTABLE_RAMPS.put(key,arc);}return arc;}

    private record PortablePart(Vec3 start,Vec3 end,Vec3 offset,Quaternionf rotation,NervCentrelineCurveR52 curve,NervRampProfileR52 ramp,NervRouteDirectoryR52.RampArc arc,double fromMetres,double toMetres,double fromFraction,double toFraction,double length,boolean canonicalReverse)
    {
        RigidTransform sample(double distance){double metres=Math.max(fromMetres,Math.min(toMetres,fromMetres+distance));double fraction=distance==0?fromFraction:distance==toMetres-fromMetres?toFraction:metres==0?0:metres==length?1:arc!=null?arc.fraction(metres):metres/length;Vec3 centre;
            if(curve!=null)centre=curve.point(fraction);else{centre=start.lerp(end,(float)fraction);if(ramp!=null)centre=new Vec3(centre.x,start.y+(end.y-start.y)*ramp.heightFraction(end.subtract(start).horizontalDistance(),fraction),centre.z);}return RigidTransform.of(centre.add(offset),rotation);}
        Vec3 tangent(double distance){double metres=Math.max(fromMetres,Math.min(toMetres,fromMetres+distance));double f=distance==0?fromFraction:distance==toMetres-fromMetres?toFraction:metres==0?0:metres==length?1:arc!=null?arc.fraction(metres):metres/length;Vec3 tangent;
            if(curve!=null)tangent=curve.tangent(f);else{var delta=end.subtract(start);double dy=delta.y;if(ramp!=null){double h=delta.horizontalDistance(),d=h*f-ramp.flatBefore(),s=0;if(d>0&&d<ramp.slopeRun())s=d<ramp.blend()?(1-Math.cos(Math.PI*d/ramp.blend()))*.5:d>ramp.slopeRun()-ramp.blend()?(1-Math.cos(Math.PI*(ramp.slopeRun()-d)/ramp.blend()))*.5:1;dy*=h*s/(ramp.slopeRun()-ramp.blend());}var v=new Vec3(delta.x,dy,delta.z);if(v.lengthSqr()==0)throw new IllegalArgumentException("Actual guide tangent required");tangent=v.scale(1/v.length());}return canonicalReverse?tangent.scale(-1):tangent;}
    }
    public static final class PortableWindowR52
    {
        private final List<PortablePart> parts;private final double length;
        private PortableWindowR52(List<PortablePart> parts){this.parts=List.copyOf(parts);double total=0;for(var p:parts)total+=p.toMetres-p.fromMetres;length=total;}
        public double length(){return length;}
        public double lengthMetres(){return length;}
        public RigidTransform sample(double localMetres){if(!Double.isFinite(localMetres)||localMetres<0||localMetres>length)throw new IllegalArgumentException("Distance outside accepted source window");double before=0;for(int i=0;i<parts.size();i++){var part=parts.get(i);double span=part.toMetres-part.fromMetres;if(localMetres<before+span||i==parts.size()-1)return part.sample(Math.max(0,Math.min(span,localMetres-before)));before+=span;}throw new IllegalStateException("Empty source window");}
        public Vec3 tangent(double localMetres){if(!Double.isFinite(localMetres)||localMetres<0||localMetres>length)throw new IllegalArgumentException("Distance outside accepted source window");double before=0;for(int i=0;i<parts.size();i++){var p=parts.get(i);double span=p.toMetres-p.fromMetres;if(localMetres<before+span||i==parts.size()-1)return p.tangent(Math.max(0,Math.min(span,localMetres-before)));before+=span;}throw new IllegalStateException("Empty source window");}
    }
    /** Decode once per accepted packet/control fingerprint, then sample the
     * immutable window at the shared monotone entity-clock distance. */
    public static PortableWindowR52 decodePortableR52(CompoundTag tag)
    {
        if(!tag.getString("Type").equals("r52-centre-window-v1"))throw new IllegalArgumentException("Actual source window type required");var parts=new ArrayList<PortablePart>();var rows=tag.getList("Parts",Tag.TAG_COMPOUND);RigidTransform previous=null;
        for(int i=0;i<rows.size();i++){var row=rows.getCompound(i);var start=point(row,"Start");var end=point(row,"End");var offset=point(row,"RootOffset");var q=new Quaternionf(row.getFloat("Qx"),row.getFloat("Qy"),row.getFloat("Qz"),row.getFloat("Qw"));double qn=q.lengthSquared();if(!Double.isFinite(qn)||Math.abs(qn-1)>1e-5)throw new IllegalArgumentException("Fixed original window rotation required");
            NervCentrelineCurveR52 curve=row.contains("Curve")?portableCurve(row.getString("Curve")):null;NervRampProfileR52 ramp=null;if(row.contains("Ramp")){var r=row.getCompound("Ramp");ramp=new NervRampProfileR52(r.getDouble("FlatBefore"),r.getDouble("SlopeRun"),r.getDouble("Blend"));}if(curve!=null&&ramp!=null)throw new IllegalArgumentException("Portable source geometry conflicts");var arc=ramp==null?null:portableRamp(start,end,ramp);
            double length=curve!=null?curve.length():arc!=null?arc.cumulative[arc.count]:start.distanceTo(end);if(!Double.isFinite(length)||length<=0||length!=row.getDouble("LegLength"))throw new IllegalArgumentException("Portable source length changed");double from=row.getDouble("FromMetres"),to=row.getDouble("ToMetres");if(!Double.isFinite(from)||!Double.isFinite(to)||from<0||to<from||to>length)throw new IllegalArgumentException("Portable source interval invalid");
            double fromFraction=row.getDouble("From"),toFraction=row.getDouble("To");if(!Double.isFinite(fromFraction)||!Double.isFinite(toFraction)||fromFraction<0||toFraction>1||toFraction<fromFraction)throw new IllegalArgumentException("Portable source fractions invalid");var part=new PortablePart(start,end,offset,q,curve,ramp,arc,from,to,fromFraction,toFraction,length,row.getBoolean("CanonicalReverse"));var a=part.sample(0);if(previous!=null&&(previous.translation().distanceToSqr(a.translation())>1e-10||previous.rotationErrorDegrees(a)>.0001))throw new IllegalArgumentException("Portable window endpoints differ");previous=part.sample(to-from);parts.add(part);
        }
        if(parts.isEmpty())throw new IllegalArgumentException("Nonempty actual portable window required");return new PortableWindowR52(parts);
    }
    public static RigidTransform samplePortableR52(CompoundTag tag,double localMetres){return decodePortableR52(tag).sample(localMetres);}
    private static double angle(Quaternionf a,Quaternionf b)
    {if(a.x==b.x&&a.y==b.y&&a.z==b.z&&a.w==b.w||a.x==-b.x&&a.y==-b.y&&a.z==-b.z&&a.w==-b.w)return 0;double aa=(double)a.x*a.x+(double)a.y*a.y+(double)a.z*a.z+(double)a.w*a.w,bb=(double)b.x*b.x+(double)b.y*b.y+(double)b.z*b.z+(double)b.w*b.w;double dot=Math.abs((double)a.x*b.x+(double)a.y*b.y+(double)a.z*b.z+(double)a.w*b.w)/Math.sqrt(aa*bb);return 2*Math.acos(Math.min(1,dot));}
    public FootSupportFrameR52.Sample sample(double time)
    {if(!Double.isFinite(time)||time<0||time>1)throw new IllegalArgumentException("Curve time outside [0,1]");return directory.sample(leg,directory.intervalFraction(leg,from,to,time),binding);}
    public NervRouteDirectoryR52 directory(){return directory;}
    public NervRouteDirectoryR52.Leg leg(){return leg;}
    public FootSupportFrameR52.Binding binding(){return binding;}
    public double fromFraction(){return from;}
    public double toFraction(){return to;}
    public double angularTravel(){return angularTravel;}
    public Vec3 footCentreLocal(){return binding.contactCentre();}
    public boolean pureTranslation(){return angularTravel==0;}
    public double translationSecondDerivativeBound(){return translationCurvature;}
    public double samplingErrorBound(){return samplingError;}
    /** R(t)=A(t)B(t), hence |R''p| <= |p|*(omegaA+omegaB)^2.
     * Original rounded ramp translation has its explicit second-derivative
     * bound as well. Float interpolation/normalization
     * contributes an explicit positive query bound, never a collision waiver. */
    public double roundoffBound(double radius)
    {
        if(angularTravel==0)return samplingError;
        double u=Math.scalb(1D,-24),gamma=128*u/(1-128*u);
        double travel=directory.node(leg.from()).footFrame().translation().distanceTo(directory.node(leg.to()).footFrame().translation())*(to-from);
        return samplingError+gamma*(4*radius+travel)+Math.ulp(radius)*16;
    }
    public int divisions(double radius,double maximumError)
    {
        if(!Double.isFinite(radius)||radius<0||!Double.isFinite(maximumError)||maximumError<=0)throw new IllegalArgumentException("Finite measured radius and positive error budget required");
        double available=maximumError-roundoffBound(radius);if(available<=0)throw new IllegalArgumentException("Error budget below certified float interpolation bound");
        double n=Math.max(1,Math.ceil(Math.sqrt((radius*angularTravel*angularTravel+translationCurvature)/(8*available))));if(n>4096)throw new IllegalArgumentException("Curve requires more bounded subdivisions than admitted");return (int)n;
    }
    public double error(double radius,int divisions)
    {if(divisions<1)throw new IllegalArgumentException("Positive curve subdivision required");return (radius*angularTravel*angularTravel+translationCurvature)/(8D*divisions*divisions)+roundoffBound(radius);}
}

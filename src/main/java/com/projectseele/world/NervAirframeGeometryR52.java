package com.projectseele.world;

import com.google.gson.*;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;
import com.projectseele.world.NervAirTransportManifestR52.*;

/** The actual R16 body/rotors and R31 cradle vertices used by both proof and draw. */
public final class NervAirframeGeometryR52
{
    static final double CRADLE_RADIAL_ENCLOSURE_R53=1.7;
    private static final int[][] ROTORS={{-29,-11},{29,-11},{-49,9},{49,9}};
    public record Part(String name,double[] vertices)
    {public Part{vertices=vertices.clone();if(vertices.length==0||vertices.length%18!=0)throw new IllegalArgumentException("Actual stride6 triangle part required");}@Override public double[] vertices(){return vertices.clone();}public double[] xyz(){var a=new double[vertices.length/2];for(int i=0;i<vertices.length/6;i++)System.arraycopy(vertices,i*6,a,i*3,3);return a;}}
    private final Map<String,Part> source;
    private final Map<String,NervRigidMeshSweepR52> rigidSources;
    private final String fingerprint;
    private volatile List<AABB> cachedBearingPatches;
    private NervAirframeGeometryR52(Map<String,Part> parts,String sha){source=Map.copyOf(parts);var meshes=new HashMap<String,NervRigidMeshSweepR52>();for(String name:List.of("un_transport_body","un_transport_rotor_0","un_transport_rotor_1","un_transport_rotor_2","un_transport_rotor_3"))meshes.put(name,new NervRigidMeshSweepR52(parts.get(name).xyz()));rigidSources=Map.copyOf(meshes);fingerprint=sha;}
    public String fingerprint(){return fingerprint;}
    public static NervAirframeGeometryR52 load(EvaOriginalMeshGeometryR52.ByteSource bytes,Map<String,String> expected)throws IOException
    {
        var parts=new LinkedHashMap<String,Part>();var receipts=new TreeMap<String,String>();
        for(String path:List.of("mesh/tv_facilities_r16.json","mesh/air_cradle_r31.json"))
        {
            byte[] b=bytes.read(path);String hash=sha(b);if(!hash.equals(expected.get(path)))throw new IllegalStateException("Actual aircraft rendered source changed: "+path);receipts.put(path,hash);
            var root=JsonParser.parseString(new String(b,StandardCharsets.UTF_8)).getAsJsonObject();
            for(var e:root.getAsJsonObject("parts").entrySet())if(e.getKey().equals("un_ground_carrier")||e.getKey().equals("un_transport_body")||e.getKey().startsWith("un_transport_rotor_")||e.getKey().startsWith("air_cradle_"))
            {var row=e.getValue().getAsJsonArray();var v=new double[row.size()];for(int i=0;i<v.length;i++){v[i]=row.get(i).getAsFloat();if(!Double.isFinite(v[i]))throw new IllegalStateException("Nonfinite original aircraft triangle");}if(parts.putIfAbsent(e.getKey(),new Part(e.getKey(),v))!=null)throw new IllegalStateException("Duplicate actual aircraft part");}
        }
        if(!parts.keySet().containsAll(Set.of("un_transport_body","un_transport_rotor_0","un_transport_rotor_1","un_transport_rotor_2","un_transport_rotor_3","air_cradle_frame_r31","air_cradle_jaw_r31_-1","air_cradle_jaw_r31_1")))throw new IllegalStateException("Complete original body/fourrotors/cradle source required");
        return new NervAirframeGeometryR52(parts,sha(receipts.toString().getBytes(StandardCharsets.UTF_8)));
    }
    public static NervAirframeGeometryR52 loadClasspath(Map<String,String> expected)throws IOException{return load(EvaOriginalMeshGeometryR52::classpathBytes,expected);}
    public Part originalGroundCarrier(){return source.get("un_ground_carrier");}
    public Part originalBody(){return source.get("un_transport_body");}
    public Part originalRotor(int i){return source.get("un_transport_rotor_"+i);}
    public NervRigidMeshSweepR52 bodyMesh(){return rigidSources.get("un_transport_body");}
    public NervRigidMeshSweepR52 rotorMesh(int i){return rigidSources.get("un_transport_rotor_"+i);}
    public RigidTransform rotorLocalFrame(int i,double clock){return RigidTransform.of(new Vec3(ROTORS[i][0],4.8,ROTORS[i][1]),new Quaternionf().rotationY((float)Math.toRadians(clock*47*(i%2==0?1:-1))));}
    public List<AABB> bearingPatches()
    {
        var cached=cachedBearingPatches;if(cached!=null)return cached;
        var patches=new LinkedHashSet<AABB>();var xyz=source.get("un_transport_body").xyz();double bottom=rigidSources.get("un_transport_body").bounds().minY;for(int i=0;i<xyz.length;i+=9){var a=new Vec3(xyz[i],xyz[i+1],xyz[i+2]);var b=new Vec3(xyz[i+3],xyz[i+4],xyz[i+5]);var c=new Vec3(xyz[i+6],xyz[i+7],xyz[i+8]);if(a.y==bottom&&b.y==bottom&&c.y==bottom&&b.subtract(a).cross(c.subtract(a)).lengthSqr()>1e-12)patches.add(new AABB(a,a).minmax(new AABB(b,b)).minmax(new AABB(c,c)));}if(patches.isEmpty())throw new IllegalStateException("Actual original gear bearing surface absent");return cachedBearingPatches=List.copyOf(patches);
    }
    /** Original rotor clock, with its continuous 47 degree/tick phase. */
    public List<Part> parts(Frame frame,List<Vec3> cargoAnchors,double rotorClock)
    {return parts(frame,cargoAnchors,List.of(),rotorClock,false);}
    public List<Part> parts(Frame frame,List<Vec3> cargoAnchors,List<Vec3> jawAxes,double rotorClock){return parts(frame,cargoAnchors,jawAxes,rotorClock,false);}
    private List<Part> parts(Frame frame,List<Vec3> cargoAnchors,List<Vec3> jawAxes,double rotorClock,boolean includeStowed)
    {
        var result=new ArrayList<Part>();result.add(source.get("un_transport_body"));
        for(int i=0;i<4;i++)
        {double angle=Math.toRadians(rotorClock*47*(i%2==0?1:-1));var root=RigidTransform.of(new Vec3(ROTORS[i][0],4.8,ROTORS[i][1]),new Quaternionf().rotationY((float)angle));result.add(transform(source.get("un_transport_rotor_"+i),root));}
        result.addAll(cradleParts(frame,cargoAnchors,jawAxes,includeStowed));
        return List.copyOf(result);
    }
    public List<Part> cradleParts(Frame frame,List<Vec3> cargoAnchors,List<Vec3> jawAxes,boolean includeStowed)
    {
        var result=new ArrayList<Part>();
        if(frame.rig().deployment()==0&&!includeStowed)return List.copyOf(result);
        if(frame.rig().deployment()>0&&(frame.cargo()==null||cargoAnchors.size()!=6))throw new IllegalStateException("Actual six frozen body anchors required for deployed cradle");
        var cargoInPlane=frame.cargo()==null?RigidTransform.identity():frame.plane().inverse().compose(frame.cargo());var anchors=new ArrayList<Vec3>();
        for(int i=0;i<6;i++)
        {
            Vec3 rest=new Vec3(i%2==0?14:-14,-13,(i/2-1)*11);Vec3 end=cargoAnchors.size()==6?cargoInPlane.transformPoint(cargoAnchors.get(i)):rest;anchors.add(rest.lerp(end,frame.rig().deployment()));
        }
        // These are the original adaptive cradle's 12-sided rods, collars,
        // crossbeams and longitudinal spines, with the exact renderer radii.
        for(int pair=0;pair<3;pair++)
        {
            Vec3 left=anchors.get(pair*2),right=anchors.get(pair*2+1),axis=right.subtract(left).normalize();Vec3 spread=axis.scale(4*frame.rig().jaws());
            result.add(rod("cross/"+pair,left.subtract(spread),right.add(spread),.48,66));
            for(int side=0;side<2;side++)
            {
                Vec3 end=side==0?left.subtract(spread):right.add(spread),top=new Vec3(side==0?14:-14,-11,(pair-1)*11),mid=top.lerp(end,.62);
                if(end.distanceTo(top)>144.002)throw new IllegalStateException("Actual original telescopic cradle stroke exceeded");
                result.add(rod("strut/"+pair+"/"+side,top,mid,.48,65));result.add(rod("piston/"+pair+"/"+side,mid,end,.24,182));result.add(rod("collar/"+pair+"/"+side,mid,mid.lerp(end,.07),.60,48));
                if(jawAxes.size()==6&&cargoAnchors.size()==6&&frame.cargo()!=null){int index=pair*2+side;var centre=cargoAnchors.get(index);var localAxis=jawAxes.get(index);var jaw=transform(rod("jaw/"+pair+"/"+side,centre.subtract(localAxis.scale(1.6)),centre.add(localAxis.scale(1.6)),.85,86),cargoInPlane);result.add(transform(jaw,new RigidTransform(end.subtract(cargoInPlane.transformPoint(centre)),0,0,0,1)));}else result.add(rod("jaw/"+pair+"/"+side,end.subtract(axis.scale(1.6)),end.add(axis.scale(1.6)),.85,86));
                if(pair>0)result.add(rod("spine/"+pair+"/"+side,anchors.get((pair-1)*2+side),end,.35,58));
            }
        }
        return List.copyOf(result);
    }
    private static Part transform(Part part,RigidTransform f)
    {double[] v=part.vertices();for(int i=0;i<v.length;i+=6){var p=f.transformPoint(new Vec3(v[i],v[i+1],v[i+2]));v[i]=p.x;v[i+1]=p.y;v[i+2]=p.z;}return new Part(part.name(),v);}
    private static Part rod(String name,Vec3 a,Vec3 b,double radius,int colour)
    {
        var axis=b.subtract(a);if(axis.lengthSqr()<1e-12)throw new IllegalStateException("Collapsed actual cradle rod");axis=axis.normalize();var x=axis.cross(Math.abs(axis.y)<.95?new Vec3(0,1,0):new Vec3(1,0,0)).normalize();var y=axis.cross(x).normalize();var v=new double[12*2*18];int at=0;
        for(int i=0;i<12;i++){double u=i*Math.PI/6,w=(i+1)*Math.PI/6;var p=x.scale(Math.cos(u)).add(y.scale(Math.sin(u))).scale(radius);var q=x.scale(Math.cos(w)).add(y.scale(Math.sin(w))).scale(radius);Vec3[] points={a.add(p),a.add(q),b.add(q),b.add(p)};for(int k:new int[]{0,1,2,0,2,3}){var z=points[k];v[at++]=z.x;v[at++]=z.y;v[at++]=z.z;v[at++]=colour;v[at++]=Math.min(255,colour+10);v[at++]=Math.min(255,colour+14);}}
        return new Part(name,v);
    }
    /** With both roots fixed, only normalized paired-anchor spread bends
     * a cradle centreline. A rod retains twice its actual radius for any
     * cross-section basis switch; a source-axis jaw keeps its orientation. */
    static double cradleChordEnclosureR53(Frame from,Frame to,List<Vec3> anchors,List<Vec3> axes,String part)
    {
        if(anchors.size()!=6||axes.size()!=6||from.cargo()==null||to.cargo()==null
                ||!from.plane().equals(to.plane())||!from.cargo().equals(to.cargo()))return CRADLE_RADIAL_ENCLOSURE_R53;
        var name=part.split("/");if(name.length<2)return CRADLE_RADIAL_ENCLOSURE_R53;
        double radial=switch(name[0]){case "jaw"->0;case "cross","strut"->2*.48;case "piston"->2*.24;case "collar"->2*.60;case "spine"->2*.35;default->Double.NaN;};
        if(!Double.isFinite(radial))return CRADLE_RADIAL_ENCLOSURE_R53;
        int pair=Integer.parseInt(name[1]);var relative=from.plane().inverse().compose(from.cargo());
        var leftRest=new Vec3(14,-13,(pair-1)*11);var rightRest=new Vec3(-14,-13,(pair-1)*11);
        var left=relative.transformPoint(anchors.get(pair*2));var right=relative.transformPoint(anchors.get(pair*2+1));
        var a=rightRest.lerp(right,from.rig().deployment()).subtract(leftRest.lerp(left,from.rig().deployment()));
        var b=rightRest.lerp(right,to.rig().deployment()).subtract(leftRest.lerp(left,to.rig().deployment()));
        var delta=b.subtract(a);double squared=delta.lengthSqr();
        double nearest=squared==0?0:Math.max(0,Math.min(1,-a.dot(delta)/squared));
        double minimum=a.add(delta.scale(nearest)).length();
        if(!Double.isFinite(minimum+squared)||minimum<1e-6)return CRADLE_RADIAL_ENCLOSURE_R53;
        double ratio=Math.sqrt(squared)/minimum,j=Math.max(Math.abs(from.rig().jaws()),Math.abs(to.rig().jaws()));
        double change=Math.abs(to.rig().jaws()-from.rig().jaws());
        // For u=v/|v|, |u'| <= |delta|/minimum and
        // |u''| <= 3|delta|^2/minimum^2. The chord error of
        // 4*j*u is at most sup |(4*j*u)''| / 8.
        double bound=change*ratio+1.5*j*ratio*ratio;
        return Double.isFinite(bound)?bound+radial:CRADLE_RADIAL_ENCLOSURE_R53;
    }
    /** Whole-box queries are only broad phase. Each static part and all four
     * continuously spinning rotors are certified triangle chord sweeps. */
    public Sweep sweep(Frame from,Frame to,List<Vec3> anchors,double clockFrom,double clockTo,double maximumError)
    {return new Sweep(this,from,to,List.copyOf(anchors),List.of(),clockFrom,clockTo,maximumError);}
    public Sweep sweep(Frame from,Frame to,List<Vec3> anchors,List<Vec3> jawAxes,double clockFrom,double clockTo,double maximumError){return new Sweep(this,from,to,List.copyOf(anchors),List.copyOf(jawAxes),clockFrom,clockTo,maximumError);}
    Sweep excludingCradlePartsR53(Frame from,Frame to,List<Vec3> anchors,List<Vec3> axes,Set<String> excluded,double rotorClock)
    {return new Sweep(this,from,to,List.copyOf(anchors),List.copyOf(axes),rotorClock,rotorClock+1,.005,Set.copyOf(excluded));}
    public static final class Sweep
    {
        private record RigidPiece(NervRigidMeshSweepR52 mesh,RigidTransform from,RigidTransform to,double bend,AABB envelope,double start,double end){}
        private record Morph(double[] a,double[] b,RigidTransform from,RigidTransform to,double error,AABB envelope,double start,double end){}
        private final NervAirframeGeometryR52 source;private final List<RigidPiece> rigid;private final List<Morph> morph;private final List<AABB> envelopes;private final int aircraftRigidCount;
        private Sweep(NervAirframeGeometryR52 source,Frame from,Frame to,List<Vec3> anchors,List<Vec3> jawAxes,double start,double end,double maximumError)
        {this(source,from,to,anchors,jawAxes,start,end,maximumError,Set.of());}
        private Sweep(NervAirframeGeometryR52 source,Frame from,Frame to,List<Vec3> anchors,List<Vec3> jawAxes,double start,double end,double maximumError,Set<String> excluded)
        {
            this.source=source;
            if(!Double.isFinite(start+end+maximumError)||end<start||maximumError<=0)throw new IllegalArgumentException("Exact native aircraft clock required");
            var pieces=new ArrayList<RigidPiece>();var moving=new ArrayList<Morph>();var boxes=new ArrayList<AABB>();
            var body=source.rigidSources.get("un_transport_body");add(pieces,boxes,body,from.plane(),to.plane(),0);
            double planeAngle=NervRigidMeshSweepR52.angular(from.plane(),to.plane());int spinParts=Math.max(1,(int)Math.ceil(((end-start)*47+Math.toDegrees(planeAngle))/80));if(spinParts>4096)throw new IllegalArgumentException("Rotor clock subdivision budget exceeded");
            for(int rotor=0;rotor<4;rotor++)
            {
                var mesh=source.rigidSources.get("un_transport_rotor_"+rotor);var at=new Vec3(ROTORS[rotor][0],4.8,ROTORS[rotor][1]);
                for(int s=0;s<spinParts;s++)
                {
                    double a=(double)s/spinParts,b=(double)(s+1)/spinParts;var fa=from.plane().interpolate(to.plane(),a);var fb=from.plane().interpolate(to.plane(),b);
                    var ra=RigidTransform.of(at,new Quaternionf().rotationY((float)Math.toRadians((start+(end-start)*a)*47*(rotor%2==0?1:-1))));
                    var rb=RigidTransform.of(at,new Quaternionf().rotationY((float)Math.toRadians((start+(end-start)*b)*47*(rotor%2==0?1:-1))));
                    // Both rotations are yaw, so their angular composition is
                    // exact. Only the rotating rotor centre has a curved chord.
                    double bend=at.length()*planeAngle*planeAngle/(8D*spinParts*spinParts)+at.length()*8e-6;add(pieces,boxes,mesh,fa.compose(ra),fb.compose(rb),bend,a,b);
                }
            }
            aircraftRigidCount=pieces.size();boolean includeStowed=from.rig().deployment()>0||to.rig().deployment()>0;double cargoAngle=from.cargo()==null||to.cargo()==null?0:NervRigidMeshSweepR52.angular(from.cargo(),to.cargo()),travel=from.plane().translation().distanceTo(to.plane().translation())+(from.cargo()==null||to.cargo()==null?0:from.cargo().translation().distanceTo(to.cargo().translation()));double coefficient=180*(planeAngle+cargoAngle)*(planeAngle+cargoAngle)/8+Math.abs(from.rig().deployment()-to.rig().deployment())*travel/4;int morphParts=Math.max(1,(int)Math.ceil(Math.sqrt(coefficient/.003)));
            // Long fixed-root deployment checks use the same bounded source
            // spans as the actuator; a whole-stroke curvature maximum need
            // not become an obstacle around every intermediate triangle.
            if(anchors.size()==6&&jawAxes.size()==6&&from.cargo()!=null&&from.plane().equals(to.plane())&&from.cargo().equals(to.cargo()))
                morphParts=Math.max(morphParts,(int)Math.ceil(Math.max(Math.abs(from.rig().deployment()-to.rig().deployment()),Math.abs(from.rig().jaws()-to.rig().jaws()))/.050001));
            if(morphParts>4096)throw new IllegalStateException("Actual cradle curve subdivision budget exceeded");
            // A locked cradle translating with both roots is rigid. Subtracting
            // large world coordinates can change the last bits of its local
            // vertices; that is not a deformation needing radial inflation.
            boolean translatedCradle=from.rig().equals(to.rig())&&from.cargo()!=null&&to.cargo()!=null
                    &&from.plane().rotationErrorDegrees(to.plane())<1e-6
                    &&from.cargo().rotationErrorDegrees(to.cargo())<1e-6
                    &&to.plane().translation().subtract(from.plane().translation()).distanceToSqr(
                            to.cargo().translation().subtract(from.cargo().translation()))<1e-18;
            for(int segment=0;segment<morphParts;segment++)
            {
                // Body and rotor sweeps already use the cached rigid meshes
                // above. Only the adaptive cradle needs per-segment vertices.
                double sa=(double)segment/morphParts,sb=(double)(segment+1)/morphParts;var fa=geometryFrame(from,to,sa);var fb=geometryFrame(from,to,sb);var pa=source.cradleParts(fa,anchors,jawAxes,includeStowed);var pb=source.cradleParts(fb,anchors,jawAxes,includeStowed);for(int p=0;p<pa.size();p++){
                if(excluded.contains(pa.get(p).name()))continue;double[] va=pa.get(p).xyz(),vb=pb.get(p).xyz();boolean equal=Arrays.equals(va,vb);
                if(equal||translatedCradle){add(pieces,boxes,new NervRigidMeshSweepR52(va),fa.plane(),fb.plane(),0,sa,sb);continue;}
                String[] partName=pa.get(p).name().split("/");
                double rodRadius=switch(partName[0]){case "cross","strut"->.48;case "piston"->.24;case "collar"->.60;case "spine"->.35;default->0;};
                boolean centreline=rodRadius>0&&anchors.size()==6&&jawAxes.size()==6&&fa.cargo()!=null
                        &&fa.plane().equals(fb.plane())&&fa.cargo().equals(fb.cargo());
                if(centreline)
                {
                    // A moving rod is contained by its swept centreline plus
                    // its radius, including any change of cross-section basis.
                    // Do not inflate the already radial surface a second time.
                    var ends=new double[][]{va,vb};
                    for(int side=0;side<2;side++)
                    {
                        double[] vertices=ends[side],line=new double[9];double count=vertices.length/6D;
                        for(int face=0;face<vertices.length;face+=18)for(int axis=0;axis<3;axis++)
                        {
                            line[axis]+=(vertices[face+axis]+vertices[face+3+axis]+vertices[face+9+axis])/count;
                            line[6+axis]+=(vertices[face+6+axis]+vertices[face+12+axis]+vertices[face+15+axis])/count;
                        }
                        System.arraycopy(line,0,line,3,3);ends[side]=line;
                    }
                    va=ends[0];vb=ends[1];
                }
                double angle=NervRigidMeshSweepR52.angular(fa.plane(),fb.plane())+(fa.cargo()==null||fb.cargo()==null?0:NervRigidMeshSweepR52.angular(fa.cargo(),fb.cargo()));double segmentTravel=fa.plane().translation().distanceTo(fb.plane().translation())+(fa.cargo()==null||fb.cargo()==null?0:fa.cargo().translation().distanceTo(fb.cargo().translation()));
                // Actual moving rod endpoints are affine blends of the plane
                // and frozen-body anchors. Curvature/product terms bound their
                // centre lines; a local radial enclosure covers the exact
                // 12-sided cross-section including its basis switch.
                double enclosure=centreline?cradleChordEnclosureR53(fa,fb,anchors,jawAxes,"jaw/"+partName[1])+rodRadius:cradleChordEnclosureR53(fa,fb,anchors,jawAxes,pa.get(p).name());
                double error=enclosure+180*angle*angle/8+Math.abs(fa.rig().deployment()-fb.rig().deployment())*segmentTravel/4+180*8e-6;
                AABB box=null;for(int i=0;i<va.length;i+=3){var v=fa.plane().transformPoint(new Vec3(va[i],va[i+1],va[i+2]));var w=fb.plane().transformPoint(new Vec3(vb[i],vb[i+1],vb[i+2]));var z=new AABB(v,v).minmax(new AABB(w,w));box=box==null?z:box.minmax(z);}box=box.inflate(error);moving.add(new Morph(va,vb,fa.plane(),fb.plane(),error,box,sa,sb));boxes.add(box);
            }}
            rigid=List.copyOf(pieces);morph=List.copyOf(moving);envelopes=List.copyOf(boxes);
        }
        private static void add(List<RigidPiece> pieces,List<AABB> boxes,NervRigidMeshSweepR52 mesh,RigidTransform a,RigidTransform b,double bend)
        {add(pieces,boxes,mesh,a,b,bend,0,1);}
        private static void add(List<RigidPiece> pieces,List<AABB> boxes,NervRigidMeshSweepR52 mesh,RigidTransform a,RigidTransform b,double bend,double start,double end)
        {
            var box=mesh.envelope(a,b).inflate(bend,0,bend);pieces.add(new RigidPiece(mesh,a,b,bend,box,start,end));
            // Scripted movement only needs each part's enclosing occupied
            // volume; expanding every mesh leaf repeats thousands of chunk
            // and reservation queries without doing triangle collisions.
            if(NervR50CarrierModeR53.enabled())boxes.add(box.inflate(1e-6));
            else for(var leaf:mesh.leafEnvelopes(a,b))boxes.add(leaf.inflate(Math.max(bend,1e-6),1e-6,Math.max(bend,1e-6)));
        }
        private static Frame geometryFrame(Frame a,Frame b,double t)
        {var cargo=a.cargo()==null?b.cargo():b.cargo()==null?a.cargo():a.cargo().interpolate(b.cargo(),t);return new Frame(a.plane().interpolate(b.plane(),t),cargo,a.rig().interpolate(b.rig(),t));}
        public List<AABB> envelopes(){return envelopes;}
        public NervAirframeGeometryR52 source(){return source;}
        public boolean intersects(NervRigidMeshSweepR52 other,RigidTransform frame)
        {return intersects(other,frame,frame);}
        public boolean intersects(NervRigidMeshSweepR52 other,RigidTransform otherFrom,RigidTransform otherTo)
        {
            for(var p:rigid)if(p.mesh().intersects(p.from(),p.to(),other,otherFrom.interpolate(otherTo,p.start()),otherFrom.interpolate(otherTo,p.end()),.005,new Vec3(p.bend(),0,p.bend())))return true;
            for(var e:morph){var a=otherFrom.interpolate(otherTo,e.start());var b=otherFrom.interpolate(otherTo,e.end());if(e.envelope().intersects(other.envelope(a,b)))for(int i=0;i<e.a().length;i+=9){var points=new Vec3[6];for(int c=0;c<3;c++){int n=i+c*3;points[c]=e.from().transformPoint(new Vec3(e.a()[n],e.a()[n+1],e.a()[n+2]));points[c+3]=e.to().transformPoint(new Vec3(e.b()[n],e.b()[n+1],e.b()[n+2]));}if(other.intersectsChord(points,new Vec3(e.error(),e.error(),e.error()),a,b))return true;}}return false;
        }
        public boolean airframeIntersectsCargo(List<NervRigidMeshSweepR52> cargo,RigidTransform from,RigidTransform to)
        {for(int i=0;i<aircraftRigidCount;i++){var p=rigid.get(i);for(var mesh:cargo)if(p.mesh().intersects(p.from(),p.to(),mesh,from.interpolate(to,p.start()),from.interpolate(to,p.end()),.005,new Vec3(p.bend(),0,p.bend())))return true;}return false;}
        public boolean intersects(AABB obstacle)
        {
            for(var p:rigid)if(p.envelope().intersects(obstacle)&&p.mesh().intersects(p.from(),p.to(),obstacle.inflate(p.bend(),0,p.bend()),.005))return true;
            for(var e:morph)if(e.envelope().intersects(obstacle))for(int i=0;i<e.a().length;i+=9)
            {var points=new Vec3[6];for(int c=0;c<3;c++){int n=i+c*3;points[c]=e.from().transformPoint(new Vec3(e.a()[n],e.a()[n+1],e.a()[n+2]));points[c+3]=e.to().transformPoint(new Vec3(e.b()[n],e.b()[n+1],e.b()[n+2]));}if(TriangleSweepMeshR52.convexSweepBox(points,e.error(),obstacle))return true;}return false;
        }
        boolean aircraftIntersectsR53(AABB obstacle)
        {
            for(int i=0;i<aircraftRigidCount;i++)
            {var p=rigid.get(i);if(p.envelope().intersects(obstacle)&&p.mesh().intersects(p.from(),p.to(),obstacle.inflate(p.bend(),0,p.bend()),.005))return true;}
            return false;
        }
    }
    private static String sha(byte[] b){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(b));}catch(Exception e){throw new IllegalStateException(e);}}
}

package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.SiloHatchMechanism;
import com.projectseele.entity.SiloHatchMechanism.Spec;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.world.phys.*;

/** Original R16 shutter/frame/cassette source with an explicit net aperture.
 * Only panel span and collar span change; armour/tier/trim thickness stays in
 * source metres. These same vertices drive draw, bearing and movement proof. */
public final class NervSiloHatchGeometryR52
{
    public static final String SOURCE="mesh/tv_facilities_r16.json";
    public static final String SOURCE_SHA="f78e9c72ba6c3901ee55ab9f377832a0a8a3421c190dc5cbda96f9789d4f2cfe";
    public record Piece(NervAirframeGeometryR52.Part part,RigidTransform local,boolean moving){}
    private record Fixed(NervAirframeGeometryR52.Part part,NervRigidMeshSweepR52 mesh){}
    private static final Map<Spec,NervSiloHatchGeometryR52> CACHE=new HashMap<>();
    private final Spec spec;private final List<Fixed> fixed;private final NervAirframeGeometryR52.Part[][] panels;private final NervRigidMeshSweepR52[][] panelMeshes;
    private NervSiloHatchGeometryR52(Spec spec,Map<String,NervAirframeGeometryR52.Part> source)
    {
        this.spec=Objects.requireNonNull(spec);var parts=new ArrayList<NervAirframeGeometryR52.Part>();
        var frame=warp(source.get("hatch_frame"),"frame",0);
        parts.add(spec.serviceColumnPorts()?serviceCarrierExit(serviceFrameReliefs(frame)):frame);
        for(int side:new int[]{-1,1}){var cassette=mirror(warp(source.get("hatch_cassette"),"cassette/"+side,1),side);parts.add(spec.serviceColumnPorts()?serviceCassetteReliefs(cassette):cassette);}
        // Every explicit R52 spec has grounded cassette beams, including
        // the 31m aperture. Undeclared legacy doors use their old renderer.
        for(int side:new int[]{-1,1})for(int end:new int[]{-1,1})parts.add(beam(side,end));
        var fm=new ArrayList<Fixed>();for(var p:parts)fm.add(new Fixed(p,new NervRigidMeshSweepR52(p.xyz())));fixed=List.copyOf(fm);
        panels=new NervAirframeGeometryR52.Part[2][4];panelMeshes=new NervRigidMeshSweepR52[2][4];for(int side=0;side<2;side++)for(int i=0;i<4;i++){var base=mirror(warp(source.get("hatch_panel"),"panel/"+(side==0?-1:1),2),side==0?-1:1);panels[side][i]=spec.uprightGuidePorts()?uprightGuidePorts(base,side,i):spec.serviceColumnPorts()&&i==3?columnPorts(base,side,i):base;panelMeshes[side][i]=new NervRigidMeshSweepR52(panels[side][i].xyz());}
    }
    public static NervSiloHatchGeometryR52 load(EvaOriginalMeshGeometryR52.ByteSource bytes,Spec spec)throws IOException
    {
        byte[] raw=bytes.read(SOURCE);String sha;try{sha=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(raw));}catch(Exception e){throw new IllegalStateException(e);}if(!SOURCE_SHA.equals(sha))throw new IllegalStateException("Declared hatch draw/proof R16 source changed");
        var data=JsonParser.parseString(new String(raw,StandardCharsets.UTF_8)).getAsJsonObject().getAsJsonObject("parts");var parts=new HashMap<String,NervAirframeGeometryR52.Part>();for(String name:List.of("hatch_frame","hatch_cassette","hatch_panel")){var a=data.getAsJsonArray(name);var v=new double[a.size()];for(int i=0;i<v.length;i++)v[i]=a.get(i).getAsFloat();parts.put(name,new NervAirframeGeometryR52.Part(name,v));}return new NervSiloHatchGeometryR52(spec,parts);
    }
    public static synchronized NervSiloHatchGeometryR52 loadClasspath(Spec spec)throws IOException
    {var result=CACHE.get(spec);if(result==null){result=load(EvaOriginalMeshGeometryR52::classpathBytes,spec);CACHE.put(spec,result);}return result;}
    /** The original upright carrier leaves the opened service pit through its
     * front collar. Keep the side corners, rear half and all separate cassettes.
     * This exact polygon subtraction never changes a moving shutter panel. */
    private static NervAirframeGeometryR52.Part serviceCarrierExit(NervAirframeGeometryR52.Part source) {
        var out=new ArrayList<Double>();var values=source.vertices();
        for(int n=0;n<values.length;n+=18){var polygon=new ArrayList<double[]>();for(int c=0;c<3;c++)polygon.add(Arrays.copyOfRange(values,n+c*6,n+c*6+6));
            appendPolygon(out,clipExit(polygon,0,-15.65,false));polygon=clipExit(polygon,0,-15.65,true);
            appendPolygon(out,clipExit(polygon,0,15.65,true));polygon=clipExit(polygon,0,15.65,false);
            appendPolygon(out,clipExit(polygon,2,0,true));
        }
        double[] rgb=new double[out.size()];for(int n=0;n<rgb.length;n++)rgb[n]=out.get(n);return new NervAirframeGeometryR52.Part(source.name(),rgb);
    }
    private static ArrayList<double[]> clipExit(List<double[]> input,int axis,double plane,boolean above) {
        var out=new ArrayList<double[]>();if(input.isEmpty())return out;var a=input.get(input.size()-1);boolean old=above?a[axis]>=plane:a[axis]<=plane;
        for(var b:input){boolean next=above?b[axis]>=plane:b[axis]<=plane;if(old!=next){double f=(plane-a[axis])/(b[axis]-a[axis]);var v=new double[6];for(int c=0;c<6;c++)v[c]=a[c]+(b[c]-a[c])*f;v[axis]=plane;out.add(v);}if(next)out.add(b);a=b;old=next;}return out;
    }
    private static void appendPolygon(List<Double> output,List<double[]> polygon) {
        for(int i=1;i+1<polygon.size();i++){var a=polygon.get(0);var b=polygon.get(i);var c=polygon.get(i+1);var ab=new Vec3(b[0]-a[0],b[1]-a[1],b[2]-a[2]);var ac=new Vec3(c[0]-a[0],c[1]-a[1],c[2]-a[2]);if(ab.cross(ac).lengthSqr()<1e-20)continue;for(var v:List.of(a,b,c))for(double value:v)output.add(value);}
    }
    private NervAirframeGeometryR52.Part warp(NervAirframeGeometryR52.Part p,String name,int kind)
    {
        var a=p.vertices();for(int i=0;i<a.length;i+=6)
        {
            if(kind==0){a[i]=edge(a[i],spec.openingX()/2D-15.5D);a[i+2]=edge(a[i+2],spec.openingZ()/2D-15.5D);if(large()&&spec.separationSign()<0&&a[i+1]<-.10)a[i+1]=-.10;}
            else if(kind==1){double x=a[i];a[i]=spec.pocketX()+(x<16.4?(x-16.4)*spec.innerTrim()/.35:x>20.4?spec.panelWidth()+(x-20.4)*spec.outerTrim()/.3:(x-16.4)*spec.panelWidth()/4D);a[i+1]=a[i+1]*spec.separationSign();a[i+2]=edge(a[i+2],spec.openingZ()/2D-15.5D);}
            else{a[i]*=spec.panelWidth()/4D;a[i+2]*=(spec.openingZ()+2D)/33D;}
        }
        if(kind==1&&spec.separationSign()<0)for(int i=0;i<a.length;i+=18)for(int n=0;n<6;n++){double old=a[i+6+n];a[i+6+n]=a[i+12+n];a[i+12+n]=old;}return new NervAirframeGeometryR52.Part(name,a);
    }
    private static double edge(double value,double offset){return value==0?0:value+Math.signum(value)*offset;}
    private static List<AABB> COLUMN_PORTS;
    private static synchronized List<AABB> columnPortsSource()
    {
        if(COLUMN_PORTS!=null)return COLUMN_PORTS;double[] xyz;try{xyz=NervPlantMotionR52.originalFixedColumnsR52().triangles();}catch(IOException missing){throw new IllegalStateException("Actual original fixed column source required for service panel ports",missing);}var groups=new AABB[4];
        for(int t=0;t<xyz.length;t+=9){var poly=new ArrayList<double[]>();for(int n=0;n<3;n++)poly.add(new double[]{xyz[t+n*3],xyz[t+n*3+1],xyz[t+n*3+2],0,0,0});poly=clip(poly,1,1.05,false);if(poly.isEmpty())continue;double x=0,z=0;for(var p:poly){x+=p[0];z+=p[2];}int group=(x>=0?2:0)+(z>=0?1:0);for(var p:poly){var at=new Vec3(p[0],0,p[2]);groups[group]=groups[group]==null?new AABB(at,at):groups[group].minmax(new AABB(at,at));}}
        var out=new ArrayList<AABB>();for(var b:groups){if(b==null||b.getXsize()<=0||b.getZsize()<=0)throw new IllegalStateException("Four exact original column foot ports required");out.add(b.inflate(.03,0,.03));}return COLUMN_PORTS=List.copyOf(out);
    }
    private List<AABB> columnPortsInHatchFrame()
    {var ports=columnPortsSource();return spec.serviceGantryYawDegrees()==180?ports.stream().map(b->new AABB(-b.maxX,b.minY,-b.maxZ,-b.minX,b.maxY,-b.minZ)).toList():ports;}
    private List<AABB> lowerFixedReliefs(boolean feet)
    {
        var out=new ArrayList<AABB>();try{for(var piece:NervLowerFrameR52.pieces(0))
        {
            if(feet&&!piece.name().startsWith("permanent_column_foot_seat_")||!feet&&!piece.name().endsWith("_cassette_hanger"))continue;
            var frame=spec.serviceGantryRelativeFrame().compose(piece.local());
            if(!feet){if(piece.mesh().triangles().length!=108)throw new IllegalStateException("Actual twelve-triangle rectangular hanger required");out.add(NervRigidMeshSweepR52.transformed(piece.mesh().bounds(),frame));continue;}
            var declaration=piece.declaration();var point=declaration.getAsJsonArray("bearing_point_local");var p=new Vec3(point.get(0).getAsDouble(),point.get(1).getAsDouble(),point.get(2).getAsDouble());var xyz=piece.mesh().triangles();AABB contact=null;int faces=0;
            for(int i=0;i<xyz.length;i+=9){boolean bottom=true;for(int c=0;c<9;c+=3)bottom&=Math.abs(xyz[i+c+1]-p.y)<1e-6&&Math.abs(xyz[i+c]-p.x)<.21&&Math.abs(xyz[i+c+2]-p.z)<.21;if(!bottom)continue;faces++;for(int c=0;c<9;c+=3){var at=frame.transformPoint(new Vec3(xyz[i+c],xyz[i+c+1],xyz[i+c+2]));contact=contact==null?new AABB(at,at):contact.minmax(new AABB(at,at));}}
            if(faces!=2||contact==null||contact.getXsize()*contact.getZsize()<.15)throw new IllegalStateException("Actual finite original floor-pad bottom required for frame recess");
            out.add(new AABB(contact.minX-.003,contact.minY,contact.minZ-.003,contact.maxX+.003,contact.minY+2,contact.maxZ+.003));
            // These named permanent pads stand on complete native floor
            // cells. Their fixed collar pockets must clear that full cell,
            // rather than only the smaller rendered 0.4m pad footprint.
            double x=Math.floor((contact.minX+contact.maxX)/2+.5)-.5,z=Math.floor((contact.minZ+contact.maxZ)/2+.5)-.5;
            out.add(new AABB(x-.004,contact.minY-1-.004,z-.004,x+1+.004,contact.minY+.004,z+1+.004));
        }}catch(IOException missing){throw new IllegalStateException("Actual current lower source required for fixed service joints",missing);}if(out.size()!=(feet?8:4))throw new IllegalStateException("Four exact original service interfaces required");return List.copyOf(out);
    }
    private NervAirframeGeometryR52.Part serviceFrameReliefs(NervAirframeGeometryR52.Part frame)
    {
        if(frame.vertices().length!=240*18)throw new IllegalStateException("Exact R16 frame primitive layout required");
        return primitiveReliefs(frame,Map.of(0,new Relief(12,lowerFixedReliefs(true)),108,new Relief(12,lowerFixedReliefs(true))));
    }
    private NervAirframeGeometryR52.Part serviceCassetteReliefs(NervAirframeGeometryR52.Part cassette)
    {
        var vertices=cassette.vertices();if(vertices.length!=876*18)throw new IllegalStateException("Exact R16 cassette primitive layout required");var ports=new ArrayList<AABB>(columnPortsInHatchFrame().stream().map(b->new AABB(b.minX,-2,b.minZ,b.maxX,2,b.maxZ)).toList());ports.addAll(lowerFixedReliefs(true));
        double lower=Double.POSITIVE_INFINITY,upper=Double.NEGATIVE_INFINITY;for(int i=44*18+1;i<56*18;i+=6){lower=Math.min(lower,vertices[i]);upper=Math.max(upper,vertices[i]);}final double bottom=lower-.001,top=upper+.001;
        // The 0.19m solid floor and its lower housing edge alone receive the
        // actual 40x200mm hanger opening. The upper wall remains unchanged.
        var hangers=lowerFixedReliefs(false).stream().map(b->new AABB(b.minX,bottom,b.minZ,b.maxX,top,b.maxZ)).toList();
        return primitiveReliefs(cassette,Map.of(0,new Relief(12,ports),12,new Relief(32,hangers,true),44,new Relief(12,hangers)));
    }
    private record Relief(int triangles,List<AABB> cuts,boolean surface){Relief(int triangles,List<AABB> cuts){this(triangles,cuts,false);}}
    private static NervAirframeGeometryR52.Part primitiveReliefs(NervAirframeGeometryR52.Part source,Map<Integer,Relief> requests)
    {
        var original=source.vertices();var pieces=new ArrayList<double[]>();for(int t=0;t<original.length/18;){var request=requests.get(t);if(request==null){pieces.add(Arrays.copyOfRange(original,t*18,(t+1)*18));t++;}else{var primitive=Arrays.copyOfRange(original,t*18,(t+request.triangles())*18);pieces.add(request.surface()?NervConvexReliefR53.subtractSurface(primitive,request.cuts()):NervConvexReliefR53.subtract(primitive,request.cuts()));t+=request.triangles();}}int count=pieces.stream().mapToInt(a->a.length).sum(),at=0;var result=new double[count];for(var a:pieces){System.arraycopy(a,0,result,at,a.length);at+=a.length;}return new NervAirframeGeometryR52.Part(source.name(),result);
    }
    private static ArrayList<double[]> clip(List<double[]> source,int axis,double value,boolean above)
    {var out=new ArrayList<double[]>();if(source.isEmpty())return out;var previous=source.get(source.size()-1);boolean old=above?previous[axis]>=value:previous[axis]<=value;for(var current:source){boolean now=above?current[axis]>=value:current[axis]<=value;if(old!=now){double t=(value-previous[axis])/(current[axis]-previous[axis]);var p=new double[6];for(int n=0;n<6;n++)p[n]=previous[n]+(current[n]-previous[n])*t;out.add(p);}if(now)out.add(current.clone());previous=current;old=now;}return out;}
    private NervAirframeGeometryR52.Part columnPorts(NervAirframeGeometryR52.Part source,int side,int index)
    {
        return cutPorts(source,side,index,columnPortsInHatchFrame(),"column_ported_panel");
    }
    /** Exact31m gate-local steel footprint of the two approved outer rails.
     * No opening, collar, original frame or unrelated shutter is enlarged. */
    public static List<AABB> uprightGuideSteelPortsR52()
    {
        // The opposite-corner layout translates each unchanged rail section
        // by29.56m in Z. Keep the original measured working-band/5mm fit.
        return List.of(new AABB(-15.30500001192093,0.0,14.168942955567978,-14.69499998807907,0.0,14.409433785081731),
            new AABB(-15.105000001490117,0.0,13.818280923865956,-14.894999998509883,0.0,14.289229369429654),
            new AABB(14.69499998807907,0.0,-15.39105704443201,15.30500001192093,0.0,-15.150566214918328),
            new AABB(14.894999998509883,0.0,-15.74171907613406,15.105000001490117,0.0,-15.270770630570178));
    }
    public static List<AABB> uprightGuideSteelPortsR52(int earlyVariant)
    {
        var original=uprightGuideSteelPortsR52();if(earlyVariant==-1)return original;
        if(earlyVariant<0||earlyVariant>2)throw new IllegalArgumentException("Explicit early guide variant required");
        // Real rail facets clipped at the three declared hatch working bands,
        // plus the original 5mm fitting allowance. All other gates keep -1.
        double[][] measuredMin={
            {-15.300000011920929,14.089968461005123,-15.100000001490116,13.737660724747258,14.699999988079071,-15.470031538994876,14.899999998509884,-15.82233927525274},
            {-15.33271235874349,14.093606019888554,-15.133711438932943,13.741413182823884,14.66728764125651,-15.466393980111453,14.866288561067066,-15.81858681717611},
            {-15.360978943596338,14.103032231542505,-15.162587493760205,13.751123938073453,14.639021056403665,-15.45696776845749,14.837412506239792,-15.808876061926547}};
        var out=new ArrayList<AABB>();var row=measuredMin[earlyVariant];
        for(int i=0;i<original.size();i++){var b=original.get(i);out.add(new AABB(Math.min(b.minX,row[i*2]-.005),b.minY,Math.min(b.minZ,row[i*2+1]-.005),b.maxX,b.maxY,b.maxZ));}
        return List.copyOf(out);
    }
    public List<AABB> uprightGuideRigidLeafSlotsR52(int side,int index)
    {
        if(!spec.uprightGuidePorts()||side<0||side>1||index<0||index>=4)return List.of();double sign=side==0?-1:1,travel=sign*(spec.pocketX()-index*spec.panelWidth());var out=new ArrayList<AABB>();for(var port:uprightGuideSteelPortsR52(spec.uprightGuideEarlyVariant())){if(Math.signum(port.getCenter().x)!=sign)continue;out.add(port.minmax(port.move(-travel,0,0)));}return List.copyOf(out);
    }
    private NervAirframeGeometryR52.Part uprightGuidePorts(NervAirframeGeometryR52.Part source,int side,int index)
    {return cutPorts(source,side,index,uprightGuideRigidLeafSlotsR52(side,index),"upright_guide_ported_panel");}
    private NervAirframeGeometryR52.Part cutPorts(NervAirframeGeometryR52.Part source,int side,int index,List<AABB> ports,String prefix)
    {
        double offset=(side==0?-1:1)*index*spec.panelWidth();var all=new ArrayList<List<double[]>>();var v=source.vertices();for(int t=0;t<v.length;t+=18){var poly=new ArrayList<double[]>();for(int c=0;c<3;c++){var p=Arrays.copyOfRange(v,t+c*6,t+c*6+6);p[0]+=offset;poly.add(p);}all.add(poly);}
        for(var port:ports){var next=new ArrayList<List<double[]>>();for(var original:all){List<double[]> inner=original;var outside=clip(inner,0,port.minX,false);if(outside.size()>=3)next.add(outside);inner=clip(inner,0,port.minX,true);outside=clip(inner,0,port.maxX,true);if(outside.size()>=3)next.add(outside);inner=clip(inner,0,port.maxX,false);outside=clip(inner,2,port.minZ,false);if(outside.size()>=3)next.add(outside);inner=clip(inner,2,port.minZ,true);outside=clip(inner,2,port.maxZ,true);if(outside.size()>=3)next.add(outside);}all=next;}
        var values=new ArrayList<Double>();for(var poly:all)for(int c=1;c+1<poly.size();c++){var a=poly.get(0);var b=poly.get(c);var d=poly.get(c+1);if(new Vec3(b[0]-a[0],b[1]-a[1],b[2]-a[2]).cross(new Vec3(d[0]-a[0],d[1]-a[1],d[2]-a[2])).lengthSqr()<=1e-20)continue;for(int n:new int[]{0,c,c+1}){var p=poly.get(n);for(int k=0;k<6;k++)values.add(k==0?p[k]-offset:p[k]);}}return new NervAirframeGeometryR52.Part(prefix+"/"+side+"/"+index,values.stream().mapToDouble(Double::doubleValue).toArray());
    }
    private static NervAirframeGeometryR52.Part mirror(NervAirframeGeometryR52.Part part,int side)
    {var a=part.vertices();if(side<0)for(int i=0;i<a.length;i+=18){for(int j=0;j<3;j++)a[i+j*6]=-a[i+j*6];for(int j=0;j<6;j++){double old=a[i+6+j];a[i+6+j]=a[i+12+j];a[i+12+j]=old;}}return new NervAirframeGeometryR52.Part(part.name(),a);}
    private NervAirframeGeometryR52.Part beam(int side,int end)
    {
        double x0=spec.openingX()/2D+.3,x1=spec.caseOuterX(),z=spec.openingZ()/2D;double inner=spec.separationSign()<0?z+1.05:z+.3,outer=spec.separationSign()<0?z+2.9:z+.9;return box("bearing/"+side+"/"+end,side>0?x0:-x1,spec.beamBottom(),end>0?inner:-outer,side>0?x1:-x0,-.35,end>0?outer:-inner,74,84,78);
    }
    private boolean large(){return spec.openingX()>31||spec.openingZ()>31;}
    private static NervAirframeGeometryR52.Part box(String name,double x0,double y0,double z0,double x1,double y1,double z1,int r,int g,int b)
    {
        var p=new Vec3[]{new Vec3(x0,y0,z0),new Vec3(x1,y0,z0),new Vec3(x1,y1,z0),new Vec3(x0,y1,z0),new Vec3(x0,y0,z1),new Vec3(x1,y0,z1),new Vec3(x1,y1,z1),new Vec3(x0,y1,z1)};int[] faces={0,2,1,0,3,2,4,5,6,4,6,7,0,1,5,0,5,4,3,7,6,3,6,2,0,4,7,0,7,3,1,2,6,1,6,5};var a=new double[faces.length*6];for(int i=0;i<faces.length;i++){var q=p[faces[i]];int n=i*6;a[n]=q.x;a[n+1]=q.y;a[n+2]=q.z;a[n+3]=r;a[n+4]=g;a[n+5]=b;}return new NervAirframeGeometryR52.Part(name,a);
    }
    public Spec spec(){return spec;}
    public List<Piece> pieces(float open)
    {
        validate(open);var parts=new ArrayList<Piece>();for(var p:fixed)parts.add(new Piece(p.part(),RigidTransform.identity(),false));for(int side=0;side<2;side++)for(int i=0;i<SiloHatchMechanism.PANELS;i++){var p=SiloHatchMechanism.panel(i,open,spec);parts.add(new Piece(panels[side][i],new RigidTransform(new Vec3((side==0?-1:1)*p.x(),p.y(),0),0,0,0,1),true));}return List.copyOf(parts);
    }
    public List<Vec3> bearingPoints()
    {
        var points=new ArrayList<Vec3>();for(int side:new int[]{-1,1})for(int end:new int[]{-1,1})for(double x:new double[]{spec.openingX()/2D+.6,spec.caseOuterX()-.3})points.add(new Vec3(side*x,spec.beamBottom(),end*(spec.openingZ()/2D+(spec.separationSign()<0?2.6:.6))));
        return List.copyOf(points);
    }
    public AABB bounds(float open)
    {validate(open);AABB all=null;for(var p:fixed)all=all==null?p.mesh().bounds():all.minmax(p.mesh().bounds());for(int side=0;side<2;side++)for(int i=0;i<SiloHatchMechanism.PANELS;i++)all=all.minmax(NervRigidMeshSweepR52.transformed(panelMeshes[side][i].bounds(),panelFrame(RigidTransform.identity(),side,i,open)));return all;}
    private int divisions(float from,float to)
    {double d=Math.abs(to-from),coefficient=Math.max(spec.maximumTier()*6/(.3*.3*8),spec.pocketX()*6/(.7*.7*8));int n=Math.max(1,(int)Math.ceil(d*Math.sqrt(coefficient/.003)));if(n>4096)throw new IllegalStateException("Explicit hatch curve exceeds its physical subdivision budget");return n;}
    private Vec3 curveError(float from,float to,RigidTransform frame)
    {double d=to-from,x=spec.pocketX()*6*d*d/(.7*.7*8),y=spec.maximumTier()*6*d*d/(.3*.3*8);var axis=frame.transformVector(new Vec3(1,0,0));return new Vec3(Math.abs(axis.x)*x,y,Math.abs(axis.z)*x);}
    public List<AABB> envelopes(RigidTransform frame,float from,float to)
    {
        validate(from);validate(to);var boxes=new ArrayList<AABB>();for(var p:fixed)boxes.addAll(p.mesh().leafEnvelopes(frame,frame));int n=divisions(from,to);for(int step=0;step<n;step++){float a=from+(to-from)*step/n,b=from+(to-from)*(step+1)/n;var pad=curveError(a,b,frame);for(int side=0;side<2;side++)for(int i=0;i<SiloHatchMechanism.PANELS;i++){var pf=panelFrame(frame,side,i,a);var pt=panelFrame(frame,side,i,b);for(var box:panelMeshes[side][i].leafEnvelopes(pf,pt))boxes.add(box.inflate(pad.x,pad.y,pad.z));}}return List.copyOf(boxes);
    }
    private RigidTransform panelFrame(RigidTransform frame,int side,int index,float open)
    {var p=SiloHatchMechanism.panel(index,open,spec);return frame.compose(new RigidTransform(new Vec3((side==0?-1:1)*p.x(),p.y(),0),0,0,0,1));}
    public boolean intersects(RigidTransform frame,float from,float to,AABB obstacle)
    {
        for(var p:fixed)if(p.mesh().intersects(frame,frame,obstacle,.005))return true;int n=divisions(from,to);for(int step=0;step<n;step++){float a=from+(to-from)*step/n,b=from+(to-from)*(step+1)/n;var error=curveError(a,b,frame);var expanded=obstacle.inflate(error.x,error.y,error.z);for(int side=0;side<2;side++)for(int i=0;i<SiloHatchMechanism.PANELS;i++)if(panelMeshes[side][i].intersects(panelFrame(frame,side,i,a),panelFrame(frame,side,i,b),expanded,.005))return true;}return false;
    }
    public boolean intersects(RigidTransform frame,float from,float to,NervRigidMeshSweepR52 other,RigidTransform otherFrom,RigidTransform otherTo)
    {
        for(var p:fixed)if(p.mesh().intersects(frame,frame,other,otherFrom,otherTo,.005,Vec3.ZERO))return true;int n=divisions(from,to);for(int step=0;step<n;step++){float a=from+(to-from)*step/n,b=from+(to-from)*(step+1)/n;var of=otherFrom.interpolate(otherTo,(double)step/n);var ot=otherFrom.interpolate(otherTo,(double)(step+1)/n);for(int side=0;side<2;side++)for(int i=0;i<SiloHatchMechanism.PANELS;i++)if(panelMeshes[side][i].intersects(panelFrame(frame,side,i,a),panelFrame(frame,side,i,b),other,of,ot,.005,curveError(a,b,frame)))return true;}return false;
    }
    public boolean movingIntersects(RigidTransform frame,float from,float to,NervRigidMeshSweepR52 other,RigidTransform otherFrame)
    {int n=divisions(from,to);for(int step=0;step<n;step++){float a=from+(to-from)*step/n,b=from+(to-from)*(step+1)/n;for(int side=0;side<2;side++)for(int i=0;i<SiloHatchMechanism.PANELS;i++)if(panelMeshes[side][i].intersects(panelFrame(frame,side,i,a),panelFrame(frame,side,i,b),other,otherFrame,otherFrame,.005,curveError(a,b,frame)))return true;}return false;}
    private static void validate(float open){if(!Float.isFinite(open)||open<0||open>1)throw new IllegalArgumentException("Actual hatch sample required");}
}

package com.projectseele.world;
import com.google.gson.*;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.world.phys.*;

/** Root's eight vertical armoured panels: separate into four depth tiers,
 * then stack horizontally in the two grounded side pockets. */
public final class NervHangarGateGeometryR52
{
    public record SealBox(double minX,double minY,double minZ,double maxX,double maxY,double maxZ)
    {public SealBox{if(!Double.isFinite(minX+minY+minZ+maxX+maxY+maxZ)||minX>=maxX||minY>=maxY||minZ>=maxZ)throw new IllegalArgumentException("Actual finite sealed floor boxes required");}public AABB bounds(){return new AABB(minX,minY,minZ,maxX,maxY,maxZ);}}
    public record BottomSeal(List<SealBox> closedBoxes,double dropM,double retreatLocalZ,int version,int retainedBoxCount)
    {
        public BottomSeal(List<SealBox> boxes,double drop,double retreat){this(boxes,drop,retreat,1,0);}
        public BottomSeal{closedBoxes=List.copyOf(closedBoxes);if(closedBoxes.isEmpty()||closedBoxes.size()>(version==1?64:512)||!Double.isFinite(dropM+retreatLocalZ)||dropM<=0||dropM>6||retreatLocalZ<=0||retreatLocalZ>32||version!=1&&version!=2||version==1&&retainedBoxCount!=0||version==2&&(retainedBoxCount<=0||retainedBoxCount>=closedBoxes.size()||retainedBoxCount>64))throw new IllegalArgumentException("Finite actual bay floor seal, explicit version and retained original mechanism required");}
    }
    public record Spec(float width,float height,int openTicks,int closeTicks,int depthDirection,BottomSeal bottomSeal)
    {
        public Spec(float width,float height,int openTicks,int closeTicks){this(width,height,openTicks,closeTicks,1);}
        public Spec(float width,float height,int openTicks,int closeTicks,int depthDirection){this(width,height,openTicks,closeTicks,depthDirection,null);}
        public Spec{if(!Float.isFinite(width+height)||width<=0||height<=0||openTicks<=0||closeTicks<=0||(depthDirection!=1&&depthDirection!=-1))throw new IllegalArgumentException("Explicit positive side-stack aperture/clocks and signed depth required");}
        public double panelWidth(){return width/8D;}
        public double gap(){return Math.min(.9,.15*width/33D);}
        public double wall(){return Math.min(.3,.1*width/33D);}
        public double pocket(){return width/2D+gap();}
        public double outer(){return pocket()+panelWidth()+wall();}
        public double inner(){return width/2D+Math.min(.05,gap()/3);}
    }
    public record Panel(double x,double z){}
    public record Piece(NervAirframeGeometryR52.Part part,RigidTransform local,boolean moving){}
    private record Fixed(NervAirframeGeometryR52.Part part,NervRigidMeshSweepR52 mesh){}
    private static final Map<Spec,NervHangarGateGeometryR52> CACHE=new HashMap<>();
    private final Spec spec;private final List<Fixed> fixed;private final NervAirframeGeometryR52.Part[] panels;private final NervRigidMeshSweepR52[] meshes;private final NervWetFloorSealR52 bottom;
    private NervHangarGateGeometryR52(Spec spec,NervAirframeGeometryR52.Part source)
    {
        this.spec=spec;bottom=spec.bottomSeal()==null?null:new NervWetFloorSealR52(spec);var statics=new ArrayList<NervAirframeGeometryR52.Part>();double h=spec.width()/2D,outer=spec.outer(),inner=spec.inner(),wall=spec.wall();
        // No bottom crossbar occupies the net hole. Both side cassettes bear
        // directly on Root's foundation; front jambs clear the travelling
        // panels after their minimum 1.1m depth separation.
        for(int side:new int[]{-1,1})
        {
            statics.add(box("jamb/"+side,side>0?h+.02:-h-.22,0,-.35,side>0?h+.22:-h-.02,spec.height()+.35,1.03,74));
            statics.add(box("outer/"+side,side>0?outer-wall:-outer,0,-.35,side>0?outer:-outer+wall,spec.height()+.35,5.73,45));
            statics.add(box("front/"+side,side>0?inner:-outer,0,-.35,side>0?outer:-inner,spec.height()+.35,0,45));
            statics.add(box("back/"+side,side>0?inner:-outer,0,5.48,side>0?outer:-inner,spec.height()+.35,5.73,45));
            statics.add(box("header/"+side,side>0?inner:-outer,spec.height(),-.35,side>0?outer:-inner,spec.height()+.35,5.73,74));
            for(int tier=0;tier<4;tier++)statics.add(box("tier/"+side+"/"+tier,side>0?outer-wall:-outer,spec.height()-.5,1.04+tier*1.1,side>0?outer:-outer+wall,spec.height()-.3,1.1+tier*1.1,160));
        }
        statics.add(box("lintel",-h-.22,spec.height(),-.35,h+.22,spec.height()+.35,1.03,74));var f=new ArrayList<Fixed>();for(var p:statics){if(spec.depthDirection()<0)p=reflectClosedDepth(p);f.add(new Fixed(p,new NervRigidMeshSweepR52(p.xyz())));}fixed=List.copyOf(f);
        panels=new NervAirframeGeometryR52.Part[2];meshes=new NervRigidMeshSweepR52[2];for(int side=0;side<2;side++){var a=source.vertices();for(int i=0;i<a.length;i+=6){double y=a[i+1],z=a[i+2];a[i]*=spec.panelWidth()/4D*(side==0?-1:1);a[i+1]=(z+16.5)*spec.height()/33D;a[i+2]=y;}if(side==1)for(int i=0;i<a.length;i+=18)for(int n=0;n<6;n++){double old=a[i+6+n];a[i+6+n]=a[i+12+n];a[i+12+n]=old;}var panel=new NervAirframeGeometryR52.Part("panel/"+side,a);panels[side]=spec.depthDirection()<0?reflectClosedDepth(panel):panel;meshes[side]=new NervRigidMeshSweepR52(panels[side].xyz());}
    }
    /** Reflection about the actual closed R16 leaf midplane (Z=.49).
     * The closed slab still occupies Z=0..0.98; only its separation and
     * pocket steel move to the other side. No rail slot removes leaf steel. */
    private static NervAirframeGeometryR52.Part reflectClosedDepth(NervAirframeGeometryR52.Part p){var a=p.vertices();for(int i=0;i<a.length;i+=6)a[i+2]=.98-a[i+2];for(int i=0;i<a.length;i+=18)for(int n=0;n<6;n++){double old=a[i+6+n];a[i+6+n]=a[i+12+n];a[i+12+n]=old;}return new NervAirframeGeometryR52.Part(p.name(),a);}
    public static NervHangarGateGeometryR52 load(EvaOriginalMeshGeometryR52.ByteSource bytes,Spec spec)throws IOException
    {
        byte[] data=bytes.read(NervSiloHatchGeometryR52.SOURCE);try{if(!HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(data)).equals(NervSiloHatchGeometryR52.SOURCE_SHA))throw new IllegalStateException("Side-stack door source changed");}catch(java.security.NoSuchAlgorithmException bad){throw new IllegalStateException(bad);}var array=JsonParser.parseString(new String(data,StandardCharsets.UTF_8)).getAsJsonObject().getAsJsonObject("parts").getAsJsonArray("hatch_panel");var v=new double[array.size()];for(int i=0;i<v.length;i++)v[i]=array.get(i).getAsFloat();return new NervHangarGateGeometryR52(spec,new NervAirframeGeometryR52.Part("source_panel",v));
    }
    public static synchronized NervHangarGateGeometryR52 loadClasspath(Spec spec)throws IOException{var g=CACHE.get(spec);if(g==null){g=load(EvaOriginalMeshGeometryR52::classpathBytes,spec);CACHE.put(spec,g);}return g;}
    private static NervAirframeGeometryR52.Part box(String name,double x0,double y0,double z0,double x1,double y1,double z1,int color)
    {
        var p=new Vec3[]{new Vec3(x0,y0,z0),new Vec3(x1,y0,z0),new Vec3(x1,y1,z0),new Vec3(x0,y1,z0),new Vec3(x0,y0,z1),new Vec3(x1,y0,z1),new Vec3(x1,y1,z1),new Vec3(x0,y1,z1)};int[] faces={0,2,1,0,3,2,4,5,6,4,6,7,0,1,5,0,5,4,3,7,6,3,6,2,0,4,7,0,7,3,1,2,6,1,6,5};var a=new double[faces.length*6];for(int i=0;i<faces.length;i++){int n=i*6;var q=p[faces[i]];a[n]=q.x;a[n+1]=q.y;a[n+2]=q.z;a[n+3]=color;a[n+4]=color+10;a[n+5]=color+14;}return new NervAirframeGeometryR52.Part(name,a);
    }
    public Spec spec(){return spec;}
    public Panel panel(int index,float progress){validate(progress);double lift=smooth(progress/.3),travel=smooth((progress-.3)/.7),closed=index*spec.panelWidth();return new Panel(closed+(spec.pocket()-closed)*travel,spec.depthDirection()*(1.1+(3-index)*1.1)*lift);}
    private static double smooth(double t){t=Math.max(0,Math.min(1,t));return t*t*(3-2*t);}
    private RigidTransform frame(RigidTransform base,int side,int index,float p){var panel=panel(index,p);return base.compose(new RigidTransform(new Vec3((side==0?-1:1)*panel.x(),0,panel.z()),0,0,0,1));}
    public List<Piece> pieces(float progress){var p=new ArrayList<Piece>();for(var f:fixed)p.add(new Piece(f.part(),RigidTransform.identity(),false));for(int side=0;side<2;side++)for(int i=0;i<4;i++)p.add(new Piece(panels[side],frame(RigidTransform.identity(),side,i,progress),true));if(bottom!=null)p.addAll(bottom.pieces(progress));return List.copyOf(p);}
    /** New horizontal native wall contacts are explicit; original8 floor feet stay unchanged. */
    public List<Vec3> bottomSealBearingPointsR52(){return bottom==null?List.of():bottom.bearingPoints();}
    public List<Vec3> bearingPoints(){var p=new ArrayList<Vec3>();for(int side:new int[]{-1,1})for(double x:new double[]{spec.inner()+.1,spec.outer()-spec.wall()/2})for(double z:new double[]{-.175,5.605})p.add(new Vec3(side*x,0,spec.depthDirection()<0?.98-z:z));return List.copyOf(p);}
    public AABB bounds(float progress){AABB box=null;for(var f:fixed)box=box==null?f.mesh().bounds():box.minmax(f.mesh().bounds());for(int side=0;side<2;side++)for(int i=0;i<4;i++)box=box.minmax(NervRigidMeshSweepR52.transformed(meshes[side].bounds(),frame(RigidTransform.identity(),side,i,progress)));return bottom==null?box:box.minmax(bottom.bounds(progress));}
    private int divisions(float a,float b){int n=Math.max(1,(int)Math.ceil(Math.abs(a-b)*Math.sqrt(Math.max(spec.pocket()*6/(.7*.7*8),4.4*6/(.3*.3*8))/.003)));if(n>4096)throw new IllegalStateException("Side-stack curve budget exceeded");return n;}
    private Vec3 error(RigidTransform base,float a,float b){double d=b-a,x=spec.pocket()*6*d*d/(.7*.7*8),z=4.4*6*d*d/(.3*.3*8);var ax=base.transformVector(new Vec3(1,0,0));var az=base.transformVector(new Vec3(0,0,1));return new Vec3(Math.abs(ax.x)*x+Math.abs(az.x)*z,0,Math.abs(ax.z)*x+Math.abs(az.z)*z);}
    public List<AABB> envelopes(RigidTransform base,float from,float to){validate(from);validate(to);var boxes=new ArrayList<AABB>();for(var f:fixed)boxes.addAll(f.mesh().leafEnvelopes(base,base));int n=divisions(from,to);for(int step=0;step<n;step++){float a=from+(to-from)*step/n,b=from+(to-from)*(step+1)/n;var pad=error(base,a,b);for(int side=0;side<2;side++)for(int i=0;i<4;i++)for(var box:meshes[side].leafEnvelopes(frame(base,side,i,a),frame(base,side,i,b)))boxes.add(box.inflate(pad.x,0,pad.z));}if(bottom!=null)boxes.addAll(bottom.envelopes(base,from,to));return List.copyOf(boxes);}
    public boolean intersects(RigidTransform base,float from,float to,AABB obstacle){for(var f:fixed)if(f.mesh().intersects(base,base,obstacle,.005))return true;int n=divisions(from,to);for(int step=0;step<n;step++){float a=from+(to-from)*step/n,b=from+(to-from)*(step+1)/n;var e=error(base,a,b);for(int side=0;side<2;side++)for(int i=0;i<4;i++)if(meshes[side].intersects(frame(base,side,i,a),frame(base,side,i,b),obstacle.inflate(e.x,0,e.z),.005))return true;}return bottom!=null&&bottom.intersects(base,from,to,obstacle);}
    public boolean intersects(RigidTransform base,float from,float to,NervRigidMeshSweepR52 obstacle,RigidTransform obstacleFrame){for(var f:fixed)if(f.mesh().intersects(base,base,obstacle,obstacleFrame,obstacleFrame,.005,Vec3.ZERO))return true;int n=divisions(from,to);for(int step=0;step<n;step++){float a=from+(to-from)*step/n,b=from+(to-from)*(step+1)/n;var e=error(base,a,b);for(int side=0;side<2;side++)for(int i=0;i<4;i++)if(meshes[side].intersects(frame(base,side,i,a),frame(base,side,i,b),obstacle,obstacleFrame,obstacleFrame,.005,e))return true;}return bottom!=null&&bottom.intersects(base,from,to,obstacle,obstacleFrame,obstacleFrame);}
    public boolean intersects(RigidTransform base,float from,float to,NervRigidMeshSweepR52 obstacle,RigidTransform obstacleFrom,RigidTransform obstacleTo){for(var f:fixed)if(f.mesh().intersects(base,base,obstacle,obstacleFrom,obstacleTo,.005,Vec3.ZERO))return true;int n=divisions(from,to);for(int step=0;step<n;step++){float a=from+(to-from)*step/n,b=from+(to-from)*(step+1)/n;var e=error(base,a,b);var of=obstacleFrom.interpolate(obstacleTo,(double)step/n);var ot=obstacleFrom.interpolate(obstacleTo,(double)(step+1)/n);for(int side=0;side<2;side++)for(int i=0;i<4;i++)if(meshes[side].intersects(frame(base,side,i,a),frame(base,side,i,b),obstacle,of,ot,.005,e))return true;}return bottom!=null&&bottom.intersects(base,from,to,obstacle,obstacleFrom,obstacleTo);}
    private static void validate(float p){if(!Float.isFinite(p)||p<0||p>1)throw new IllegalArgumentException("Actual side-stack sample required");}
}

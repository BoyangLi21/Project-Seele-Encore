package com.projectseele.world;


import com.projectseele.entity.*;

import com.projectseele.world.NervRouteDirectoryR52.*;

import java.io.IOException;

import java.util.*;

import net.minecraft.server.level.ServerLevel;

import net.minecraft.world.entity.*;

import net.minecraft.world.phys.*;

import org.joml.Quaternionf;


/** Real supported axle couplings and retracting T-head stubs at existing

 * Root foot-axis turns. This class owns geometry/proofs, never a new clock,

 * map node, entity placement or a carrier commit. */

public final class NervFootGuideDockR52 {

    public static final double TURN_CLEARANCE=3.4,BRIDGE_WITHDRAWAL=1.5;

    /** Root-approved compression only at these named finite bearing faces. */

    public static final double CONTACT_COMPRESSION=.0002;

    public static final String SOURCE="mesh/foot_guide_dock_r52.json",SOURCE_SHA="45cf09ba27dd4fecd375270ebeadf36b5d519aa398f0a7fc726d869b479890f9";

    public enum Stage { COUPLE,OPEN_INCOMING,TURN,CLOSE_OUTGOING,RELEASE }

    public record Sample(Stage stage,double fraction){public Sample{if(stage==null||!Double.isFinite(fraction)||fraction<0||fraction>1)throw new IllegalArgumentException("Finite physical docking phase required");}}

    public record Spec(NervRouteDirectoryR52 directory,Leg leg,FootSupportFrameR52.Binding binding,Vec3 fromUp,Vec3 toUp,double foundationTop){

        public Spec{if(directory==null||leg==null||binding==null||!leg.equals(directory.leg(leg.id()))||leg.motion()!=Motion.FOOT_BEARING_TURN||!Double.isFinite(foundationTop)||!finiteUnit(fromUp)||!finiteUnit(toUp)||directory.node(leg.from()).footFrame().translation().distanceToSqr(directory.node(leg.to()).footFrame().translation())>1e-10)throw new IllegalArgumentException("Existing stationary Root bearing turn required");}

    }

    /** Canonical immutable Root snapshot; graphical clients need no server

     * directory or permissive callback to reconstruct this exact geometry. */

    public record ViewSpec(int variant,String legId,FootSupportFrameR52.Binding binding,RigidTransform footFrom,RigidTransform footTo,Quaternionf bodyFrom,Quaternionf bodyTo,Vec3 fromUp,Vec3 toUp,double foundationTop){

        public ViewSpec{if(variant<0||variant>2||legId==null||binding==null||footFrom==null||footTo==null||bodyFrom==null||bodyTo==null||!finiteUnit(fromUp)||!finiteUnit(toUp)||!Double.isFinite(foundationTop)||footFrom.translation().distanceToSqr(footTo.translation())>1e-10)throw new IllegalArgumentException("Actual canonical Root turn snapshot required");bodyFrom=new Quaternionf(bodyFrom);bodyTo=new Quaternionf(bodyTo);}

        @Override public Quaternionf bodyFrom(){return new Quaternionf(bodyFrom);}@Override public Quaternionf bodyTo(){return new Quaternionf(bodyTo);}

    }

    /** Five actual mechanism coordinates; no coordinate permits hiding or

     * scaling a part. A reverse job addresses the same canonical mechanism. */

    public record StationPose(double turn,double incoming,double outgoing,double coupling,double raised){public StationPose{for(double v:new double[]{turn,incoming,outgoing,coupling,raised})if(!Double.isFinite(v)||v<0||v>1)throw new IllegalArgumentException("Finite real station coordinates required");}}

    private static boolean reverse(Spec s){return s.leg().id().endsWith("/reverse");}

    public static ViewSpec view(Spec s){boolean r=reverse(s);var leg=r?s.directory().leg(s.leg().id().substring(0,s.leg().id().length()-8)):s.leg();var feet=new FootSupportFrameR52.Binding(s.binding().leftFoot(),s.binding().rightFoot(),RigidTransform.identity());return new ViewSpec(variant(s),leg.id(),feet,s.directory().node(leg.from()).footFrame(),s.directory().node(leg.to()).footFrame(),leg.evaFrom().quaternion(),leg.evaTo().quaternion(),r?s.toUp():s.fromUp(),r?s.fromUp():s.toUp(),s.foundationTop());}

    public static StationPose stationPose(Spec s,Sample sample){double t=turnFraction(sample),in=incoming(sample),out=outgoing(sample);return new StationPose(reverse(s)?1-t:t,reverse(s)?out:in,reverse(s)?in:out,coupled(sample),1);}

    public static RigidTransform root(ViewSpec s,double turn){return FootSupportFrameR52.sample(s.binding(),s.footFrom().interpolate(s.footTo(),turn),s.bodyFrom(),s.bodyTo(),turn).evaRoot();}

    private static Vec3 up(ViewSpec s,double turn){if(turn==0)return s.fromUp();if(turn==1)return s.toUp();var q=new Quaternionf().rotationTo(s.fromUp().toVector3f(),s.toUp().toVector3f());var desired=new Vec3(new Quaternionf().slerp(q,(float)turn).transform(s.fromUp().toVector3f())).normalize();var axis=root(s,turn).transformVector(s.binding().rightFoot().subtract(s.binding().leftFoot())).normalize();return desired.subtract(axis.scale(desired.dot(axis))).normalize();}

    private static net.minecraft.nbt.CompoundTag pointTag(Vec3 p){var t=new net.minecraft.nbt.CompoundTag();t.putDouble("X",p.x);t.putDouble("Y",p.y);t.putDouble("Z",p.z);return t;}

    private static Vec3 tagPoint(net.minecraft.nbt.CompoundTag p){return new Vec3(p.getDouble("X"),p.getDouble("Y"),p.getDouble("Z"));}

    public static net.minecraft.nbt.CompoundTag snapshot(Spec spec){return snapshot(view(spec));}

    public static net.minecraft.nbt.CompoundTag snapshot(ViewSpec s){var t=new net.minecraft.nbt.CompoundTag();t.putString("Source",SOURCE_SHA);t.putString("GuideSource",NervFootGuideRigR52.SOURCE_SHA);t.putInt("Variant",s.variant());t.putString("Leg",s.legId());t.put("Left",pointTag(s.binding().leftFoot()));t.put("Right",pointTag(s.binding().rightFoot()));t.put("Plug",NervAircraftFrameR52.encodeRigid(s.binding().plugInEva()));t.put("FootFrom",NervAircraftFrameR52.encodeRigid(s.footFrom()));t.put("FootTo",NervAircraftFrameR52.encodeRigid(s.footTo()));t.put("BodyFrom",NervAircraftFrameR52.encodeRigid(RigidTransform.of(Vec3.ZERO,s.bodyFrom())));t.put("BodyTo",NervAircraftFrameR52.encodeRigid(RigidTransform.of(Vec3.ZERO,s.bodyTo())));t.put("UpFrom",pointTag(s.fromUp()));t.put("UpTo",pointTag(s.toUp()));t.putDouble("FoundationTop",s.foundationTop());return t;}

    public static ViewSpec viewSpec(net.minecraft.nbt.CompoundTag t){if(!t.getString("Source").equals(SOURCE_SHA)||!t.getString("GuideSource").equals(NervFootGuideRigR52.SOURCE_SHA))throw new IllegalStateException("Actual canonical station source snapshot changed");return new ViewSpec(t.getInt("Variant"),t.getString("Leg"),new FootSupportFrameR52.Binding(tagPoint(t.getCompound("Left")),tagPoint(t.getCompound("Right")),NervAircraftFrameR52.decodeRigid(t.getCompound("Plug"))),NervAircraftFrameR52.decodeRigid(t.getCompound("FootFrom")),NervAircraftFrameR52.decodeRigid(t.getCompound("FootTo")),NervAircraftFrameR52.decodeRigid(t.getCompound("BodyFrom")).rotation(),NervAircraftFrameR52.decodeRigid(t.getCompound("BodyTo")).rotation(),tagPoint(t.getCompound("UpFrom")),tagPoint(t.getCompound("UpTo")),t.getDouble("FoundationTop"));}

    public static net.minecraft.nbt.CompoundTag encodePose(StationPose p){var t=new net.minecraft.nbt.CompoundTag();t.putDouble("Turn",p.turn());t.putDouble("Incoming",p.incoming());t.putDouble("Outgoing",p.outgoing());t.putDouble("Coupling",p.coupling());t.putDouble("Raised",p.raised());return t;}

    public static StationPose decodePose(net.minecraft.nbt.CompoundTag t){return new StationPose(t.getDouble("Turn"),t.getDouble("Incoming"),t.getDouble("Outgoing"),t.getDouble("Coupling"),t.getDouble("Raised"));}

    public static StationPose interpolate(StationPose a,StationPose b,double t){t=Math.max(0,Math.min(1,t));return new StationPose(a.turn()+(b.turn()-a.turn())*t,a.incoming()+(b.incoming()-a.incoming())*t,a.outgoing()+(b.outgoing()-a.outgoing())*t,a.coupling()+(b.coupling()-a.coupling())*t,a.raised()+(b.raised()-a.raised())*t);}

    private static boolean finiteUnit(Vec3 p){return p!=null&&Double.isFinite(p.lengthSqr())&&Math.abs(p.length()-1)<1e-6;}

    /** Only a Root TURN endpoint loses its old straight overhang. */

    public static boolean cutStartR52(NervRouteDirectoryR52 d,Leg l){return turnNode(d,l.from());}

    public static boolean cutEndR52(NervRouteDirectoryR52 d,Leg l){return turnNode(d,l.to());}

    private static boolean turnNode(NervRouteDirectoryR52 d,String node){for(var route:d.routes().values())for(String id:route.legs()){var l=d.leg(id);if(l.motion()==Motion.FOOT_BEARING_TURN&&(l.from().equals(node)||l.to().equals(node)))return true;}return false;}

    public static RigidTransform root(Spec s,Sample p){return s.directory().sample(s.leg(),turnFraction(p),s.binding()).evaRoot();}

    private static double turnFraction(Sample p){return p.stage().ordinal()<Stage.TURN.ordinal()?0:p.stage()==Stage.TURN?p.fraction():1;}

    /** Exact one-clock interpolation used by the actual stator draw source. */

    public static Vec3 guideUp(Spec s,Sample p){double t=turnFraction(p);if(t==0)return s.fromUp();if(t==1)return s.toUp();var q=new Quaternionf().rotationTo(s.fromUp().toVector3f(),s.toUp().toVector3f());var mid=new Quaternionf().slerp(q,(float)t);var desired=new Vec3(mid.transform(s.fromUp().toVector3f())).normalize();var axis=root(s,p).transformVector(s.binding().rightFoot().subtract(s.binding().leftFoot())).normalize();return desired.subtract(axis.scale(desired.dot(axis))).normalize();}

    public record Piece(String name,NervRigidMeshSweepR52 mesh,double[] rgb,RigidTransform frame,boolean moving){}

    public record SaddleSupport(int faces,double finiteArea,double maximumFit,double minimumNormalAgreement,boolean beamTipBears){public boolean bears(){return faces>=28&&finiteArea>=.0025&&maximumFit<=.0002&&minimumNormalAgreement>.99&&beamTipBears;}}

    private static double planeHeight(double[] xyz,int n,double x,double z){double ax=xyz[n],az=xyz[n+2],bx=xyz[n+3],bz=xyz[n+5],cx=xyz[n+6],cz=xyz[n+8],det=(bz-cz)*(ax-cx)+(cx-bx)*(az-cz);if(Math.abs(det)<1e-12)return Double.NaN;double a=((bz-cz)*(x-cx)+(cx-bx)*(z-cz))/det,b=((cz-az)*(x-cx)+(ax-cx)*(z-cz))/det;if(a< -1e-7||b< -1e-7||a+b>1+1e-7)return Double.NaN;return xyz[n+1]*a+xyz[n+4]*b+xyz[n+7]*(1-a-b);}

    /** Actual outer saddle facets bear on the actual matching lower cradle;

     * three actual flat tip/cup probes close the separate beam load path. */

    public static List<SaddleSupport> saddleSupportsR52(ViewSpec view,StationPose pose)throws IOException{

        var parts=pieces(view,pose);var result=new ArrayList<SaddleSupport>();for(int side:new int[]{-1,1}){var ring=parts.stream().filter(p->p.name().equals("dock_saddle/"+side)).findFirst().orElseThrow();var cup=parts.stream().filter(p->p.name().equals("dock_saddle_cradle/"+side)).findFirst().orElseThrow();var tip=parts.stream().filter(p->p.name().equals("dock_axle_beam/"+side+"/tip")).findFirst().orElseThrow();var relative=cup.frame().inverse().compose(ring.frame());var raw=ring.mesh().triangles();double[] saddle=new double[raw.length];for(int n=0;n<raw.length;n+=3){var p=relative.transformPoint(new Vec3(raw[n],raw[n+1],raw[n+2]));saddle[n]=p.x;saddle[n+1]=p.y;saddle[n+2]=p.z;}int faces=0;double area=0,maximum=0,minimumNormal=1;var xyz=cup.mesh().triangles();for(int n=0;n<xyz.length;n+=9){if(xyz[n+1]<-.280001||xyz[n+4]<-.280001||xyz[n+7]<-.280001)continue;var a=new Vec3(xyz[n],xyz[n+1],xyz[n+2]);var b=new Vec3(xyz[n+3],xyz[n+4],xyz[n+5]);var c=new Vec3(xyz[n+6],xyz[n+7],xyz[n+8]);var point=a.add(b).add(c).scale(1D/3);var normal=b.subtract(a).cross(c.subtract(a)).normalize();double low=Double.POSITIVE_INFINITY;Vec3 outer=null;for(int k=0;k<saddle.length;k+=9){double y=planeHeight(saddle,k,point.x,point.z);if(!Double.isFinite(y)||y>=low)continue;low=y;outer=new Vec3(saddle[k+3]-saddle[k],saddle[k+4]-saddle[k+1],saddle[k+5]-saddle[k+2]).cross(new Vec3(saddle[k+6]-saddle[k],saddle[k+7]-saddle[k+1],saddle[k+8]-saddle[k+2])).normalize();}if(outer==null){maximum=Double.POSITIVE_INFINITY;continue;}maximum=Math.max(maximum,Math.abs(low-point.y));minimumNormal=Math.min(minimumNormal,Math.abs(normal.dot(outer)));faces++;area+=b.subtract(a).cross(c.subtract(a)).length()*.25;}

            boolean tipBears=true;var toTip=tip.frame().inverse().compose(cup.frame());var top=tip.mesh().triangles();for(var point:List.of(new Vec3(-.04,-.29,-.04),new Vec3(.04,-.29,-.04),new Vec3(0,-.29,.04))){var p=toTip.transformPoint(point);boolean found=false;for(int n=0;n<top.length;n+=9){double y=planeHeight(top,n,p.x,p.z);if(Double.isFinite(y)&&Math.abs(y-p.y)<=.0002)found=true;}tipBears&=found;}

            result.add(new SaddleSupport(faces,area,maximum,minimumNormal,tipBears));}return List.copyOf(result);

    }

    public record Foot(String name,Vec3 centre,double halfX,double halfZ){}

    private static final Map<String,Piece> boxTemplates=new HashMap<>();

    private static synchronized Piece box(String name,AABB b,RigidTransform f,boolean moving){String key=name+"/"+b;var p=boxTemplates.get(key);if(p==null){var made=NervServiceFootDriveR52.box(name,b,RigidTransform.identity(),moving);p=new Piece(name,made.mesh(),made.rgb(),RigidTransform.identity(),moving);boxTemplates.put(key,p);}return new Piece(name,p.mesh(),p.rgb(),f,moving);}

    private static final Map<String,Piece> fixedCantilevers=new HashMap<>();

    private static Piece saddleCradle(String name,RigidTransform frame){String key="saddle_cradle_template";var template=fixedCantilevers.get(key);if(template==null){var rgb=new ArrayList<Double>();int[] faces={0,2,1,0,3,2,4,5,6,4,6,7,0,1,5,0,5,4,3,7,6,3,6,2,0,4,7,0,7,3,1,2,6,1,6,5};for(int k=-14;k<14;k++){double z0=(float)(.28*Math.sin(k*Math.PI/128)),z1=(float)(.28*Math.sin((k+1)*Math.PI/128)),y0=(float)(-.28*Math.cos(k*Math.PI/128)),y1=(float)(-.28*Math.cos((k+1)*Math.PI/128));Vec3[] v={new Vec3(-.10,-.29,z0),new Vec3(.10,-.29,z0),new Vec3(.10,y0,z0),new Vec3(-.10,y0,z0),new Vec3(-.10,-.29,z1),new Vec3(.10,-.29,z1),new Vec3(.10,y1,z1),new Vec3(-.10,y1,z1)};for(int i:faces){var p=v[i];for(double value:new double[]{(float)p.x,(float)p.y,(float)p.z,.36,.43,.48})rgb.add(value);}}double[] color=rgb.stream().mapToDouble(Double::doubleValue).toArray(),xyz=new double[color.length/2];for(int n=0,i=0;n<color.length;n+=6){xyz[i++]=color[n];xyz[i++]=color[n+1];xyz[i++]=color[n+2];}template=new Piece(key,new NervRigidMeshSweepR52(xyz),color,RigidTransform.identity(),true);fixedCantilevers.put(key,template);}return new Piece(name,template.mesh(),template.rgb(),frame,true);}

    private static synchronized Piece cantileverArc(String name,Vec3 a,Vec3 b,Vec3 A,Vec3 B){String key=name+"/"+a+"/"+b+"/"+A+"/"+B;var known=fixedCantilevers.get(key);if(known!=null)return known;Vec3[] corners={Vec3.ZERO,b.subtract(a),B.subtract(a),A.subtract(a),new Vec3(0,.10,0),b.subtract(a).add(0,.10,0),B.subtract(a).add(0,.10,0),A.subtract(a).add(0,.10,0)};int[] indices={0,2,1,0,3,2,4,5,6,4,6,7,0,1,5,0,5,4,1,2,6,1,6,5,2,3,7,2,7,6,3,0,4,3,4,7};double[] xyz=new double[indices.length*3],rgb=new double[indices.length*6];for(int n=0;n<indices.length;n++){var p=corners[indices[n]];xyz[n*3]=(float)p.x;xyz[n*3+1]=(float)p.y;xyz[n*3+2]=(float)p.z;for(int c=0;c<3;c++)rgb[n*6+c]=xyz[n*3+c];rgb[n*6+3]=.36;rgb[n*6+4]=.43;rgb[n*6+5]=.48;}known=new Piece(name,new NervRigidMeshSweepR52(xyz),rgb,new RigidTransform(a,0,0,0,1),false);fixedCantilevers.put(key,known);return known;}

    private static RigidTransform axisFrame(Spec s,Sample p){return root(s,p).compose(NervFootGuideRigR52.localBearing(s.binding()));}

    public static List<Piece> pieces(Spec s,Sample p)throws IOException {return buildPieces(s,p);}

    public static List<Piece> pieces(ViewSpec s,StationPose p)throws IOException {return buildPieces(s,p);}

    public static List<Foot> feet(Spec s)throws IOException {return foundationFeet(s);}

    public static List<Foot> feet(ViewSpec s)throws IOException {return foundationFeet(s);}

    public static final class AcceptedDockStep {

        private final UUID actor,station;private final long at;private final net.minecraft.nbt.CompoundTag state,stationBefore;private final Spec spec;private final Sample from,to;private final List<AABB> envelopes;

        private AcceptedDockStep(ServerLevel l,NervCarrierPlatformEntity e,NervCarrierPlatformEntity fixed,Spec s,Sample from,Sample to,List<AABB> boxes){actor=e.getUUID();station=fixed.getUUID();at=l.getGameTime();state=e.originalCarrierStateR52().copy();stationBefore=NervFootGuideStationR52.rawState(fixed).copy();spec=s;this.from=from;this.to=to;envelopes=List.copyOf(boxes);}

        public UUID actor(){return actor;}public UUID station(){return station;}public long checkedAt(){return at;}public Spec spec(){return spec;}public Sample from(){return from;}public Sample to(){return to;}public RigidTransform fromRoot(){return root(spec,from);}public RigidTransform toRoot(){return root(spec,to);}public Vec3 fromUp(){return guideUp(spec,from);}public Vec3 toUp(){return guideUp(spec,to);}public List<AABB> envelopes(){return envelopes;}

        public net.minecraft.nbt.CompoundTag stationState(){var t=new net.minecraft.nbt.CompoundTag();t.putString("Source",SOURCE_SHA);t.putString("Leg",spec.leg().id());t.putString("Stage",to.stage().name());t.putDouble("Fraction",to.fraction());t.putDouble("FoundationTop",spec.foundationTop());t.put("View",snapshot(spec));t.put("Pose",encodePose(stationPose(spec,to)));return t;}

        public boolean current(ServerLevel l){try{return at==l.getGameTime()&&l.getEntity(actor) instanceof NervCarrierPlatformEntity e&&NervOriginalCarrierR52.declared(e)&&e.originalCarrierStateR52().equals(state)&&l.getEntity(station) instanceof NervCarrierPlatformEntity fixed&&NervFootGuideStationR52.declared(fixed)&&NervFootGuideStationR52.rawState(fixed).equals(stationBefore)&&NervFootGuideStationR52.currentPose(fixed).equals(stationPose(spec,from))&&foundationsBear(l,spec);}catch(IOException missing){return false;}}

    }

    public static final class AcceptedStationStep {

        private final UUID station;private final long at;private final net.minecraft.nbt.CompoundTag before;private final ViewSpec view;private final StationPose from,to;private final List<AABB> envelopes;

        private AcceptedStationStep(ServerLevel l,NervCarrierPlatformEntity actor,ViewSpec view,StationPose from,StationPose to,List<AABB> boxes){station=actor.getUUID();at=l.getGameTime();before=NervFootGuideStationR52.rawState(actor).copy();this.view=view;this.from=from;this.to=to;envelopes=List.copyOf(boxes);}

        public UUID station(){return station;}public ViewSpec view(){return view;}public StationPose fromPose(){return from;}public StationPose toPose(){return to;}public long checkedAt(){return at;}public List<AABB> envelopes(){return envelopes;}

        public boolean current(ServerLevel l){try{return at==l.getGameTime()&&l.getEntity(station) instanceof NervCarrierPlatformEntity e&&NervFootGuideStationR52.declared(e)&&NervFootGuideStationR52.rawState(e).equals(before)&&NervFootGuideStationR52.currentPose(e).equals(from)&&foundationsBear(l,view);}catch(IOException missing){return false;}}

    }

    /** Bidirectional prepare/idle motion of the fixed station. An arriving

     * original carrier, EVA or pilot is never in this proof's own set. */

    public static double stationSweepCoefficientR52(ViewSpec view){return 120000+400*(Math.abs(view.footFrom().translation().y-view.foundationTop())+10);}

    public static int stationSweepDivisionsR52(ViewSpec view,double delta){int n=Math.max(16,(int)Math.ceil(Math.abs(delta)*Math.sqrt(stationSweepCoefficientR52(view)/(8*.0015))));if(n>4096)throw new IllegalStateException("Actual station nonlinear curve budget exceeded");return n;}

    public static double stationSweepErrorR52(ViewSpec view,double delta,int divisions){if(divisions<1)throw new IllegalArgumentException("Positive real source divisions required");return .0005+stationSweepCoefficientR52(view)*delta*delta/(8D*divisions*divisions);}

    public static AcceptedStationStep proposeStation(ServerLevel l,NervCarrierPlatformEntity station,ViewSpec view,StationPose from,StationPose to,Set<UUID> own)throws IOException {

        if(!own.equals(Set.of(station.getUUID()))||!NervFootGuideStationR52.declared(station)||!NervFootGuideStationR52.currentPose(station).equals(from)||!snapshot(NervFootGuideStationR52.view(station)).equals(snapshot(view))||from.coupling()!=0||to.coupling()!=0||!foundationsBear(l,view)||saddleSupportsR52(view,from).stream().anyMatch(f->!f.bears())||saddleSupportsR52(view,to).stream().anyMatch(f->!f.bears()))return null;

        double delta=Math.max(Math.abs(from.turn()-to.turn()),Math.max(Math.abs(from.incoming()-to.incoming()),Math.max(Math.abs(from.outgoing()-to.outgoing()),Math.abs(from.raised()-to.raised()))));if(delta>.051)return null;if(from.turn()!=to.turn()&&(from.raised()!=0||to.raised()!=0||from.incoming()!=1||to.incoming()!=1||from.outgoing()!=1||to.outgoing()!=1))return null;

        var boxes=new ArrayList<AABB>();int n=stationSweepDivisionsR52(view,delta);double error=stationSweepErrorR52(view,delta,n);

        for(int k=0;k<n;k++){var a=pieces(view,interpolate(from,to,k/(double)n));var b=pieces(view,interpolate(from,to,(k+1)/(double)n));for(int i=0;i<a.size();i++){var p=a.get(i);var q=b.get(i);if(!p.name().equals(q.name())||p.mesh().triangles().length!=q.mesh().triangles().length)return null;var bound=p.mesh().envelope(p.frame(),q.frame()).inflate(error);boxes.add(bound);if(!EntryPlugEjectionR48.loaded(l,bound))return null;

            for(var shape:l.getBlockCollisions(station,bound))for(var obstacle:shape.toAabbs()){if(p.name().startsWith("dock_foundation/")&&p.mesh().envelope(p.frame(),p.frame()).minY>=obstacle.maxY-.000003&&q.mesh().envelope(q.frame(),q.frame()).minY>=obstacle.maxY-.000003)continue;if(p.mesh().intersects(p.frame(),q.frame(),obstacle.inflate(error),.001))return null;}

            for(var fixed:NervFixedFootGuidesR52.actualPieces(l,bound)){if(namedFixedEndContactR52(p,q,fixed))continue;if(p.mesh().intersects(p.frame(),q.frame(),fixed.mesh(),fixed.frame(),fixed.frame(),.001,new Vec3(error,error,error)))return null;}for(var actor:l.getEntities((Entity)null,bound.inflate(100),e->!own.contains(e.getUUID())&&e.isAlive()&&(e instanceof LivingEntity||e.canBeCollidedWith()||e instanceof NervCarrierPlatformEntity||e instanceof NervSiloDoorEntity||e instanceof NervHangarDoorEntity||e instanceof UNTransportEntity))){if(actor instanceof NervCarrierPlatformEntity carrier&&NervOriginalCarrierR52.declared(carrier)){for(var part:NervOriginalCarrierR52.actualPartsR52(carrier)){if(namedStationContactR52(part,part,view,interpolate(from,to,k/(double)n),interpolate(from,to,(k+1)/(double)n),p))continue;if(p.mesh().intersects(p.frame(),q.frame(),part.mesh(),part.frame(),part.frame(),.001,new Vec3(error,error,error)))return null;}}else{var actual=NervFlightProofR52.actualObstacleMeshes(actor);if(actual==null)return null;if(actual.isEmpty()){if(p.mesh().intersects(p.frame(),q.frame(),actor.getBoundingBox().inflate(error),.001))return null;}else for(var mesh:actual)if(p.mesh().intersects(p.frame(),q.frame(),mesh.mesh(),mesh.frame(),mesh.endFrame(),.001,new Vec3(error,error,error)))return null;}}

        }}return new AcceptedStationStep(l,station,view,from,to,boxes);

    }

    /** Current physical controller, real support tops and full carrier/dock

     * source sweeps are the sole constructor of an accepted small step. */

    public static AcceptedDockStep propose(ServerLevel l,NervCarrierPlatformEntity e,Spec s,Sample from,Sample to,Set<UUID> own)throws IOException {return checkStep(l,e,s,from,to,own);}

    private record Template(double[] rgb,NervRigidMeshSweepR52 mesh){}

    private static Map<String,Template> templates;

    private static synchronized Map<String,Template> templates()throws IOException {

        if(templates!=null)return templates;var bytes=EvaOriginalMeshGeometryR52.classpathBytes(SOURCE);try{if(!java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes)).equals(SOURCE_SHA))throw new IllegalStateException("Actual docking source changed");}catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}

        var j=com.google.gson.JsonParser.parseString(new String(bytes,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();if(!j.get("schema").getAsString().equals("projectseele.r52.actual-foot-guide-dock.v1")||j.get("stride").getAsInt()!=6||!j.get("original_guide_sha256").getAsString().equals(NervFootGuideRigR52.SOURCE_SHA))throw new IllegalStateException("Actual original axle/source pair required");

        var out=new LinkedHashMap<String,Template>();for(var entry:j.getAsJsonObject("parts").entrySet()){var a=entry.getValue().getAsJsonArray();double[] rgb=new double[a.size()],xyz=new double[a.size()/2];for(int n=0,k=0;n<rgb.length;n+=6){for(int c=0;c<6;c++)rgb[n+c]=a.get(n+c).getAsDouble();xyz[k++]=rgb[n];xyz[k++]=rgb[n+1];xyz[k++]=rgb[n+2];}out.put(entry.getKey(),new Template(rgb,new NervRigidMeshSweepR52(xyz)));}templates=Map.copyOf(out);return templates;

    }

    private static int variant(Spec s){int v=-1;for(var r:s.directory().routes().values())if(r.legs().contains(s.leg().id())){if(v!=-1&&v!=r.variant())throw new IllegalStateException("Turn shared by different original variants");v=r.variant();}if(v<0)throw new IllegalStateException("Turn absent from Root routes");return v;}

    private static double coupled(Sample p){return p.stage()==Stage.COUPLE?p.fraction():p.stage()==Stage.RELEASE?1-p.fraction():1;}

    private static double incoming(Sample p){return p.stage()==Stage.COUPLE?0:p.stage()==Stage.OPEN_INCOMING?p.fraction():1;}

    private static double outgoing(Sample p){return p.stage()==Stage.CLOSE_OUTGOING?1-p.fraction():p.stage()==Stage.RELEASE?0:1;}

    private static double ease(double t){t=Math.max(0,Math.min(1,t));return t*t*t*(10+t*(-15+6*t));}

    private static RigidTransform railFrame(Spec s,double end,Vec3 up){var r=s.directory().sample(s.leg(),end,s.binding()).evaRoot();var b=s.binding();var axis=r.transformVector(b.rightFoot().subtract(b.leftFoot())).normalize();var normal=axis.subtract(up.scale(axis.dot(up))).normalize();return NervFootGuideRigR52.bearingFrame(r.transformPoint(b.contactCentre()),normal,up);}

    private static List<Piece> buildPieces(Spec s,Sample p)throws IOException {return buildPieces(view(s),stationPose(s,p));}

    public static Vec3 guideUpR52(ViewSpec spec,double turn){return up(spec,turn);}

    private static RigidTransform axisFrame(ViewSpec s,double turn){return root(s,turn).compose(NervFootGuideRigR52.localBearing(s.binding()));}

    private static Vec3 baseAxis(ViewSpec s){var axis=axisFrame(s,0).transformVector(new Vec3(1,0,0));return new Vec3(axis.x,0,axis.z).normalize();}

    private static Vec3 postAt(ViewSpec s,double turn,int side,double exterior){if(upperDock(s)&&s.legId().contains("/turn_out")&&side==1)exterior-=2.0;var centre=axisFrame(s,0).translation();var anchor=axisFrame(s,turn).transformPoint(new Vec3(side*15.10,0,0));var axis=baseAxis(s);return anchor.add(axis.scale(side*exterior-anchor.subtract(centre).dot(axis))).add(axis.cross(new Vec3(0,1,0)).scale(upperDock(s)?(s.legId().contains("/turn_in")?side*.4+6:side*.4+(side==1?-3:6)):side*.4));}

    private static RigidTransform railFrame(ViewSpec s,double end,Vec3 up){var r=root(s,end);var axis=r.transformVector(s.binding().rightFoot().subtract(s.binding().leftFoot())).normalize();var normal=axis.subtract(up.scale(axis.dot(up))).normalize();return NervFootGuideRigR52.bearingFrame(r.transformPoint(s.binding().contactCentre()),normal,up);}

    private static RigidTransform rotateAbout(RigidTransform frame,RigidTransform pivot,Quaternionf rotation){var local=frame.translation().subtract(pivot.translation());var point=pivot.translation().add(new Vec3(rotation.transform(local.toVector3f())));return RigidTransform.of(point,new Quaternionf(rotation).mul(frame.rotation()).normalize());}

    private static boolean upperDock(ViewSpec s){return s.legId().contains("/exit3/");}

    private static double bridgePark(ViewSpec s,double progress){return ease((progress-(upperDock(s)?.80:.60))/(upperDock(s)?.10:.15));}

    private static RigidTransform bridgeBaseFrame(ViewSpec s,boolean in,int side,double progress)throws IOException{

        var actual=NervFootGuideRigR52.draws(s.binding(),root(s,in?0:1),1,in?s.fromUp():s.toUp()).stream().filter(d->d.part().name().equals("foot_guide_stator_"+side)).findFirst().orElseThrow().frame();

        var rf=new RigidTransform(Vec3.ZERO,actual.qx(),actual.qy(),actual.qz(),actual.qw());

        for(int n=0;n<4;n++){var next=new RigidTransform(Vec3.ZERO,rf.qx(),rf.qy(),rf.qz(),rf.qw());if(next.equals(rf))break;rf=next;}

        var actualCentre=actual.translation();

        var corrected=actualCentre.subtract(rf.transformVector(new Vec3(side*NervFootGuideRigR52.AXIS_EXTENSION,0,0)));

        // The full6.8m head stays intact. This120um tangent seam gap keeps it

        // exterior to the exact installed fixed terminal despite path rounding.

        var translation=corrected.add(rf.transformVector(new Vec3(0,in?.00012:-.00012,(upperDock(s)?1.5*ease(progress/.10)+8.5*ease((progress-.20)/.15):.27*ease(progress/.15)))));

        if(upperDock(s))translation=translation.add(0,6*ease((progress-.10)/.10),0);

        var open=new RigidTransform(translation,rf.qx(),rf.qy(),rf.qz(),rf.qw());double align=ease((progress-(upperDock(s)?.65:.45))/.15);if(align==0)return open;

        var pivot=new Vec3(side*(15.625+NervFootGuideRigR52.AXIS_EXTENSION-15.25),0,.8);var worldPivot=open.transformPoint(pivot);

        var target=NervFootGuideRigR52.bearingFrame(Vec3.ZERO,baseAxis(s),new Vec3(0,1,0)).rotation();var rotation=open.rotation().slerp(target,(float)align).normalize();

        return RigidTransform.of(worldPivot.subtract(new Vec3(rotation.transform(pivot.toVector3f()))),rotation);

    }

    private static synchronized double bridgeRearStroke(ViewSpec s,boolean in,int side)throws IOException{String key="rear/"+in+"/"+side;var known=bridgeStrokes.computeIfAbsent(s,q->new HashMap<>());if(known.containsKey(key))return known.get(key);var axis=baseAxis(s).cross(new Vec3(0,1,0)).scale(side);var origin=axisFrame(s,0).translation();double minimum=Double.POSITIVE_INFINITY,maximumPost=Double.NEGATIVE_INFINITY;for(int k=0;k<=32;k++)maximumPost=Math.max(maximumPost,postAt(s,k/32D,side,21.0).subtract(origin).dot(axis)+.20);for(var foot:foundationFeet(s)){if(!foot.name().startsWith("dock_foot/"+side+"/"))continue;var c=foot.centre();for(int x=(int)Math.floor(c.x-foot.halfX()+1e-7);x<=Math.floor(c.x+foot.halfX()-1e-7);x++)for(int z=(int)Math.floor(c.z-foot.halfZ()+1e-7);z<=Math.floor(c.z+foot.halfZ()-1e-7);z++)for(double X:new double[]{x,x+1})for(double Z:new double[]{z,z+1})maximumPost=Math.max(maximumPost,new Vec3(X,s.foundationTop(),Z).subtract(origin).dot(axis));}for(var p:bridgePieces("rear_measure",side,bridgeBaseFrame(s,in,side,1),1)){var xyz=p.mesh().triangles();for(int n=0;n<xyz.length;n+=3)minimum=Math.min(minimum,p.frame().transformPoint(new Vec3(xyz[n],xyz[n+1],xyz[n+2])).subtract(origin).dot(axis));}double stroke=Math.max(0,maximumPost+.02-minimum);if(stroke>2*42*.62)throw new IllegalStateException("Bounded42-sleeve endpoint travel required");known.put(key,stroke);return stroke;}

    private static RigidTransform bridgeOpen(ViewSpec s,boolean in,int side,double progress)throws IOException {var open=bridgeBaseFrame(s,in,side,progress);double amount=bridgePark(s,progress);if(amount==0)return open;var rearAxis=baseAxis(s).cross(new Vec3(0,1,0)).scale(side);return RigidTransform.of(rearAxis.scale(bridgeRearStroke(s,in,side)*amount),new Quaternionf()).compose(open);}

    private static List<Piece> narrowBridgeT(String name,int side,double lower,double upper,RigidTransform frame){var rows=List.of(new AABB(15.22,lower,.72,15.28,upper,.88),new AABB(15.28,lower,.79,15.555,upper,.81),new AABB(15.505,lower,.30,15.555,upper,1.30),new AABB(15.75,lower,.30,15.80,upper,1.30),new AABB(15.555,lower,.30,15.75,upper,.35),new AABB(15.555,lower,1.25,15.75,upper,1.30),new AABB(15.555,lower,.35,15.75,Math.min(upper,lower+.05),1.25),new AABB(15.555,Math.max(lower,upper-.05),.35,15.75,upper,1.25));var out=new ArrayList<Piece>();double dx=NervFootGuideRigR52.AXIS_EXTENSION-15.25;for(int i=0;i<rows.size();i++){var b=rows.get(i);b=side>0?b.move(dx,0,0):new AABB(-b.maxX-dx,b.minY,b.minZ,-b.minX-dx,b.maxY,b.maxZ);out.add(box(name+"/"+i,b,frame,true));}return List.copyOf(out);}

    /** Three real T modules retain the complete original6.8m guide plane.

     * The two outer modules fold around visible bored steel hinges only

     * after the complete real1.01m rear release; every steel part remains present. */

    private static List<Piece> bridgePieces(String name,int side,RigidTransform frame,double folded)throws IOException{var out=new ArrayList<Piece>();var source=templates();double a=Math.PI*.5*folded,cx=side*(15.625+NervFootGuideRigR52.AXIS_EXTENSION-15.25);for(int segment:new int[]{-1,0,1}){double low=segment<0?-TURN_CLEARANCE:segment==0?-1.2:1.2,high=segment<0?-1.2:segment==0?1.2:TURN_CLEARANCE;var f=frame;if(segment!=0&&folded>0){var pivot=new RigidTransform(new Vec3(cx,segment*1.2,1.4),0,0,0,1);f=frame.compose(pivot).compose(RigidTransform.of(Vec3.ZERO,new Quaternionf().rotationX((float)(segment*a)))).compose(pivot.inverse());}out.addAll(narrowBridgeT(name+"/module_"+segment,side,low,high,f));}

        for(int end:new int[]{-1,1}){var pivot=new RigidTransform(new Vec3(cx,end*1.2,1.4),0,0,0,1);var fixed=frame.compose(pivot);var moving=fixed.compose(RigidTransform.of(Vec3.ZERO,new Quaternionf().rotationX((float)(end*a))));for(int cheek:new int[]{-1,1}){var bearing=source.get("bridge_fold_bearing_outer");out.add(new Piece(name+"/hinge_"+end+"/outer_"+cheek,bearing.mesh(),bearing.rgb(),fixed.compose(new RigidTransform(new Vec3(cheek*.12,0,0),0,0,0,1)),true));double y0=end<0?.06:-.15,y1=end<0?.15:-.06;out.add(box(name+"/hinge_"+end+"/fixed_web_"+cheek,new AABB(cheek*.12-.025,y0,-.15,cheek*.12+.025,y1,0),fixed,true));}for(String n:List.of("bridge_fold_pin","bridge_fold_bearing_inner")){var t=source.get(n);out.add(new Piece(name+"/hinge_"+end+"/"+n,t.mesh(),t.rgb(),moving,true));}double y0=end<0?-.15:.06,y1=end<0?-.06:.15;out.add(box(name+"/hinge_"+end+"/moving_web",new AABB(-.075,y0,-.15,.075,y1,0),moving,true));}return List.copyOf(out);}

    /** Derive the finite side stroke from the entire actual parked T rather

     * than from its centre. The upright original shaft axis stays unchanged. */

    private static final Map<ViewSpec,Map<String,Double>> bridgeStrokes=new HashMap<>();

    private static synchronized double bridgeSideStroke(ViewSpec s,boolean in,int side)throws IOException{String key=in+"/"+side;var known=bridgeStrokes.computeIfAbsent(s,q->new HashMap<>());if(known.containsKey(key))return known.get(key);var centre=axisFrame(s,0).translation();var axis=baseAxis(s).scale(side);double minimum=Double.POSITIVE_INFINITY;var parked=bridgeOpen(s,in,side,1);for(var piece:bridgePieces("park_measure",side,parked,1)){var xyz=piece.mesh().triangles();for(int n=0;n<xyz.length;n+=3)minimum=Math.min(minimum,piece.frame().transformPoint(new Vec3(xyz[n],xyz[n+1],xyz[n+2])).subtract(centre).dot(axis));}double stroke=20.71-minimum;if(stroke<0||stroke>20)throw new IllegalStateException("Finite mid-gap actual T drive required");known.put(key,stroke);return stroke;}

    private static synchronized double bridgeOutsideStroke(ViewSpec s,boolean in,int side)throws IOException{String key="outside/"+in+"/"+side;var known=bridgeStrokes.computeIfAbsent(s,q->new HashMap<>());if(known.containsKey(key))return known.get(key);var origin=axisFrame(s,0).translation();var axis=baseAxis(s).scale(side);double minimum=Double.POSITIVE_INFINITY;for(int k=0;k<=32;k++)for(var p:bridgePieces("outside_measure",side,bridgeBaseFrame(s,in,side,.15+.45*k/32D),ease((.15+.45*k/32D-(upperDock(s)?.35:.30))/.15))){var xyz=p.mesh().triangles();for(int n=0;n<xyz.length;n+=3)minimum=Math.min(minimum,p.frame().transformPoint(new Vec3(xyz[n],xyz[n+1],xyz[n+2])).subtract(origin).dot(axis));}double stroke=Math.max(0,(!upperDock(s)&&s.legId().contains("/turn_in")&&!in?18.04:16.10)-minimum);known.put(key,stroke);return stroke;}

    private static synchronized double bridgeGateInboardStroke(ViewSpec s,boolean in,int side)throws IOException{String key="gate/"+in+"/"+side;var known=bridgeStrokes.computeIfAbsent(s,q->new HashMap<>());if(known.containsKey(key))return known.get(key);var centre=axisFrame(s,0).translation();var axis=baseAxis(s).scale(side);double maximum=Double.NEGATIVE_INFINITY;var parked=bridgeOpen(s,in,side,1);for(var piece:bridgePieces("gate_measure",side,parked,1)){var xyz=piece.mesh().triangles();for(int n=0;n<xyz.length;n+=3)maximum=Math.max(maximum,piece.frame().transformPoint(new Vec3(xyz[n],xyz[n+1],xyz[n+2])).subtract(centre).dot(axis));}double stroke=Math.max(0,maximum-15.40);known.put(key,stroke);return stroke;}

    /** A finite driven branch shares the actual middle steel column. Its

     * nested source tubes, spherical bearings and welded webs remain visible

     * throughout rear release, folding, hub alignment and below-case parking. */

    private static void driveLink(List<Piece> out,Map<String,Template> source,String name,Vec3 start,Vec3 end)throws IOException{

        var delta=end.subtract(start);double length=delta.length();if(length<.62||length>=.62+41*(.62-.010))throw new IllegalStateException("Actual42-sleeve bridge branch has no finite overlap: "+length);

        var direction=delta.scale(1/length);var cross=direction.cross(new Vec3(0,0,1));if(cross.lengthSqr()<.01)cross=direction.cross(new Vec3(1,0,0));var frame=NervFootGuideRigR52.bearingFrame(start,cross.normalize(),direction);var tipFrame=NervFootGuideRigR52.bearingFrame(end,cross.normalize(),direction.scale(-1));

        for(int k=0;k<42;k++){var t=source.get(k<32?"column_telescope_"+k:"bridge_telescope_"+k);out.add(new Piece(name+"/tube/"+k,t.mesh(),t.rgb(),frame.compose(new RigidTransform(new Vec3(0,k*(length-.62)/41,0),0,0,0,1)),true));}

        for(String joint:List.of("base","tip")){var f=joint.equals("base")?frame:tipFrame;for(String part:List.of("ball","socket")){var t=source.get("bridge_drive_"+part+"_"+joint);out.add(new Piece(name+"/"+joint+"/"+part,t.mesh(),t.rgb(),f,true));}double outer=joint.equals("base")?.06:.019,inner=joint.equals("base")?.045:.012;var walls=List.of(new AABB(-outer,0,-outer,-inner,.003,outer),new AABB(inner,0,-outer,outer,.003,outer),new AABB(-inner,0,-outer,inner,.003,-inner),new AABB(-inner,0,inner,inner,.003,outer));for(int k=0;k<4;k++)out.add(box(name+"/"+joint+"/annular_cap/"+k,walls.get(k),f,true));}

    }

    private static void bridgeDrive(List<Piece> out,Map<String,Template> source,String name,int side,boolean in,RigidTransform column,RigidTransform head,ViewSpec s,AABB headSteel)throws IOException{

        double fore=in?.12:-.12;var start=column.transformPoint(new Vec3(0,.31,fore));if(upperDock(s)&&s.legId().contains("/turn_out"))start=start.add(baseAxis(s).scale(side*(side==1?(in?.28:.10):.48)));var seat=column.inverse().transformPoint(start);var actual=headSteel.getCenter();if(upperDock(s)&&s.legId().contains("/turn_out")&&!in&&side==-1)actual=new Vec3(actual.x,-.6,actual.z);if(upperDock(s)&&s.legId().contains("/turn_in")&&in&&side==1)actual=new Vec3(actual.x,-.6,actual.z);if(!upperDock(s))actual=new Vec3(side*(Math.max(Math.abs(headSteel.minX),Math.abs(headSteel.maxX))-.020),actual.y,actual.z);var end=head.transformPoint(actual);driveLink(out,source,name,start,end);

        out.add(box(name+"/existing_column_web",new AABB(Math.min(-.02,seat.x-.02),.29,Math.min(0,seat.z),Math.max(.02,seat.x+.02),.33,Math.max(0,seat.z)),column,true));

        var web=new AABB(Math.min(actual.x,actual.x-side*.010),actual.y-.012,actual.z-.012,Math.max(actual.x,actual.x-side*.010),actual.y+.012,actual.z+.012);out.add(box(name+"/actual_T_backplate_web",web,head,true));

    }

    private static List<Piece> buildPieces(ViewSpec s,StationPose p)throws IOException {

        var source=templates();var out=new ArrayList<Piece>();var f=axisFrame(s,p.turn());double gap=.2*(1-p.coupling());

        for(int side:new int[]{-1,1}){

            var centre=f.transformPoint(new Vec3(side*16.35,0,0));var anchor=f.transformPoint(new Vec3(side*15.10,0,0));var post=postAt(s,p.turn(),side,21.0);var saddle=source.get("saddle_"+side);

            boolean sourceShoe=!(upperDock(s)&&s.legId().contains("/turn_out"));double bottom=s.foundationTop()+(sourceShoe?(side==1?.24:.20):.10),full=anchor.y-.12-bottom,height=.62+(Math.min(full,1.5)-.62)*ease(p.raised()/.20)+(full-Math.min(full,1.5))*ease((p.raised()-.65)/.35),drop=full-height;if(full<.62)throw new IllegalArgumentException("Actual supported telescopes require lower foundation");var initialHorizontal=anchor.subtract(post);initialHorizontal=new Vec3(initialHorizontal.x,0,initialHorizontal.z).normalize();double originalSpan=anchor.subtract(post).dot(initialHorizontal),armSpan=.62+(originalSpan-.62)*ease((p.raised()-.40)/.20);double park=1-ease((p.raised()-.20)/.20);var targetAxis=baseAxis(s).cross(new Vec3(0,1,0)).normalize();var actualAxis=f.transformVector(new Vec3(1,0,0));double yaw=Math.atan2(actualAxis.cross(targetAxis).y,actualAxis.dot(targetAxis))*park;var worldRotation=new Quaternionf().rotationY((float)yaw);var parkDirection=targetAxis.scale(side);double beamYaw=Math.atan2(initialHorizontal.cross(parkDirection).y,initialHorizontal.dot(parkDirection))*park;var horizontal=new Vec3(new Quaternionf().rotationY((float)beamYaw).transform(initialHorizontal.toVector3f())).normalize();var packetAnchor=post.add(horizontal.scale(armSpan)).add(0,-drop,0);var movingAxis=RigidTransform.of(packetAnchor,new Quaternionf(worldRotation).mul(f.rotation()).normalize()).compose(new RigidTransform(new Vec3(-side*15.10,0,0),0,0,0,1));var base=NervFootGuideRigR52.bearingFrame(new Vec3(post.x,bottom,post.z),horizontal,new Vec3(0,1,0));if(sourceShoe){var shoe=NervFootGuideRigR52.bearingFrame(new Vec3(post.x,s.foundationTop()+.10,post.z),baseAxis(s).scale(-side),new Vec3(0,1,0));if(side==1){out.add(box("dock_column_shoe/"+side+"/back",new AABB(.20,0,-.15,.35,.10,.15),shoe,true));for(int toe:new int[]{1})out.add(box("dock_column_shoe/"+side+"/finger/"+toe,new AABB(-.02,0,toe<0?-.14:.10,.20,.10,toe<0?-.10:.14),shoe,true));out.add(box("dock_column_shoe/"+side+"/outer_cap",new AABB(-.10,.10,upperDock(s)?.045:.01,0,.14,.15),shoe,true));}else out.add(box("dock_column_shoe/"+side,new AABB(.04,0,-.02,.35,.10,.02),shoe,true));}var pivot=base.compose(new RigidTransform(new Vec3(0,height+.12,0),0,0,0,1));var foldedPivot=pivot;

            var shaft=source.get("axis_"+side);out.add(new Piece("dock_axis/"+side,shaft.mesh(),shaft.rgb(),movingAxis.compose(new RigidTransform(new Vec3(side*gap,0,0),0,0,0,1)),true));out.add(new Piece("dock_saddle/"+side,saddle.mesh(),saddle.rgb(),movingAxis,true));

            for(int k=0;k<32;k++){var tube=source.get("column_telescope_"+k);var frame=base.compose(new RigidTransform(new Vec3(0,k*(height-.62)/31,0),0,0,0,1));out.add(new Piece("dock_column/"+side+"/"+k,tube.mesh(),tube.rgb(),frame,true));}

            for(String name:List.of("fold_pin","fold_base","fold_socket")){var t=source.get(name);out.add(new Piece("dock_"+name+"/"+side,t.mesh(),t.rgb(),name.equals("fold_pin")?pivot.compose(RigidTransform.of(Vec3.ZERO,new Quaternionf().rotationX((float)(-Math.PI*.5)))):foldedPivot,true));}

            double dx=armSpan;var beam=foldedPivot;double length=Math.abs(dx),direction=Math.signum(dx);if(length<.42||length>12.82)throw new IllegalStateException("Actual32-section cassette-bypass beam overlap required");

            for(int k=0;k<32;k++){double w=.15-k*.0022;var frame=beam.compose(new RigidTransform(new Vec3(direction*k*(length-.42)/31,-.3818,0),0,0,0,1));for(int wall=0;wall<4;wall++){var b=switch(wall){case 0->new AABB(0,-w,-w,.42,-w+.00201,w);case 1->new AABB(0,w-.00201,-w,.42,w,w);case 2->new AABB(0,-w+.00201,-w,.42,w-.00201,-w+.00201);default->new AABB(0,-w+.00201,w-.00201,.42,w-.00201,w);};if(direction<0)b=new AABB(-b.maxX,b.minY,b.minZ,-b.minX,b.maxY,b.maxZ);out.add(box("dock_axle_beam/"+side+"/"+k+"/"+wall,b,frame,true));}}

            double endHalf=.15-31*.0022;out.add(box("dock_axle_beam/"+side+"/tip",new AABB(-.10,-.30,-endHalf,.10,-.29,endHalf),beam.compose(new RigidTransform(new Vec3(dx,0,0),0,0,0,1)),true));out.add(box("dock_fold_connector/"+side,new AABB(.06,-.24,-.08,.16,0,.08),beam,true));

            var cradleFrame=NervFootGuideRigR52.bearingFrame(packetAnchor,movingAxis.transformVector(new Vec3(1,0,0)),new Vec3(0,1,0));out.add(saddleCradle("dock_saddle_cradle/"+side,cradleFrame));

            // Release the real opposed pads first, then lower the complete

            // short bridge below the complete turn envelope. This avoids a

            // stationary bridge clipping the Root's simultaneous yaw turn.

            for(boolean in:new boolean[]{true,false}){double progress=in?p.incoming():p.outgoing();var open=bridgeOpen(s,in,side,progress);var sideAxis=baseAxis(s).scale(side);double bridgePark=bridgePark(s,progress);double lateral=bridgeOutsideStroke(s,in,side)*ease((progress-(upperDock(s)?.50:.15))/.15)*(1-bridgePark)+bridgeSideStroke(s,in,side)*bridgePark;if(lateral!=0)open=RigidTransform.of(sideAxis.scale(lateral),new Quaternionf()).compose(open);var rows=bridgePieces("service_bridge/dock/"+s.legId()+"/"+(in?"in/":"out/")+side,side,open,ease((progress-(upperDock(s)?.35:.30))/.15));double maximum=Double.NEGATIVE_INFINITY;for(var row:rows)maximum=Math.max(maximum,row.mesh().envelope(row.frame(),row.frame()).maxY);double down=(maximum-s.foundationTop()+(upperDock(s)?2.4:-.10))*ease((progress-(upperDock(s)?.90:.75))/(upperDock(s)?.10:.20));for(var piece:rows){var moving=down==0?piece.frame():RigidTransform.of(new Vec3(0,-down,0),new Quaternionf()).compose(piece.frame());out.add(new Piece(piece.name(),piece.mesh(),piece.rgb(),moving,true));}

                var supported=down==0?open:RigidTransform.of(new Vec3(0,-down,0),new Quaternionf()).compose(open);var steel=rows.stream().filter(p0->p0.name().endsWith(upperDock(s)&&s.legId().contains("/turn_out")?"/module_0/2":"/module_0/3")).findFirst().orElseThrow().mesh().bounds();bridgeDrive(out,source,"dock_bridge_drive/"+s.legId()+"/"+(in?"in/":"out/")+side,side,in,base.compose(new RigidTransform(new Vec3(0,height-.62,0),0,0,0,1)),supported,s,steel);

            }

        }

        // Finite supported arc segments under the two moving columns. Their

        // foundation is below the proved complete Root turn envelope, never

        // a floor plate inside the EVA/deck cavity.

        for(int side:new int[]{-1,1})for(int k=0;k<16;k++){

            double inner=18.92,outer=upperDock(s)&&s.legId().contains("/turn_out")?21.08:20.80;var a=postAt(s,k/16D,side,inner);var b=postAt(s,(k+1)/16D,side,inner);var A=postAt(s,k/16D,side,outer);var B=postAt(s,(k+1)/16D,side,outer);a=new Vec3(a.x,s.foundationTop(),a.z);b=new Vec3(b.x,s.foundationTop(),b.z);A=new Vec3(A.x,s.foundationTop(),A.z);B=new Vec3(B.x,s.foundationTop(),B.z);

            if(a.distanceTo(b)<.00001){if(k==0){var axis=A.subtract(a).normalize();var frame=NervFootGuideRigR52.bearingFrame(a,axis,new Vec3(0,1,0));out.add(box("dock_foundation/"+side+"/0",new AABB(0,0,-.08,A.subtract(a).length(),.10,.08),frame,false));}continue;}

            out.add(cantileverArc("dock_foundation/"+side+"/"+k,a,b,A,B));

        }

        for(var foot:foundationFeet(s))out.add(box("dock_foundation/native_pad/"+foot.name(),new AABB(-foot.halfX(),0,-foot.halfZ(),foot.halfX(),.10,foot.halfZ()),new RigidTransform(foot.centre(),0,0,0,1),false));

        return List.copyOf(out);

    }

    private static List<Foot> foundationFeet(Spec s)throws IOException {return foundationFeet(view(s));}

    private static List<Foot> foundationFeet(ViewSpec view)throws IOException {templates();var out=new LinkedHashMap<String,Foot>();for(int side:new int[]{-1,1})for(int k=0;k<=16;k++){var p=postAt(view,k/16D,side,19.0);var centre=new Vec3(p.x,view.foundationTop(),p.z);String key=String.format(java.util.Locale.ROOT,"%.6f/%.6f",centre.x,centre.z);out.putIfAbsent(key,new Foot("dock_foot/"+side+"/"+k,centre,.08,.08));}return List.copyOf(out.values());}

    public static boolean foundationsBear(ServerLevel l,Spec s)throws IOException {return foundationsBear(l,view(s));}

    /** Every square of the actual lower foot face lies on the union of

     * current native upper faces, including feet that span cell seams. */

    public static boolean foundationsBear(ServerLevel l,ViewSpec s)throws IOException {for(var foot:feet(s)){var p=foot.centre();double x0=p.x-foot.halfX(),x1=p.x+foot.halfX(),z0=p.z-foot.halfZ(),z1=p.z+foot.halfZ();var tops=new ArrayList<AABB>();for(int x=(int)Math.floor(x0);x<=Math.floor(x1);x++)for(int z=(int)Math.floor(z0);z<=Math.floor(z1);z++){var at=new net.minecraft.core.BlockPos(x,(int)Math.floor(p.y-.001),z);if(!l.hasChunkAt(at))return false;for(var box:l.getBlockState(at).getCollisionShape(l,at).toAabbs()){var w=box.move(at);if(Math.abs(w.maxY-p.y)<.000003&&w.maxX>x0&&w.minX<x1&&w.maxZ>z0&&w.minZ<z1)tops.add(w);}}var xs=new TreeSet<Double>();var zs=new TreeSet<Double>();xs.add(x0);xs.add(x1);zs.add(z0);zs.add(z1);for(var w:tops){xs.add(Math.max(x0,w.minX));xs.add(Math.min(x1,w.maxX));zs.add(Math.max(z0,w.minZ));zs.add(Math.min(z1,w.maxZ));}var X=new ArrayList<>(xs);var Z=new ArrayList<>(zs);double area=0;for(int x=0;x<X.size()-1;x++)for(int z=0;z<Z.size()-1;z++){double cx=(X.get(x)+X.get(x+1))*.5,cz=(Z.get(z)+Z.get(z+1))*.5;if(tops.stream().anyMatch(w->cx>=w.minX&&cx<=w.maxX&&cz>=w.minZ&&cz<=w.maxZ))area+=(X.get(x+1)-X.get(x))*(Z.get(z+1)-Z.get(z));}if(area<4*foot.halfX()*foot.halfZ()-1e-10)return false;}return true;}

    /** Three non-collinear probes lie on both actual source cap triangles.

     * No bearing follows from centre coincidence or a source AABB. */

    public static boolean finiteAxleContacts(Spec s,Sample sample)throws IOException {

        if(coupled(sample)!=1)return false;var axis=axisFrame(s,sample);var original=NervFootGuideRigR52.draws(s.binding(),root(s,sample),1,guideUp(s,sample));var machine=pieces(s,sample);

        for(int side:new int[]{-1,1}){var rotor=original.stream().filter(d->d.part().name().equals("foot_guide_rotor_"+side)).findFirst().orElseThrow();var shaft=machine.stream().filter(d->d.name().equals("dock_axis/"+side)).findFirst().orElseThrow();double plane=side*(double)(float)14.84;var rf=relative(axis,rotor.frame());var sf=relative(axis,shaft.frame());for(double[] yz:new double[][]{{.035,.021},{.11,.037},{.022,.115}})if(!capContains(rotor.part().mesh(),rf,plane,yz[0],yz[1])||!capContains(shaft.mesh(),sf,plane,yz[0],yz[1]))return false;}return true;

    }

    private static RigidTransform relative(RigidTransform reference,RigidTransform frame){var inverse=reference.rotation().conjugate();var delta=frame.translation().subtract(reference.translation());var local=new Vec3(inverse.transform(delta.toVector3f()));return RigidTransform.of(local,inverse.mul(frame.rotation()));}

    private static boolean capContains(NervRigidMeshSweepR52 mesh,RigidTransform f,double plane,double y,double z){var xyz=mesh.triangles();for(int i=0;i<xyz.length;i+=9){var p=new Vec3[3];boolean face=true;for(int k=0;k<3;k++){int n=i+3*k;p[k]=f.transformPoint(new Vec3(xyz[n],xyz[n+1],xyz[n+2]));face&=Math.abs(p[k].x-plane)<=CONTACT_COMPRESSION;}if(!face)continue;double det=(p[1].z-p[2].z)*(p[0].y-p[2].y)+(p[2].y-p[1].y)*(p[0].z-p[2].z);if(Math.abs(det)<1e-12)continue;double a=((p[1].z-p[2].z)*(y-p[2].y)+(p[2].y-p[1].y)*(z-p[2].z))/det,b=((p[2].z-p[0].z)*(y-p[2].y)+(p[0].y-p[2].y)*(z-p[2].z))/det;if(a>=-1e-7&&b>=-1e-7&&a+b<=1+1e-7)return true;}return false;}

    public record BearingFaces(int side,int faces,double area,double maximumSeparation,double maximumCompression,double minimumNormalAgreement){public boolean bears(){return faces>=3&&area>=.0025&&maximumSeparation<=CONTACT_COMPRESSION&&maximumCompression<=CONTACT_COMPRESSION&&minimumNormalAgreement>=.999;}}

    private record Triangle(Vec3 a,Vec3 b,Vec3 c,Vec3 normal,double area){}

    private static List<Triangle> cylinderFaces(NervFootGuideRigR52.Draw d,boolean bore){var out=new ArrayList<Triangle>();var xyz=d.part().mesh().triangles();for(int n=0;n<xyz.length;n+=9){var p=new Vec3[3];boolean face=true;for(int k=0;k<3;k++){int i=n+3*k;var local=new Vec3(xyz[i],xyz[i+1],xyz[i+2]);face&=Math.abs(Math.hypot(local.y,local.z)-.18)<.000002&&(!bore||local.y<=.000002);p[k]=d.frame().transformPoint(local);}if(!face)continue;var cross=p[1].subtract(p[0]).cross(p[2].subtract(p[0]));double area=cross.length()*.5;if(area<1e-10)continue;out.add(new Triangle(p[0],p[1],p[2],cross.normalize(),area));}return List.copyOf(out);}

    /** Only the selected lower annular wall and matching original cylinder

     * faces participate in this 0.2mm finite contact/compression allowance. */

    public static List<BearingFaces> bearingFaces(FootSupportFrameR52.Binding binding,RigidTransform root,Vec3 up)throws IOException {

        var draws=NervFootGuideRigR52.draws(binding,root,1,up);var result=new ArrayList<BearingFaces>();

        for(int side:new int[]{-1,1}){var rotor=draws.stream().filter(d->d.part().name().equals("foot_guide_rotor_"+side)).findFirst().orElseThrow();var stator=draws.stream().filter(d->d.part().name().equals("foot_guide_stator_"+side)).findFirst().orElseThrow();var solid=cylinderFaces(rotor,false);int faces=0;double area=0,separation=0,compression=0,agreement=1;

            for(var hole:cylinderFaces(stator,true)){var point=hole.a().add(hole.b()).add(hole.c()).scale(1D/3);double best=Double.POSITIVE_INFINITY;Triangle matched=null;Vec3 nearest=null;for(var t:solid){var q=NervAirCradleContactsR52.closest(point,t.a(),t.b(),t.c());double distance=q.distanceToSqr(point);if(distance<best){best=distance;matched=t;nearest=q;}}if(matched==null)continue;var local=stator.frame().inverse().transformPoint(point);var toward=stator.frame().transformVector(new Vec3(0,-local.y,-local.z)).normalize();double signed=nearest.subtract(point).dot(toward);compression=Math.max(compression,Math.max(0,-signed));if(Math.sqrt(best)>CONTACT_COMPRESSION)continue;double normal=Math.abs(hole.normal().dot(matched.normal()));if(normal<.999)continue;faces++;area+=hole.area();separation=Math.max(separation,Math.sqrt(best));agreement=Math.min(agreement,normal);}

            result.add(new BearingFaces(side,faces,area,separation,compression,agreement));

        }return List.copyOf(result);

    }

    private static boolean planarAxleJoint(Piece p,NervOriginalCarrierR52.Part original,Spec s,Sample at)throws IOException {

        if(!p.name().startsWith("dock_axis/")||!original.name().startsWith("guide/foot_guide_rotor_"))return false;int side=p.name().endsWith("/-1")?-1:1;if(!original.name().endsWith("_"+side))return false;var frame=axisFrame(s,at);double plane=(double)(float)14.84;for(var pair:List.of(new Object[]{p.mesh(),p.frame()},new Object[]{original.mesh(),original.frame()})){var mesh=(NervRigidMeshSweepR52)pair[0];var f=relative(frame,(RigidTransform)pair[1]);var xyz=mesh.triangles();for(int i=0;i<xyz.length;i+=3){double x=side*f.transformPoint(new Vec3(xyz[i],xyz[i+1],xyz[i+2])).x;if(mesh==p.mesh()?x<plane-CONTACT_COMPRESSION:x>plane+CONTACT_COMPRESSION)return false;}}return true;

    }

    private static NervFootGuideRigR52.Draw drawFor(Spec s,Sample at,NervOriginalCarrierR52.Part part)throws IOException {if(!part.name().startsWith("guide/"))return null;for(var d:NervFootGuideRigR52.draws(s.binding(),root(s,at),1,guideUp(s,at)))if(part.name().equals("guide/"+d.part().name()))return d;return null;}

    private static boolean padJoint(Piece p,NervOriginalCarrierR52.Part hardware,Spec s,Sample at)throws IOException {var d=drawFor(s,at,hardware);return d!=null&&NervFootGuideRigR52.namedGuideContactR52(d,d,new NervServiceFootDriveR52.Piece(p.name(),p.rgb(),p.mesh(),p.frame(),p.moving()));}

    private static NervFootGuideRigR52.Draw actualGuideDraw(NervOriginalCarrierR52.Part p){if(!p.name().startsWith("guide/"))return null;var xyz=p.mesh().triangles();var rgb=new double[xyz.length*2];for(int i=0,j=0;i<xyz.length;i+=3,j+=6){rgb[j]=xyz[i];rgb[j+1]=xyz[i+1];rgb[j+2]=xyz[i+2];}String name=p.name().substring(6);return new NervFootGuideRigR52.Draw(new NervFootGuideRigR52.Part(name,name.startsWith("foot_guide_rotor_")?"rotor":"stator",rgb,p.mesh()),p.frame());}

    /** Exact inverse rows of the actual double source matrix, avoiding a

     *14.75m float quaternion projection inventing several microns. */

    private static Vec3 inverseRow(RigidTransform frame,boolean x){var a=frame.transformVector(new Vec3(1,0,0));var b=frame.transformVector(new Vec3(0,1,0));var c=frame.transformVector(new Vec3(0,0,1));double det=a.dot(b.cross(c));return (x?b.cross(c):c.cross(a)).scale(1/det);}

    private static boolean stablePadPlaneContact(NervFootGuideRigR52.Draw draw,Piece guide){if(!draw.part().name().startsWith("foot_guide_pad_")||!guide.name().endsWith("/0"))return false;var bounds=guide.mesh().bounds();boolean inner=draw.part().name().endsWith("_inner");int side=draw.part().name().split("_")[3].equals("-1")?-1:1;double plane=side<0?-bounds.maxX:bounds.minX,opposite=side<0?-bounds.minX:bounds.maxX;var row=inverseRow(guide.frame(),true);var xyz=draw.part().mesh().triangles();for(int i=0;i<xyz.length;i+=3){double x=side*row.dot(draw.frame().transformPoint(new Vec3(xyz[i],xyz[i+1],xyz[i+2])).subtract(guide.frame().translation()));if(inner?x>plane+.000003:x<opposite-.000003)return false;}return true;}


    /** Named contact for normal entry/exit/stationary empty-carrier proofs.

     * Every original pad vertex remains in the real finite T-head's exterior

     * half space at both actual samples; no station part is ignored. */

    public static boolean namedStationContactR52(NervOriginalCarrierR52.Part from,NervOriginalCarrierR52.Part to,ViewSpec view,StationPose before,StationPose after,Piece piece)throws IOException {

        boolean bridge=piece.name().startsWith("service_bridge/dock/")&&piece.name().endsWith("/0")&&from.name().startsWith("guide/foot_guide_pad_");boolean axle=piece.name().startsWith("dock_axis/")&&from.name().startsWith("guide/foot_guide_rotor_");if(!bridge&&!axle||!from.name().equals(to.name()))return false;var a=actualGuideDraw(from);var b=from==to?a:actualGuideDraw(to);if(a==null||b==null)return false;Piece end=before.equals(after)?piece:null;if(end==null)for(var p:pieces(view,after))if(p.name().equals(piece.name())){end=p;break;}if(end==null)return false;

        if(piece.name().startsWith("service_bridge/dock/")&&piece.name().endsWith("/0"))return stablePadPlaneContact(a,piece)&&stablePadPlaneContact(b,end);

        if(!piece.name().startsWith("dock_axis/")||!a.part().name().startsWith("foot_guide_rotor_"))return false;int side=piece.name().endsWith("/-1")?-1:1;if(!a.part().name().endsWith("_"+side))return false;

        for(int index=0;index<2;index++){var pose=index==0?before:after;var ref=axisFrame(view,pose.turn());var shaft=index==0?piece:end;var rotor=index==0?from:to;double plane=(double)(float)14.84;for(var pair:List.of(new Object[]{shaft.mesh(),shaft.frame(),true},new Object[]{rotor.mesh(),rotor.frame(),false})){var mesh=(NervRigidMeshSweepR52)pair[0];var f=relative(ref,(RigidTransform)pair[1]);boolean outer=(Boolean)pair[2];var xyz=mesh.triangles();for(int n=0;n<xyz.length;n+=3){double x=side*f.transformPoint(new Vec3(xyz[n],xyz[n+1],xyz[n+2])).x;if(outer?x<plane-CONTACT_COMPRESSION:x>plane+CONTACT_COMPRESSION)return false;}}}

        return true;

    }

    /** Only a whole real short T-guide remains beyond a real fixed rail's

     * terminal plane. This is an exterior test, not a support receipt. */

    public static boolean namedFixedEndContactR52(Piece from,Piece to,NervServiceFootDriveR52.Piece fixed){

        if(!from.name().startsWith("service_bridge/dock/")||!fixed.name().startsWith("ground_rail/")||!from.frame().rotation().equals(to.frame().rotation()))return false;

        var bounds=fixed.mesh().bounds();boolean lower=true,upper=true;for(var p:List.of(from,to)){var row=inverseRow(fixed.frame(),false);var xyz=p.mesh().triangles();for(int n=0;n<xyz.length;n+=3){double y=row.dot(p.frame().transformPoint(new Vec3(xyz[n],xyz[n+1],xyz[n+2])).subtract(fixed.frame().translation()));lower&=y<=bounds.minY+.000003;upper&=y>=bounds.maxY-.000003;}}return lower||upper;

    }

    private static boolean monotone(Sample a,Sample b){return a.stage()==b.stage()?b.fraction()>=a.fraction()&&b.fraction()-a.fraction()<=.051:a.fraction()==1&&b.fraction()==0&&b.stage().ordinal()==a.stage().ordinal()+1;}

    private static AcceptedDockStep checkStep(ServerLevel l,NervCarrierPlatformEntity e,Spec s,Sample from,Sample to,Set<UUID> own)throws IOException {

        if(!s.directory().installed()||e.getUnitVariant()!=variant(s)||!NervOriginalCarrierR52.declared(e)||NervOriginalCarrierR52.progress(e,1)!=1||!own.contains(e.getUUID())||!monotone(from,to)||!NervAirTransportManifestR52.same(NervOriginalCarrierR52.actualRoot(e,1),root(s,from))||NervOriginalCarrierR52.guideUp(e).distanceTo(guideUp(s,from))>1e-6||!foundationsBear(l,s))return null;

        var station=NervFootGuideStationR52.controller(l,s);if(station==null||!NervFootGuideStationR52.currentPose(station).equals(stationPose(s,from))||!snapshot(NervFootGuideStationR52.view(station)).equals(snapshot(view(s))))return null;var owned=new HashSet<>(own);owned.add(station.getUUID());var saved=e.originalCarrierStateR52().getCompound("DockR52");if(saved.isEmpty()){if(from.stage()!=Stage.COUPLE||from.fraction()!=0)return null;}else if(!saved.getString("Source").equals(SOURCE_SHA)||!saved.getString("Leg").equals(s.leg().id())||!saved.getString("Stage").equals(from.stage().name())||saved.getDouble("Fraction")!=from.fraction()||saved.getDouble("FoundationTop")!=s.foundationTop())return null;

        if(coupled(from)==1&&!finiteAxleContacts(s,from)||coupled(to)==1&&!finiteAxleContacts(s,to)||bearingFaces(s.binding(),root(s,from),guideUp(s,from)).stream().anyMatch(f->!f.bears())||bearingFaces(s.binding(),root(s,to),guideUp(s,to)).stream().anyMatch(f->!f.bears())||saddleSupportsR52(view(s),stationPose(s,from)).stream().anyMatch(f->!f.bears())||saddleSupportsR52(view(s),stationPose(s,to)).stream().anyMatch(f->!f.bears()))return null;var boxes=new ArrayList<AABB>();

        var body=new ArrayList<NervRigidMeshSweepR52>();if(e.originalCarrierStateR52().getBoolean("Attached")){var actor=l.getEntity(e.originalCarrierStateR52().getUUID("OriginalEva"));if(!(actor instanceof EvaUnit01Entity eva)||!EvaMechanicalFrameR52.active(eva)||!NervAirTransportManifestR52.same(EvaMechanicalFrameR52.frame(eva,1),root(s,from)))return null;for(var p:EvaMechanicalFrameR52.capturedGeometry(eva).parts())body.add(new NervRigidMeshSweepR52(p.triangles()));}

        DirectoryTrajectoryR52 curve=from.stage()==Stage.TURN&&to.stage()==Stage.TURN?new DirectoryTrajectoryR52(s.directory(),s.leg(),s.binding(),from.fraction(),to.fraction()):null;double delta=from.stage()==to.stage()?Math.abs(to.fraction()-from.fraction()):0;int divisions=curve==null?stationSweepDivisionsR52(view(s),delta):Math.max(16,curve.divisions(80,.003));for(int k=0;k<divisions;k++){var a=between(from,to,k/(double)divisions);var b=between(from,to,(k+1)/(double)divisions);var A=pieces(s,a);var B=pieces(s,b);var ca=new ArrayList<>(NervOriginalCarrierR52.partsAtR52(variant(s),root(s,a),1,guideUp(s,a)));var cb=new ArrayList<>(NervOriginalCarrierR52.partsAtR52(variant(s),root(s,b),1,guideUp(s,b)));for(int n=0;n<body.size();n++){ca.add(new NervOriginalCarrierR52.Part("original_body/"+n,NervOriginalCarrierR52.Role.STRUCTURE,body.get(n),root(s,a)));cb.add(new NervOriginalCarrierR52.Part("original_body/"+n,NervOriginalCarrierR52.Role.STRUCTURE,body.get(n),root(s,b)));}double error=curve==null?stationSweepErrorR52(view(s),delta,divisions):curve.error(80,divisions);

            // The complete original carrier and captured body are swept as

            // well as the station; a dock proof never grants a free turn.

            for(int n=0;n<ca.size();n++){var h=ca.get(n);var j=cb.get(n);var bound=h.mesh().envelope(h.frame(),j.frame()).inflate(error);boxes.add(bound);if(!EntryPlugEjectionR48.loaded(l,bound))return null;for(var shape:l.getBlockCollisions(e,bound))for(var obstacle:shape.toAabbs())if(h.mesh().intersects(h.frame(),j.frame(),obstacle.inflate(error),.001))return null;for(var fixed:NervFixedFootGuidesR52.actualPieces(l,bound)){var fp=new Piece(fixed.name(),fixed.mesh(),fixed.rgb(),fixed.frame(),false);if(padJoint(fp,h,s,a)&&padJoint(fp,j,s,b))continue;if(h.mesh().intersects(h.frame(),j.frame(),fixed.mesh(),fixed.frame(),fixed.frame(),.001,new Vec3(error,error,error)))return null;}for(var actor:l.getEntities((Entity)null,bound.inflate(100),x->!owned.contains(x.getUUID())&&x.isAlive()&&(x instanceof LivingEntity||x.canBeCollidedWith()||x instanceof NervCarrierPlatformEntity||x instanceof NervSiloDoorEntity||x instanceof NervHangarDoorEntity))){var actual=NervFlightProofR52.actualObstacleMeshes(actor);if(actual==null)return null;if(actual.isEmpty()){if(h.mesh().intersects(h.frame(),j.frame(),actor.getBoundingBox().inflate(error),.001))return null;}else for(var mesh:actual)if(h.mesh().intersects(h.frame(),j.frame(),mesh.mesh(),mesh.frame(),mesh.endFrame(),.001,new Vec3(error,error,error)))return null;}}

            for(int i=0;i<A.size();i++){var p=A.get(i);var q=B.get(i);if(!p.name().equals(q.name()))return null;var box=p.mesh().envelope(p.frame(),q.frame()).inflate(error);boxes.add(box);if(!EntryPlugEjectionR48.loaded(l,box))return null;

                for(var shape:l.getBlockCollisions(e,box))for(var obstacle:shape.toAabbs()){if(p.name().startsWith("dock_foundation/")&&p.mesh().envelope(p.frame(),p.frame()).minY>=obstacle.maxY-.000003&&q.mesh().envelope(q.frame(),q.frame()).minY>=obstacle.maxY-.000003)continue;if(p.mesh().intersects(p.frame(),q.frame(),obstacle.inflate(error),.001))return null;}

                for(var actor:l.getEntities((Entity)null,box.inflate(100),x->!owned.contains(x.getUUID())&&x.isAlive()&&(x instanceof LivingEntity||x.canBeCollidedWith()||x instanceof NervCarrierPlatformEntity||x instanceof NervSiloDoorEntity||x instanceof NervHangarDoorEntity))){var actual=NervFlightProofR52.actualObstacleMeshes(actor);if(actual==null)return null;if(actual.isEmpty()){if(p.mesh().intersects(p.frame(),q.frame(),actor.getBoundingBox().inflate(error),.001))return null;}else for(var mesh:actual)if(p.mesh().intersects(p.frame(),q.frame(),mesh.mesh(),mesh.frame(),mesh.endFrame(),.001,new Vec3(error,error,error)))return null;}

                for(var fixed:NervFixedFootGuidesR52.actualPieces(l,box)){if(namedFixedEndContactR52(p,q,fixed))continue;if(p.mesh().intersects(p.frame(),q.frame(),fixed.mesh(),fixed.frame(),fixed.frame(),.001,new Vec3(error,error,error)))return null;}for(int n=0;n<ca.size();n++){var h=ca.get(n);var j=cb.get(n);if(planarAxleJoint(p,h,s,a)&&planarAxleJoint(q,j,s,b)||padJoint(p,h,s,a)&&padJoint(q,j,s,b))continue;if(p.mesh().intersects(p.frame(),q.frame(),h.mesh(),h.frame(),j.frame(),.001,new Vec3(error,error,error)))return null;}

            }

        }

        return new AcceptedDockStep(l,e,station,s,from,to,boxes);

    }

    private static Sample between(Sample a,Sample b,double t){if(a.stage()!=b.stage())return t<1?a:b;return new Sample(a.stage(),a.fraction()+(b.fraction()-a.fraction())*t);}

    private NervFootGuideDockR52(){}

}

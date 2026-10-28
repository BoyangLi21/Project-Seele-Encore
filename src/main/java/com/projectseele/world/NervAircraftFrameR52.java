package com.projectseele.world;

import com.projectseele.entity.UNTransportEntity;
import com.projectseele.world.NervAirTransportManifestR52.*;
import java.util.*;
import net.minecraft.nbt.*;
import net.minecraft.network.syncher.*;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;

/** Synchronized actual aircraft/rig sample. The renderer consumes this same
 * checked sample instead of reconstructing a plane from the EVA root. */
public final class NervAircraftFrameR52
{
    private static final EntityDataAccessor<CompoundTag> DATA=SynchedEntityData.defineId(UNTransportEntity.class,EntityDataSerializers.COMPOUND_TAG);
    private static final Map<String,NervAirframeGeometryR52> CLIENT_GEOMETRY=new HashMap<>();
    private static final Map<UNTransportEntity,ClientFrameR54> CLIENT_FRAMES=new WeakHashMap<>();
    private static final class ClientFrameR54
    {
        final com.projectseele.entity.MechanicalVisualClockR54 clock=new com.projectseele.entity.MechanicalVisualClockR54();
        Frame from,to;CompoundTag received;long revision;
        List<Vec3> fromAnchors=List.of(),toAnchors=List.of(),fromAxes=List.of(),toAxes=List.of();
        double fromRotor,toRotor;
        void receive(CompoundTag data,long now)
        {
            if(received==data)return;
            Frame target=decode(data.getCompound("Current"));
            var anchors=readPoints(data,"Anchors");var axes=readPoints(data,"JawAxes");
            if(target.equals(to)&&anchors.equals(toAnchors)&&axes.equals(toAxes)&&data.getDouble("RotorCurrent")==toRotor)
            {received=data;return;}
            Frame previous=to==null?target:sample(now);
            if(previous.cargo()==null&&target.cargo()!=null)previous=new Frame(previous.plane(),target.cargo(),previous.rig());
            if(previous.cargo()!=null&&target.cargo()==null)previous=new Frame(previous.plane(),null,previous.rig());
            fromAnchors=to==null?anchors:blendPoints(fromAnchors,toAnchors,clock.fraction(now),false);
            fromAxes=to==null?axes:blendPoints(fromAxes,toAxes,clock.fraction(now),true);
            fromRotor=to==null?data.getDouble("RotorCurrent"):rotor(now);
            toAnchors=anchors;toAxes=axes;toRotor=data.getDouble("RotorCurrent");
            from=previous;to=target;received=data;clock.receive(++revision,now);
        }
        Frame sample(long now){return from.interpolate(to,clock.fraction(now));}
        List<Vec3> anchors(long now){return blendPoints(fromAnchors,toAnchors,clock.fraction(now),false);}
        List<Vec3> axes(long now){return blendPoints(fromAxes,toAxes,clock.fraction(now),true);}
        double rotor(long now){return fromRotor+(toRotor-fromRotor)*clock.fraction(now);}
    }
    public static boolean bootstrap(){return true;}
    public static void define(SynchedEntityData data){data.define(DATA,new CompoundTag());}
    public static boolean active(UNTransportEntity p){return p.getEntityData().get(DATA).getBoolean("Active");}
    public static boolean contextMatches(UNTransportEntity p,NervAirTransportManifestR52 manifest)
    {
        var data=p.getEntityData().get(DATA);if(!active(p)||!data.getString("Manifest").equals(manifest.fingerprint())||data.getLong("Epoch")!=manifest.directory().epoch()||!p.isNerv()||p.groundCart()||!net.minecraft.core.registries.BuiltInRegistries.ENTITY_TYPE.getKey(p.getType()).toString().equals("projectseele:un_transport")||manifest.aircraft().values().stream().noneMatch(a->a.entity().equals(p.getUUID())&&a.serial()==p.serial()))return false;
        var sources=data.getCompound("Sources");if(!sources.getAllKeys().equals(manifest.meshSources().keySet()))return false;for(var e:manifest.meshSources().entrySet())if(!sources.getString(e.getKey()).equals(e.getValue()))return false;return true;
    }
    public static void save(UNTransportEntity p,CompoundTag data){data.put("R52AircraftSample",p.getEntityData().get(DATA).copy());}
    public static void load(UNTransportEntity p,CompoundTag data){p.getEntityData().set(DATA,data.getCompound("R52AircraftSample").copy());}
    public static RigidTransform actual(UNTransportEntity p)
    {if(!active(p))return RigidTransform.of(p.position(),new Quaternionf().rotationY((float)Math.toRadians(-p.getYRot())));var frame=decodeRigid(p.getEntityData().get(DATA).getCompound("Current").getCompound("Plane"));if(!p.level().isClientSide&&(p.position().distanceToSqr(frame.translation())>1e-10||!NervAirTransportManifestR52.same(RigidTransform.of(p.position(),new Quaternionf().rotationY((float)Math.toRadians(-p.getYRot()))),frame)))throw new IllegalStateException("Actual original aircraft differs from the checked synchronized frame");return frame;}
    public static boolean bind(UNTransportEntity p,NervAirTransportManifestR52 manifest,Aircraft aircraft)
    {
        if(p.level().isClientSide||!p.getUUID().equals(aircraft.entity())||p.serial()!=aircraft.serial()||!p.isNerv()||p.groundCart()||p.carrying()||!net.minecraft.core.registries.BuiltInRegistries.ENTITY_TYPE.getKey(p.getType()).toString().equals("projectseele:un_transport"))return false;
        if(active(p))return contextMatches(p,manifest);
        var stand=manifest.node(aircraft.stand()).frame();if(!NervAirTransportManifestR52.same(actual(p),stand.plane())||p.hoistDistance()!=stand.rig().hoist())return false;
        var tag=p.getEntityData().get(DATA).copy();tag.putBoolean("Active",true);tag.putString("Manifest",manifest.fingerprint());tag.putLong("Epoch",manifest.directory().epoch());tag.putLong("At",p.level().getGameTime());tag.putDouble("RotorPrevious",p.level().getGameTime()%3600);tag.putDouble("RotorCurrent",p.level().getGameTime()%3600);tag.put("Previous",encode(stand,tag.getCompound("Previous")));tag.put("Current",encode(stand,tag.getCompound("Current")));var hashes=new CompoundTag();manifest.meshSources().forEach(hashes::putString);tag.put("Sources",hashes);tag.put("Anchors",new ListTag());p.getEntityData().set(DATA,tag);return true;
    }
    public static boolean apply(UNTransportEntity p,NervFlightProofR52.CheckedFlightStep proof)
    {
        if(!(p.level() instanceof net.minecraft.server.level.ServerLevel l)||!active(p)||!proof.aircraft().equals(p.getUUID())||!proof.current(l)||!p.getEntityData().get(DATA).getString("Manifest").equals(proof.manifestFingerprint()))return false;
        var previousState=p.getEntityData().get(DATA).copy();previousState.remove("RecoveryAnchorBlendR52");p.getEntityData().set(DATA,previousState);
        var data=p.getEntityData().get(DATA).copy();boolean referenceOnly=proof.from().cargo()!=null&&proof.to().cargo()==null&&proof.from().rig().deployment()==0&&proof.from().rig().equals(proof.to().rig())&&proof.rotorFrom()==proof.rotorTo()&&NervAirTransportManifestR52.same(proof.from().plane(),proof.to().plane());if(!referenceOnly){data.putDouble("RotorPrevious",proof.rotorFrom());data.putDouble("RotorCurrent",proof.rotorTo());data.put("Previous",encode(proof.from(),data.getCompound("Previous")));data.putLong("At",l.getGameTime());}else data.put("DetachedCargoReferenceR52",data.getCompound("Current").getCompound("Cargo").copy());data.put("Current",encode(proof.to(),data.getCompound("Current")));var anchors=new ListTag();if(proof.preview()!=null){for(var a:proof.preview().anchors())anchors.add(point(a));data.put("Anchors",anchors);var axes=new ListTag();for(var a:proof.preview().jawAxes())axes.add(point(a));data.put("JawAxes",axes);}p.getEntityData().set(DATA,data);
        var to=proof.to();p.setPos(to.plane().translation());var f=to.plane().transformVector(new Vec3(0,0,1));p.setYRot((float)-Math.toDegrees(Math.atan2(f.x,f.z)));p.setXRot(0);p.setDeltaMovement(Vec3.ZERO);p.setHoistDistance(to.rig().hoist());return true;
    }
    public static boolean applyRecoveryStepR52(UNTransportEntity p,NervHullGroundRecoveryR52.AcceptedRecoveryStep proof)
    {
        if(!(p.level() instanceof net.minecraft.server.level.ServerLevel level)||!active(p)||!proof.aircraft().equals(p.getUUID())||!proof.cargoCommitted(level))return false;
        var data=p.getEntityData().get(DATA).copy();data.put("PreviousAnchorsR52",data.getList("Anchors",Tag.TAG_COMPOUND).copy());data.put("PreviousJawAxesR52",data.getList("JawAxes",Tag.TAG_COMPOUND).copy());data.putBoolean("RecoveryAnchorBlendR52",true);
        data.put("Previous",encode(proof.from(),data.getCompound("Previous")));data.put("Current",encode(proof.to(),data.getCompound("Current")));data.putLong("At",level.getGameTime());data.putDouble("RotorPrevious",proof.rotorFrom());data.putDouble("RotorCurrent",proof.rotorTo());
        var anchors=new ListTag();proof.anchors().forEach(a->anchors.add(point(a)));data.put("Anchors",anchors);var axes=new ListTag();proof.jawAxes().forEach(a->axes.add(point(a)));data.put("JawAxes",axes);p.getEntityData().set(DATA,data);p.setDeltaMovement(Vec3.ZERO);return true;
    }
    private static List<Vec3> readPoints(CompoundTag data,String key)
    {
        var points=new ArrayList<Vec3>();for(var point:data.getList(key,Tag.TAG_COMPOUND))points.add(readPoint((CompoundTag)point));return List.copyOf(points);
    }
    private static List<Vec3> blendPoints(List<Vec3> from,List<Vec3> to,double fraction,boolean axis)
    {
        if(from.size()!=to.size()||fraction>=1)return to;
        var points=new ArrayList<Vec3>(to.size());
        for(int i=0;i<to.size();i++){var point=from.get(i).lerp(to.get(i),fraction);points.add(axis?point.normalize():point);}return points;
    }
    private static ClientFrameR54 clientFrame(UNTransportEntity p,long now)
    {
        var visual=CLIENT_FRAMES.computeIfAbsent(p,ignored->new ClientFrameR54());
        visual.receive(p.getEntityData().get(DATA),now);return visual;
    }
    public static Frame frame(UNTransportEntity p,float partial)
    {
        if(!p.level().isClientSide)return decode(p.getEntityData().get(DATA).getCompound("Current"));
        long now=com.projectseele.entity.MechanicalVisualClockR54.presentationTime(p.level().getGameTime(),partial);
        return clientFrame(p,now).sample(now);
    }
    public static RigidTransform renderedCargoR54(com.projectseele.entity.EvaUnit01Entity eva,float partial)
    {
        for(var plane:eva.level().getEntitiesOfClass(UNTransportEntity.class,eva.getBoundingBox().inflate(192),
                p->p.carrying()&&p.cargoEntityId()==eva.getId()&&active(p)))
            return frame(plane,partial).cargo();
        return null;
    }
    public static NervAirframeGeometryR52 renderGeometry(UNTransportEntity p)
    {
        var data=p.getEntityData().get(DATA);String manifest=data.getString("Manifest");var geometry=CLIENT_GEOMETRY.get(manifest);
        if(geometry==null){var hashes=new HashMap<String,String>();var sources=data.getCompound("Sources");for(String k:sources.getAllKeys())hashes.put(k,sources.getString(k));try{geometry=NervAirframeGeometryR52.loadClasspath(hashes);}catch(java.io.IOException|IllegalStateException missing){throw new IllegalStateException("Actual checked aircraft draw source absent",missing);}CLIENT_GEOMETRY.put(manifest,geometry);}
        return geometry;
    }
    public static double renderRotorClock(UNTransportEntity p,float partial)
    {long now=com.projectseele.entity.MechanicalVisualClockR54.presentationTime(p.level().getGameTime(),partial);return clientFrame(p,now).rotor(now);}
    public static List<NervAirframeGeometryR52.Part> renderCradleParts(UNTransportEntity p,float partial)
    {long now=com.projectseele.entity.MechanicalVisualClockR54.presentationTime(p.level().getGameTime(),partial);var visual=clientFrame(p,now);return renderGeometry(p).cradleParts(visual.sample(now),visual.anchors(now),visual.axes(now),false);}
    public static List<NervAirframeGeometryR52.Part> renderParts(UNTransportEntity p,float partial)
    {long now=com.projectseele.entity.MechanicalVisualClockR54.presentationTime(p.level().getGameTime(),partial);var visual=clientFrame(p,now);return renderGeometry(p).parts(visual.sample(now),visual.anchors(now),visual.axes(now),visual.rotor(now));}
    public static double rotorClock(UNTransportEntity p){return p.getEntityData().get(DATA).getDouble("RotorCurrent");}
    public static long sampledAt(UNTransportEntity p){return p.getEntityData().get(DATA).getLong("At");}
    public static List<Vec3> jawAxes(UNTransportEntity p){var list=new ArrayList<Vec3>();for(var a:p.getEntityData().get(DATA).getList("JawAxes",Tag.TAG_COMPOUND))list.add(readPoint((CompoundTag)a));return List.copyOf(list);}
    public static List<Vec3> anchors(UNTransportEntity p){var list=new ArrayList<Vec3>();for(var a:p.getEntityData().get(DATA).getList("Anchors",Tag.TAG_COMPOUND))list.add(readPoint((CompoundTag)a));return List.copyOf(list);}
    public static CompoundTag encodeRigid(RigidTransform f){return NervAircraftFrameCodecR52.encodeRigid(f);}
    public static CompoundTag encodeRigid(RigidTransform f,CompoundTag prior){return NervAircraftFrameCodecR52.encodeRigid(f,prior);}
    public static RigidTransform decodeRigid(CompoundTag t){return NervAircraftFrameCodecR52.decodeRigid(t);}
    public static CompoundTag encode(Frame f){return NervAircraftFrameCodecR52.encode(f);}
    public static CompoundTag encode(Frame f,CompoundTag prior){return NervAircraftFrameCodecR52.encode(f,prior);}
    public static void putFrame(CompoundTag data,String key,Frame f){data.put(key,encode(f,data.getCompound(key)));}
    public static Frame decode(CompoundTag t){return NervAircraftFrameCodecR52.decode(t);}
    private static CompoundTag point(Vec3 p){var t=new CompoundTag();t.putDouble("X",p.x);t.putDouble("Y",p.y);t.putDouble("Z",p.z);return t;}
    private static Vec3 readPoint(CompoundTag t){return new Vec3(t.getDouble("X"),t.getDouble("Y"),t.getDouble("Z"));}
    private NervAircraftFrameR52(){}
}

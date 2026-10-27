package com.projectseele.world;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import com.google.gson.*;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;
import com.projectseele.world.NervAirTransportManifestR52.*;

/** Actual selected resource geometry; no installed world/native clearance claim. */
public final class NervAirframeGeometryR52Test
{
    private static int checks;
    private static void check(boolean b,String text){checks++;if(!b)throw new AssertionError(text);}
    private static String sha(byte[] b)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(b));}
    private static void contactSelectionChecks()
    {
        var parts=new ArrayList<EvaOriginalMeshGeometryR52.Part>();var low=new ArrayList<Vec3>();var high=new ArrayList<Vec3>();
        var names=List.of("arm_l","arm_r","leg_l","leg_r","shin_l","shin_r");
        for(int i=0;i<6;i++)
        {
            double x=i%2==0?-10:10,y=i%2==0?0:.4,z=i/2*8;
            double[] triangles={x-1,y,z-1,x+1,y,z-1,x,y,z+1,
                    x-1,y+4,z-1,x+1,y+4,z-1,x,y+4,z+1};
            parts.add(new EvaOriginalMeshGeometryR52.Part(names.get(i),"synthetic/limb","synthetic",
                    triangles,new AABB(x-1,y,z-1,x+1,y+4,z+1)));
            low.add(new Vec3(x,y+.1,z));high.add(new Vec3(x,y+4.1,z));
        }
        var body=new EvaOriginalMeshGeometryR52.Geometry(2,"synthetic",parts);
        var rescued=NervAirCradleContactsR52.evaluate(body,low);
        var suspended=NervAirCradleContactsR52.evaluate(body,high);
        check(rescued.size()==6&&suspended.size()==6,"Contact selection retains all six paired original limb grips");
        for(int i=0;i<6;i++)
        {
            check(rescued.get(i).skin().y>=4,"Near-floor tilted jaws select an actual higher skin triangle");
            check(Math.abs(rescued.get(i).skin().distanceTo(rescued.get(i).centre())-.85)<1e-9,
                    "Selected jaw still touches actual skin at its original radius");
            check(suspended.get(i).skin().distanceToSqr(new Vec3(high.get(i).x,high.get(i).y-.1,high.get(i).z))<1e-18,
                    "A normal suspended contact keeps its nearest actual surface");
            if(i%2==0)check(rescued.get(i).axis().equals(rescued.get(i+1).axis()),"Opposed original jaws retain the same paired axis");
        }
    }

    public static void main(String[] args)throws Exception
    {
        var assets=Path.of(args.length==0?"src/main/resources/assets/projectseele":args[0]);var hashes=new HashMap<String,String>();for(String path:List.of("mesh/tv_facilities_r16.json","mesh/air_cradle_r31.json"))hashes.put(path,sha(Files.readAllBytes(assets.resolve(path))));
        var source=NervAirframeGeometryR52.load(path->Files.readAllBytes(assets.resolve(path)),hashes);var frame=new Frame(RigidTransform.identity(),null,new Rig(84,0,1));var parts=source.parts(frame,List.of(),0);check(parts.size()==5,"Actual stowed draw is the R16 body and four rotors; no phantom rods below apron");
        var body=new NervRigidMeshSweepR52(parts.get(0).xyz());var bounds=body.bounds();check(bounds.minX==-69&&bounds.minY==-11&&bounds.minZ==-56&&bounds.maxX==69&&bounds.maxY==19&&bounds.maxZ==58,"Selected R16 body exact raw bounds retained");
        var sweep=source.sweep(frame,frame,List.of(),0,1,.005);var corner=new AABB(68,17,56.8,68.5,17.5,57.3);check(bounds.intersects(corner),"Empty-wing-corner witness lies inside broad aircraft AABB");check(!sweep.intersects(corner),"Actual parts permit empty corner; whole AABB never acts as narrow collider");
        var support=new AABB(-70,-12,-57,70,-11,59);check(!sweep.intersects(support),"Actual original gear floor contact is bearing, not penetration");check(sweep.intersects(new AABB(-70,-12,-57,70,-10.998,59)),"A real two millimetre apron penetration is still blocked");
        var end=new Frame(new RigidTransform(new Vec3(10,0,0),0,0,0,1),null,new Rig(84,0,1));check(!source.sweep(frame,end,List.of(),0,1,.005).intersects(support),"Pure translation preserves exact gear bearing without phantom float inflation");
        var yawFrame=new Frame(RigidTransform.of(Vec3.ZERO,new Quaternionf().rotationY((float)Math.PI/2)),null,new Rig(84,0,1));check(!source.sweep(frame,yawFrame,List.of(),0,1,.005).intersects(support),"Yaw-only actual curves preserve exact Y bearing instead of isotropic pad below the floor");check(source.sweep(frame,yawFrame,List.of(),0,1,.005).intersects(new AABB(-100,-12,-100,100,-10.998,100)),"Yaw bearing proof still blocks real penetration");
        var raw=JsonParser.parseString(Files.readString(assets.resolve("mesh/tv_facilities_r16.json"))).getAsJsonObject().getAsJsonObject("parts").getAsJsonArray("un_transport_rotor_0");double[] xyz=new double[raw.size()/2];for(int i=0;i<raw.size()/6;i++)for(int a=0;a<3;a++)xyz[i*3+a]=raw.get(i*6+a).getAsFloat();var rotor=new NervRigidMeshSweepR52(xyz);var top=new Vec3(-29,4.8,-11);var a=RigidTransform.of(top,new Quaternionf());var b=RigidTransform.of(top,new Quaternionf().rotationY((float)Math.toRadians(47)));var mid=a.interpolate(b,.5);boolean continuous=false;
        for(int i=0;i<xyz.length;i+=3){var p=mid.transformPoint(new Vec3(xyz[i],xyz[i+1],xyz[i+2]));var probe=new AABB(p.add(-.0001,-.0001,-.0001),p.add(.0001,.0001,.0001));if(!rotor.intersects(a,a,probe,.005)&&!rotor.intersects(b,b,probe,.005)&&rotor.intersects(a,b,probe,.005)){continuous=true;break;}}
        check(continuous,"Actual rotor blade intermediate sweep detects an obstacle missed by both endpoint shapes");
        check(source.bearingPatches().size()==4&&source.bearingPatches().stream().allMatch(p->p.minY==-11&&Math.abs(p.getXsize()-2.6)<1e-5&&Math.abs(p.getZsize()-2.6)<1e-5),"Positive apron support uses all four actual 2.6m original gear soles");
        var anchors=List.of(new Vec3(-12,80,0),new Vec3(12,80,0),new Vec3(-10,40,0),new Vec3(10,40,0),new Vec3(-8,10,0),new Vec3(8,10,0));var cargo0=new Frame(RigidTransform.identity(),new RigidTransform(new Vec3(0,-112,0),0,0,0,1),new Rig(112,1,0));var cargo1=new Frame(RigidTransform.identity(),RigidTransform.of(new Vec3(0,-112,0),new Quaternionf().rotationY((float)Math.PI/2)),new Rig(112,1,0));var turn=source.sweep(cargo0,cargo1,anchors,0,1,.005);check(!turn.intersects(new AABB(40,-50,0,40.1,-49.9,.1)),"Full actual cargo/cradle turn subdivides its curve rather than inflating a distant empty corner by fifty metres");
        boolean cradleMiddle=false;var middle=cargo0.interpolate(cargo1,.5);for(var part:source.parts(middle,anchors,0))if(part.name().startsWith("jaw/")){var actual=part.xyz();for(int i=0;i<actual.length;i+=3){var q=new Vec3(actual[i],actual[i+1],actual[i+2]);var probe=new AABB(q.add(-.0001,-.0001,-.0001),q.add(.0001,.0001,.0001));if(!source.sweep(cargo0,cargo0,anchors,0,0,.005).intersects(probe)&&!source.sweep(cargo1,cargo1,anchors,0,0,.005).intersects(probe)&&turn.intersects(probe)){cradleMiddle=true;break;}}if(cradleMiddle)break;}check(cradleMiddle,"Actual cradle intermediate skin jaw is covered even when both endpoint shapes miss it");
        // Captured original 02 wreck: a tilted right-shin jaw penetrated
        // the actual floor by 4.31 mm despite its body remaining clear.
        var wreckStart=new Frame(new RigidTransform(new Vec3(72.50857491591684,193.025,297.5828188997969),0,0,0,1),
                new RigidTransform(new Vec3(72.50857491591684,81.025,297.5828188997969),0,.7149445F,0,.69918126F),new Rig(112,1,0));
        var wreckEnd=new Frame(new RigidTransform(new Vec3(72.50857491591684,241,297.5828188997969),0,0,0,1),
                new RigidTransform(new Vec3(72.50857491591684,129,297.5828188997969),0,.7149445F,0,.69918126F),wreckStart.rig());
        var oldAnchors=List.of(new Vec3(1.7092967015062879,16.608440867736032,1.8929138265355248),new Vec3(10.386497982895902,11.483047200960673,-8.83906054393236),new Vec3(-3.551125397464932,4.665647086564674,2.1846823043300674),new Vec3(3.7275973685224204,2.392297664946931,2.0022223900792664),new Vec3(-11.729083350690976,3.5510853912359437,-13.312982429946562),new Vec3(-4.275370874228277,0.948347461714868,6.748962413373394));var oldAxes=List.of(new Vec3(0.622135875234355,-0.3009630426518975,-0.7227504408190252),new Vec3(0.622135875234355,-0.3009630426518975,-0.7227504408190252),new Vec3(0.9356741562630441,-0.3508016407133167,-0.03810619600912378),new Vec3(0.9356741562630441,-0.3508016407133167,-0.03810619600912378),new Vec3(0.3097344187857256,-0.08155576563102362,0.9473189784395785),new Vec3(0.3097344187857256,-0.08155576563102362,0.9473189784395785));
        var safeAnchors=List.of(new Vec3(1.7092967015062879,16.608440867736032,1.8929138265355248),new Vec3(10.386497982895902,11.483047200960673,-8.83906054393236),new Vec3(-3.551125397464932,4.665647086564674,2.1846823043300674),new Vec3(3.7275973685224204,2.392297664946931,2.0022223900792664),new Vec3(-10.694925693737346,3.6456332050864777,-13.408699354208359),new Vec3(-4.01831317716515,2.783071142975788,6.655667102825849));var safeAxes=List.of(new Vec3(0.622135875234355,-0.3009630426518975,-0.7227504408190252),new Vec3(0.622135875234355,-0.3009630426518975,-0.7227504408190252),new Vec3(0.9356741562630441,-0.3508016407133167,-0.03810619600912378),new Vec3(0.9356741562630441,-0.3508016407133167,-0.03810619600912378),new Vec3(0.3154755134999008,-0.04075677730203359,0.9480580601872052),new Vec3(0.3154755134999008,-0.04075677730203359,0.9480580601872052));
        var jawStart=new Frame(wreckStart.plane(),wreckStart.cargo(),new Rig(112,.35F,.65F));
        var jawEnd=new Frame(wreckStart.plane(),wreckStart.cargo(),new Rig(112,.4F,.6F));
        double jawBound=NervAirframeGeometryR52.cradleChordEnclosureR53(jawStart,jawEnd,safeAnchors,safeAxes,"jaw/1/0");
        check(jawBound>=0&&jawBound<.1,"Observed fixed jaw deployment uses the analytic normalized-spread curvature, not 1.7m radial inflation");
        check(NervAirframeGeometryR52.cradleChordEnclosureR53(jawStart,jawStart,safeAnchors,safeAxes,"jaw/1/0")==0,"Unchanged fixed jaw has zero curvature error");
        for(var radius:Map.of("cross/1",.48,"strut/1/0",.48,"piston/1/0",.24,"collar/1/0",.60,"spine/1/0",.35).entrySet())
            check(Math.abs(NervAirframeGeometryR52.cradleChordEnclosureR53(jawStart,jawEnd,safeAnchors,safeAxes,radius.getKey())-jawBound-2*radius.getValue())<1e-12,
                    "Fixed-root "+radius.getKey()+" retains twice its actual radius for any cross-section basis switch");
        var rotatingJaw=new Frame(wreckStart.plane(),RigidTransform.of(wreckStart.cargo().translation(),new Quaternionf().rotationY(.1F)),jawEnd.rig());
        check(NervAirframeGeometryR52.cradleChordEnclosureR53(jawStart,rotatingJaw,safeAnchors,safeAxes,"jaw/1/0")==NervAirframeGeometryR52.CRADLE_RADIAL_ENCLOSURE_R53,"Cargo rotation cannot use fixed jaw translation proof");
        check(NervAirframeGeometryR52.cradleChordEnclosureR53(jawStart,jawEnd,safeAnchors,List.of(),"jaw/1/0")==NervAirframeGeometryR52.CRADLE_RADIAL_ENCLOSURE_R53,"Unbound jaw orientation retains the original strict enclosure");
        var collapsedAnchors=new ArrayList<>(safeAnchors);collapsedAnchors.set(2,Vec3.ZERO);collapsedAnchors.set(3,Vec3.ZERO);
        check(NervAirframeGeometryR52.cradleChordEnclosureR53(wreckStart,wreckStart,collapsedAnchors,safeAxes,"jaw/1/0")==NervAirframeGeometryR52.CRADLE_RADIAL_ENCLOSURE_R53,"Vanishing paired axis has no normalized-curve permission");
        // An actual intermediate vertex must remain in the continuous sweep;
        // this witness supplements, rather than supplies, the analytic bound.
        var jawMiddle=jawStart.interpolate(jawEnd,.5);var jawPart=source.cradleParts(jawMiddle,safeAnchors,safeAxes,true).stream().filter(p->p.name().equals("jaw/1/0")).findFirst().orElseThrow().xyz();
        var jawPoint=jawMiddle.plane().transformPoint(new Vec3(jawPart[0],jawPart[1],jawPart[2]));
        check(source.sweep(jawStart,jawEnd,safeAnchors,safeAxes,0,1,.005).intersects(new AABB(jawPoint.add(-.002,-.002,-.002),jawPoint.add(.002,.002,.002))),"Analytic jaw bound retains real intermediate source contact");
        var actualFloor=new AABB(80,80,301,81,81,302);
        check(source.sweep(wreckStart,wreckEnd,oldAnchors,oldAxes,0,60,.005).intersects(actualFloor),
                "Original posed jaw really penetrates the observed native floor");
        var wreckRise=source.sweep(wreckStart,wreckEnd,safeAnchors,safeAxes,0,60,.005);
        check(!wreckRise.intersects(actualFloor),"Alternative actual paired skin contacts clear the same floor without changing the body");
        var shortRiseStart=wreckStart.interpolate(wreckEnd,0.0000453);
        var shortRiseEnd=wreckStart.interpolate(wreckEnd,0.00035224);
        var liftFloor=new AABB(71,80,290,72,81,291);
        check(!source.sweep(shortRiseStart,shortRiseEnd,safeAnchors,safeAxes,1,2,.005).intersects(liftFloor),
                "A common 15mm lift cannot invent a radial collider from local-coordinate roundoff");
        var clampStart=new Frame(wreckStart.plane(),wreckStart.cargo(),new Rig(112,0,1));
        check(!source.sweep(clampStart,wreckStart,safeAnchors,safeAxes,0,20,.005).intersects(actualFloor),
                "Alternative actual contacts also clear the unchanged full deployment sweep");
        var liftedMiddle=wreckStart.interpolate(wreckEnd,.5);
        var middleJaw=source.cradleParts(liftedMiddle,safeAnchors,safeAxes,true).stream().filter(p->p.name().equals("jaw/2/1")).findFirst().orElseThrow().xyz();
        var jawVertex=liftedMiddle.plane().transformPoint(new Vec3(middleJaw[0],middleJaw[1],middleJaw[2]));
        check(wreckRise.intersects(new AABB(jawVertex.add(-.02,-.02,-.02),jawVertex.add(.02,.02,.02))),
                "New contacts retain the real jaw and reject an intermediate obstacle");
        contactSelectionChecks();
        NervRescueContactEgressR53Test.main(new String[0]);

        var rawBody=parts.get(0).xyz();int triangle=0;Vec3 va,vb,vc,normal;do{va=new Vec3(rawBody[triangle],rawBody[triangle+1],rawBody[triangle+2]);vb=new Vec3(rawBody[triangle+3],rawBody[triangle+4],rawBody[triangle+5]);vc=new Vec3(rawBody[triangle+6],rawBody[triangle+7],rawBody[triangle+8]);normal=vb.subtract(va).cross(vc.subtract(va));triangle+=9;}while(normal.lengthSqr()<1e-12);var centre=va.add(vb).add(vc).scale(1D/3);normal=normal.normalize();Vec3 p0=centre.add(normal.scale(.02)),p1=centre.subtract(normal.scale(.02)).add(vb.subtract(va).normalize().scale(.02)),p2=centre.subtract(normal.scale(.02)).subtract(vb.subtract(va).normalize().scale(.02));var intruder=new NervRigidMeshSweepR52(new double[]{p0.x,p0.y,p0.z,p1.x,p1.y,p1.z,p2.x,p2.y,p2.z});check(sweep.airframeIntersectsCargo(List.of(intruder),RigidTransform.identity(),RigidTransform.identity()),"Payload crossing the actual original body surface cannot be hidden by own-member exclusion");var far=new RigidTransform(new Vec3(0,-200,0),0,0,0,1);check(!sweep.airframeIntersectsCargo(List.of(intruder),far,far),"Remote held cargo does not become fake aircraft carriage or an own-body intersection");
        var bad=new HashMap<>(hashes);bad.put("mesh/tv_facilities_r16.json","0".repeat(64));boolean rejected=false;try{NervAirframeGeometryR52.load(path->Files.readAllBytes(assets.resolve(path)),bad);}catch(IllegalStateException changed){rejected=true;}check(rejected,"Renderer/proof cannot silently select a different actual aircraft resource");
        System.out.println("PASS R52 actual R16 mesh, empty corner, floor and continuous rotor checks: "+checks+" source="+source.fingerprint());
    }
}

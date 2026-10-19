package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.*;
import com.projectseele.util.QuaternionChannelsR45;
import java.io.*;
import java.net.URL;
import java.nio.file.*;
import cpw.mods.niofs.union.UnionPath;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.phys.*;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Server-safe evaluator of the actual selected renderer triangles. No old
 * support cloud, pivot line, convex fill or standing-box fallback is used. */
public final class EvaOriginalMeshGeometryR52
{
    public record Part(String bone,String resource,String sourceSHA256,double[] triangles,AABB bounds)
    {
        public Part{triangles=triangles.clone();}
        @Override public double[] triangles(){return triangles.clone();}
        public int triangleCount(){return triangles.length/9;}
        public List<Vec3> vertices(){var out=new ArrayList<Vec3>(triangles.length/3);for(int n=0;n<triangles.length;n+=3)out.add(new Vec3(triangles[n],triangles[n+1],triangles[n+2]));return List.copyOf(out);}
    }
    public record Geometry(int variant,String sourceFingerprint,List<Part> parts)
    {
        public Geometry{parts=List.copyOf(parts);if(parts.isEmpty())throw new IllegalArgumentException("Complete actual body required");}
        public int triangleCount(){return parts.stream().mapToInt(Part::triangleCount).sum();}
        public AABB bounds(){AABB out=null;for(var part:parts)out=out==null?part.bounds():out.minmax(part.bounds());return out;}
    }
    private record Bone(String name,String parent,Vector3f pivot,Quaternionf bind){}
    private record RawPart(Vector3f pivot,float[] values){}
    private record Corrective(Map<String,Quaternionf> targets,float activation,float[] sparse){}
    private record Skin(String other,float[] weights,float[] rest,Map<String,float[]> influences,Map<String,Matrix4f> inverseBind,Corrective corrective){}
    private record Mesh(String resource,String hash,Map<String,RawPart> parts,Map<String,Skin> skins){}
    private record Rig(Mesh body,Mesh hands,Map<String,Bone> geo,Set<String> handJoints,String contractHash){}
    private static final Set<String> HIDDEN_FACTORY=Set.of("dorsal_liner","r37_red_upper","r37_red_lower","r37_lining");
    public static final String CLASSPATH_SELECTION="/assets/projectseele/eva/eva_original_mesh_geometry_r52_sources.json";
    private static volatile Provider installed;
    @FunctionalInterface public interface ByteSource{byte[] read(String relativeResource)throws IOException;}

    /** Root supplies the same resolved assets and exact per-resource hashes as
     * the graphical client. Never guesses a private override or resource pack. */
    public static void install(Path assets,Map<String,String> expectedSHA256)throws IOException
    {installed=load(assets,expectedSHA256);}
    public static void install(ByteSource actualRenderedAssets,Map<String,String> expectedSHA256)throws IOException
    {installed=load(actualRenderedAssets,expectedSHA256);}
    public static void installClasspath(Map<String,String> expectedSHA256)throws IOException
    {install(EvaOriginalMeshGeometryR52::classpathBytes,expectedSHA256);}
    /** Only the small checked-in source receipt is read; private meshes stay
     * in their existing JAR resources, with no extraction or asset copies. */
    public static void installClasspath()throws IOException
    {
        var manifest=json(classpathBytes("eva/eva_original_mesh_geometry_r52_sources.json"));require("projectseele.r52.actual-rendered-mesh-selection.v1".equals(manifest.get("schema").getAsString()),"Actual classpath source receipt required");
        var hashes=new HashMap<String,String>();for(var entry:manifest.getAsJsonObject("resources").entrySet())hashes.put(entry.getKey(),entry.getValue().getAsString());installClasspath(hashes);
    }
    public static byte[] classpathBytes(String relativeResource)throws IOException
    {
        try(var input=openClasspathResourceR52(relativeResource)){return input.readAllBytes();}
    }
    /** Keep Forge's selected resource and overlay order. Its Union URL input
     * stream first materialises a ZipFS byte channel; the real selected Path's
     * input stream instead inflates incrementally. No private filesystem API,
     * guessed JAR, resource extraction or alternate asset search is used. */
    public static InputStream openClasspathResourceR52(String relativeResource)throws IOException
    {
        require(relativeResource.matches("[A-Za-z0-9_./-]+")&&!relativeResource.contains(".."),"Actual classpath relative resource required");
        var url=EvaOriginalMeshGeometryR52.class.getResource("/assets/projectseele/"+relativeResource);
        if(url==null)throw new IOException("Actual rendered classpath asset absent: "+relativeResource);
        return resourceStreamR52(url);
    }
    static InputStream resourceStreamR52(URL url)throws IOException
    {
        if(!url.getProtocol().equals("union"))return url.openStream();
        try{return Files.newInputStream(selectedUnionPathR52(Path.of(url.toURI()),0));}
        catch(java.net.URISyntaxException invalid){throw new IOException("Invalid actual resource URL",invalid);}
    }
    private static Path selectedUnionPathR52(Path path,int depth)throws IOException
    {
        if(!(path instanceof UnionPath union))return path;
        if(depth>=4)throw new IOException("Nested actual resource filesystem exceeds bound");
        var selected=new ArrayList<Path>(1);var filter=union.getFileSystem().getFilesystemFilter();
        String logical=union.toAbsolutePath().normalize().toString().replace('\\','/');
        if(logical.startsWith("/"))logical=logical.substring(1);
        final String name=logical;final int count=logical.split("/").length;
        // UnionFileSystem invokes this public filter on the underlying paths
        // in the very same priority order used by findFirstFiltered. Honour
        // its filesystem filter before retaining the first exact member.
        try(var entries=Files.newDirectoryStream(union.getParent(),candidate->{
            if(!candidate.getFileName().equals(union.getFileName())&&!candidate.getFileName().toString().equals(union.getFileName().toString()))return false;
            String baseName;
            if(candidate.getFileSystem().provider().getScheme().equals("jar")){
                String archive=candidate.toUri().getRawSchemeSpecificPart();int bang=archive.indexOf("!/");
                if(bang<0)throw new IOException("Actual archive resource has no member boundary");
                baseName=Path.of(java.net.URI.create(archive.substring(0,bang))).toString().replace('\\','/');
            }else{Path base=candidate;for(int n=0;n<count;n++)base=base==null?null:base.getParent();if(base==null)throw new IOException("Actual resource base is absent");baseName=base.toString().replace('\\','/');}
            if(baseName.startsWith("/"))baseName=baseName.substring(1);
            if((filter==null||filter.test(name,baseName))&&selected.isEmpty())selected.add(candidate);
            return false;
        })){for(var ignored:entries){/* The callback resolves the real member. */}}
        if(selected.isEmpty())throw new IOException("Actual selected resource member absent: "+union);
        return selectedUnionPathR52(selected.get(0),depth+1);
    }
    /** Immutable selected CPU source; querying never installs or edits actors. */
    public static Provider readOnlySelectedProviderR52()
    {var result=installed;if(result==null)throw new IllegalStateException("Actual selected mesh source not installed");return result;}

    public static Provider load(Path assets,Map<String,String> expectedSHA256)throws IOException
    {
        var root=assets.toAbsolutePath().normalize();return load(relative->{var path=root.resolve(relative).normalize();require(path.startsWith(root)&&Files.isRegularFile(path),"Actual selected resource absent: "+relative);return Files.readAllBytes(path);},expectedSHA256);
    }
    public static Provider load(ByteSource actualRenderedAssets,Map<String,String> expectedSHA256)throws IOException
    {
        var rigs=new HashMap<Integer,Rig>();var selection=new TreeMap<String,String>();
        for(int variant=0;variant<3;variant++)
        {
            String stem="eva_unit0"+variant;String body="mesh/"+stem+".mesh.json",hands="mesh/"+stem+"_anatomical_hands_r45.mesh.json",geo="geo/"+stem+".geo.json",contract="hand_rigs/unit0"+variant+"/hand_rig_contract.json";
            byte[] bodyBytes=read(actualRenderedAssets,body,expectedSHA256,selection),handBytes=read(actualRenderedAssets,hands,expectedSHA256,selection),geoBytes=read(actualRenderedAssets,geo,expectedSHA256,selection),contractBytes=read(actualRenderedAssets,contract,expectedSHA256,selection);
            var skeleton=skeleton(json(geoBytes));var c=json(contractBytes);
            require(c.get("rig").getAsInt()==variant&&c.get("schema").getAsString().equals("projectseele.anatomical-hands.r45.v2"),"Actual 34-joint contract required");
            require(!c.has("knife_mechanism_r45"),"Renderer selects a different body mesh; this selection is incomplete");
            var joints=new HashSet<String>();for(var value:c.getAsJsonArray("new_bones")){String name=value.getAsJsonObject().get("name").getAsString();require(skeleton.containsKey(name),"Hand joint missing from selected GEO");joints.add(name);}
            require(joints.size()==34,"Exactly 34 actual hand joints required");
            var b=mesh(body,selection.get(body),json(bodyBytes));var h=mesh(hands,selection.get(hands),json(handBytes));
            require(h.parts().keySet().equals(Set.of("hand_l","hand_r")),"Both actual replacement hand surfaces required");
            for(var m:List.of(b,h))for(String part:m.parts().keySet())require(skeleton.containsKey(part),"Rendered part missing actual GEO bone: "+part);
            for(String side:List.of("l","r"))
            {
                require(b.parts().keySet().containsAll(Set.of("arm_"+side,"forearm_"+side,"foot_"+side,"leg_"+side,"shin_"+side)),"Actual complete limb mesh missing");
                var skin=h.skins().get("hand_"+side);require(skin!=null&&skin.influences().size()==18&&skin.inverseBind().size()==18&&skin.corrective()!=null,"Actual 18-influence hand skin/corrective required");
                var expected=new HashSet<String>();expected.add("hand_"+side);for(String joint:joints)if(joint.startsWith("r45_hand_"+side+"_"))expected.add(joint);
                require(skin.influences().keySet().equals(expected),"Hand source joint palette identity differs");
            }
            rigs.put(variant,new Rig(b,h,skeleton,Set.copyOf(joints),selection.get(contract)));
        }
        return new Provider(Map.copyOf(rigs),sha(selection.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8)));
    }
    private static byte[] read(ByteSource source,String relative,Map<String,String> expected,Map<String,String> receipt)throws IOException
    {
        String hash=expected.get(relative);require(hash!=null&&hash.matches("[0-9a-f]{64}"),"Exact actual rendered resource SHA256 required: "+relative);
        byte[] bytes=source.read(relative);require(bytes!=null&&hash.equals(sha(bytes)),"Actual rendered resource changed: "+relative);receipt.put(relative,hash);return bytes;
    }
    private static JsonObject json(byte[] data){return JsonParser.parseString(new String(data,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();}
    private static String sha(byte[] bytes){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}catch(Exception impossible){throw new IllegalStateException(impossible);}}

    /** Evaluate the actual closed, unarmed frozen assembly, including the
     * retained service pose after recovery. A bind-pose comparison must not
     * reject original joints that have already been captured and restored. */
    public static Geometry parts(EvaUnit01Entity eva,EvaBodyPose.Sample frozenLocalPose)
    {
        var cradle=EvaAirTransportR31.cradleStateR50(eva);require(cradle.getBoolean("MechanicalFrameR52"),"Actual mechanical frozen source required");
        Geometry geometry;
        if(cradle.getBoolean("FrozenOccupiedRecoveryR52"))
        {
            // Rehydrate with the same evaluator used by occupied capture.
            // A field recovery can retain a bent or damaged dorsal joint;
            // reloading it must not require a factory rest pose.
            var provider=readOnlySelectedProviderR52();
            var hands=EvaFrozenHandsR52.decode(eva.getUnitVariant(),provider.handContractFingerprint(eva.getUnitVariant()),provider.handJoints(eva.getUnitVariant()),cradle.getCompound(EvaFrozenHandsR52.KEY));
            geometry=provider.evaluate(eva.getUnitVariant(),frozenLocalPose,hands);
        }
        else geometry=cradle.getBoolean("FrozenRecoveryR52")?partsForFrozenRecovery(eva,frozenLocalPose,cradle.getCompound(EvaFrozenHandsR52.KEY)):partsForCapture(eva,frozenLocalPose,cradle.getCompound(EvaFrozenHandsR52.KEY));
        var origin=cradle.getCompound("Origin");
        for(String bone:frozenLocalPose.rig.keySet())
        {
            var row=origin.getList(bone,net.minecraft.nbt.Tag.TAG_FLOAT);require(row.size()==9,"Actual captured body bone absent");
            var exact=origin.getCompound("__exact_quaternions_r53").getList(bone,net.minecraft.nbt.Tag.TAG_FLOAT);
            var q=exact.size()==4?new Quaternionf(exact.getFloat(0),exact.getFloat(1),exact.getFloat(2),exact.getFloat(3)):new Quaternionf().rotationZYX(row.getFloat(2),row.getFloat(1),row.getFloat(0));var p=new Vector3f(-row.getFloat(3),row.getFloat(4),row.getFloat(5)).div(16);
            require(sameRotation(q,frozenLocalPose.rotations.get(bone))&&p.distanceSquared(frozenLocalPose.positions.get(bone))<1e-12F
                    &&row.getFloat(6)==1&&row.getFloat(7)==1&&row.getFloat(8)==1,"Body argument is not the actual captured unturned unit-scale pose");
        }
        return geometry;
    }
    /** Root calls before setting Active, then stores this same hand snapshot
     * under FRAME/AnatomicalHandsR52. Nothing in this query starts transport. */
    public static Geometry partsForCapture(EvaUnit01Entity eva,EvaBodyPose.Sample frozenLocalPose,CompoundTag handSnapshot)
    {return partsForFrozen(eva,frozenLocalPose,handSnapshot,false);}
    /** Recovery evaluates the retained field pose just as the pickup preview
     * does; a weapon or open dorsal cover is not a factory-pose prerequisite. */
    public static Geometry partsForFrozenRecovery(EvaUnit01Entity eva,EvaBodyPose.Sample frozenLocalPose,CompoundTag handSnapshot)
    {
        require(EvaShutdownR30.disabled(eva)&&eva.getPilotEntity()==null,"Actual stopped unpiloted hull required");
        var provider=readOnlySelectedProviderR52();
        var hands=EvaFrozenHandsR52.decode(eva.getUnitVariant(),provider.handContractFingerprint(eva.getUnitVariant()),provider.handJoints(eva.getUnitVariant()),handSnapshot);
        return provider.evaluate(eva.getUnitVariant(),frozenLocalPose,hands);
    }
    private static Geometry partsForFrozen(EvaUnit01Entity eva,EvaBodyPose.Sample frozenLocalPose,CompoundTag handSnapshot,boolean factory)
    {
        var provider=installed;if(provider==null)throw new IllegalStateException("Root actual asset selection not installed");
        require(!eva.isExperimentalUnit()&&eva.getUnitVariant()>=0&&eva.getUnitVariant()<3,"Only original three actual rigs are admitted");
        require(eva.isNervLogisticsLocked()&&!eva.isFirstBattleActive()&&!eva.isBerserk()&&eva.getWeapon()==EvaUnit01Entity.WEAPON_FISTS&&!EvaShieldRigR47.equipped(eva),"Factory frozen equipment/pose admission only");
        require(EvaDorsalMechanism.open(eva)<.0001F&&EvaDorsalMechanism.bow(eva)<.0001F&&EvaBerserkMotionR34.mouth(eva,1)==0,"Actual dorsal and late mouth mechanism must be closed before capture");
        var rig=provider.rigs.get(eva.getUnitVariant());require(EvaAnatomicalHandsR45.contractFingerprintR45(eva.getUnitVariant()).equals(rig.contractHash()),"Actual live hand override differs from geometry selection");
        require(frozenLocalPose.rotations.containsKey("dorsal_cover")&&sameRotation(frozenLocalPose.rotations.get("dorsal_cover"),new Quaternionf())
                &&frozenLocalPose.positions.get("dorsal_cover").lengthSquared()<1e-12F,"Captured late dorsal cover does not match the actual closed renderer state");
        var hands=EvaFrozenHandsR52.decode(eva.getUnitVariant(),rig.contractHash(),rig.handJoints(),handSnapshot);
        provider.validateBody(eva.getUnitVariant(),frozenLocalPose,factory);
        return provider.evaluate(eva.getUnitVariant(),frozenLocalPose,hands);
    }

    public static final class Provider
    {
        private final Map<Integer,Rig> rigs;private final String fingerprint;
        private record Rotation(float x,float y,float z,float w)
        {static Rotation of(Quaternionf q){return new Rotation(q.x,q.y,q.z,q.w);}}
        private record BodyChannels(String parent,float px,float py,float pz,Rotation rotation,float x,float y,float z){}
        private record EvaluatedPose(Map<String,BodyChannels> body,Map<String,Rotation> hands,boolean liner,boolean dominantReview){}
        private record Evaluated(EvaluatedPose pose,Geometry geometry){}
        private final Map<Integer,Evaluated> evaluated=new HashMap<>();
        private static EvaluatedPose evaluationPose(EvaBodyPose.Sample body,EvaAnatomicalHandsR45.Pose hands,boolean liner)
        {
            var bones=new HashMap<String,BodyChannels>();
            for(var entry:body.rig.entrySet())
            {
                var bone=entry.getValue();var p=bone.pivot();var offset=body.positions.get(entry.getKey());
                bones.put(entry.getKey(),new BodyChannels(bone.parent(),p.x,p.y,p.z,Rotation.of(body.rotations.get(entry.getKey())),offset.x,offset.y,offset.z));
            }
            var fingers=new HashMap<String,Rotation>();hands.rotations().forEach((name,q)->fingers.put(name,Rotation.of(q)));
            return new EvaluatedPose(Map.copyOf(bones),Map.copyOf(fingers),liner,Boolean.getBoolean("projectseele.r44DominantSkinReview"));
        }
        private Provider(Map<Integer,Rig> rigs,String fingerprint){this.rigs=rigs;this.fingerprint=fingerprint;}
        public String sourceFingerprint(){return fingerprint;}
        public String handContractFingerprint(int variant){return rig(variant).contractHash();}
        public Set<String> handJoints(int variant){return rig(variant).handJoints();}
        private Rig rig(int variant){var r=rigs.get(variant);require(r!=null,"Original rig selection absent");return r;}
        private void validateBody(int variant,EvaBodyPose.Sample body,boolean factory)
        {
            var r=rig(variant);require(body!=null&&!body.rig.isEmpty(),"Original frozen local body required");
            for(var entry:body.rig.entrySet())
            {
                var b=r.geo().get(entry.getKey());var actual=entry.getValue();require(b!=null&&Objects.equals(b.parent(),actual.parent())&&b.pivot().distance(actual.pivot())<1e-5F,"Actual selected rig parent/pivot differs: "+entry.getKey());
                var q=body.rotations.get(entry.getKey());var p=body.positions.get(entry.getKey());unit(q);finite(p);
                if(factory)require(sameRotation(q,actual.bindRotation())&&p.lengthSquared()<1e-12F,"Only exact actual factory frozen body is commissioned: "+entry.getKey());
            }
            // EvaMouthR37 writes the extra jaw after the BodyPose commit. Its
            // verified closed rule is zero rotation/offset, identical to this
            // selected GEO bind; hidden inner mouth surfaces are not submitted.
            for(String part:r.body().parts().keySet())if(!HIDDEN_FACTORY.contains(part)&&!part.equals("r37_jaw"))require(body.rig.containsKey(part),"Frozen body is missing a rendered source part: "+part);
        }
        /** Pure evaluator for asset/renderer comparison, including articulated
         * poses and corrective tests. Calling it never commissions movement. */
        public Geometry evaluate(int variant,EvaBodyPose.Sample body,EvaAnatomicalHandsR45.Pose hands)
        {return evaluateMechanicalService(variant,body,hands,false);}
        /** Conservative displacement bounds for the actual selected palette.
         * The DQ sum is aligned to its largest-weight quaternion, hence its
         * norm is at least 1/N. The 16*N*N factor covers normalization, dual
         * projection and translation derivatives. A possible hemisphere
         * crossing is rejected instead of assuming a continuous skin. */
        public Map<String,Double> releaseMotionBoundsR52(int variant,EvaBodyPose.Sample from,EvaAnatomicalHandsR45.Pose fromHands,EvaBodyPose.Sample to,EvaAnatomicalHandsR45.Pose toHands,Geometry actual)
        {
            var r=rig(variant);var locals=new HashMap<String,Quaternionf>();var offsets=new HashMap<String,Vector3f>();var pivots=new HashMap<String,Vector3f>();var angles=new HashMap<String,Double>();var displacements=new HashMap<String,Double>();
            for(var b:r.geo().values()){String name=b.name();var a=from.rig.containsKey(name)?from.rotations.get(name):fromHands.rotations().getOrDefault(name,b.bind());var z=to.rig.containsKey(name)?to.rotations.get(name):toHands.rotations().getOrDefault(name,b.bind());var e=QuaternionChannelsR45.euler(a);locals.put(name,new Quaternionf().rotationZYX(e.z,e.y,e.x));var p=from.rig.containsKey(name)?from.positions.get(name):new Vector3f();var q=to.rig.containsKey(name)?to.positions.get(name):new Vector3f();offsets.put(name,new Vector3f(p));pivots.put(name,from.rig.containsKey(name)?from.rig.get(name).pivot():b.pivot());double angle=a.equals(z,1e-7F)?0:2*Math.acos(Math.min(1,Math.abs(a.dot(z))));angles.put(name,angle);displacements.put(name,(double)p.distance(q)*EvaScale.RENDER_SCALE);}
            var models=new HashMap<String,Matrix4f>();for(String name:r.geo().keySet())model(name,r.geo(),locals,offsets,pivots,models,new HashSet<>());
            var result=new HashMap<String,Double>();for(var part:actual.parts()){var mesh=r.body().parts().containsKey(part.bone())?r.body():r.hands();var raw=mesh.parts().get(part.bone());var skin=mesh.skins().get(part.bone());var influences=new HashSet<String>();influences.add(part.bone());if(skin!=null){if(skin.influences().isEmpty())influences.add(skin.other());else influences.addAll(skin.influences().keySet());}
                var drivers=new HashSet<String>();for(String influence:influences)for(String n=influence;n!=null;n=r.geo().get(n).parent())if(angles.get(n)>0||displacements.get(n)>0)drivers.add(n);if(skin!=null&&skin.corrective()!=null)for(String n:skin.corrective().targets().keySet())if(angles.get(n)>0)drivers.add(n);
                double angle=drivers.stream().mapToDouble(angles::get).sum(),translation=drivers.stream().mapToDouble(displacements::get).sum();if(angle==0&&translation==0){result.put(part.bone(),0D);continue;}
                var rotations=new ArrayList<Quaternionf>();for(String n:influences){var rotationMatrix=new Matrix4f(models.get(n));if(skin!=null&&skin.inverseBind().containsKey(n))rotationMatrix.mul(skin.inverseBind().get(n));rotations.add(rotationMatrix.getUnnormalizedRotation(new Quaternionf()).normalize());}boolean crossed=false;for(int a=0;a<rotations.size();a++)for(int b=a+1;b<rotations.size();b++)if(Math.abs(rotations.get(a).dot(rotations.get(b)))<=Math.sin(Math.min(Math.PI/2,angle))+1e-5)crossed=true;if(crossed){result.put(part.bone(),Double.POSITIVE_INFINITY);continue;}
                AABB rest=null;var values=skin==null?raw.values():skin.rest();for(int i=0;i<values.length;i+=8){var p=new Vec3(-(values[i]+raw.pivot().x)/16,(values[i+1]+raw.pivot().y)/16,(values[i+2]+raw.pivot().z)/16);rest=rest==null?new AABB(p,p):rest.minmax(new AABB(p,p));}
                double radius=0;for(String d:drivers){var pivot=models.get(d).transformPosition(new Vector3f(pivots.get(d))).mul(EvaScale.RENDER_SCALE);for(String n:influences){var m=new Matrix4f(models.get(n));if(skin!=null&&skin.inverseBind().containsKey(n))m.mul(skin.inverseBind().get(n));for(double x:new double[]{rest.minX,rest.maxX})for(double y:new double[]{rest.minY,rest.maxY})for(double z:new double[]{rest.minZ,rest.maxZ})radius=Math.max(radius,m.transformPosition(new Vector3f((float)x,(float)y,(float)z)).mul(EvaScale.RENDER_SCALE).distance(pivot));}for(var p:part.vertices())radius=Math.max(radius,new Vec3(pivot.x,pivot.y,pivot.z).distanceTo(p));}
                double bound=(radius+translation)*Math.expm1(angle)+translation;if(skin!=null)bound*=16D*influences.size()*influences.size();if(skin!=null&&skin.corrective()!=null)bound+=Math.sqrt(3)*2/16*EvaScale.RENDER_SCALE*1.5*angle/skin.corrective().activation();result.put(part.bone(),bound+.00005);
            }return Map.copyOf(result);
        }
        /** Pure actual service visibility; never relaxes any native capture admission. */
        public synchronized Geometry evaluateMechanicalService(int variant,EvaBodyPose.Sample body,EvaAnatomicalHandsR45.Pose hands,boolean linerVisible)
        {
            // Cache exact local channels, not the game clock: a mechanism may
            // change pose more than once in one tick. World frames stay live.
            var pose=evaluationPose(body,hands,linerVisible);var old=evaluated.get(variant);
            if(old!=null&&old.pose().equals(pose))return old.geometry();
            var geometry=new Geometry(variant,fingerprint,evaluateServiceParts(variant,body,hands,linerVisible,false));
            evaluated.put(variant,new Evaluated(pose,geometry));return geometry;
        }
        /** Contact-only query: these two arm surfaces are never a transport envelope. */
        public List<Part> evaluateShoulderContactsR53(int variant,EvaBodyPose.Sample body,EvaAnatomicalHandsR45.Pose hands)
        {
            return evaluateServiceParts(variant,body,hands,false,true);
        }
        private List<Part> evaluateServiceParts(int variant,EvaBodyPose.Sample body,EvaAnatomicalHandsR45.Pose hands,boolean linerVisible,boolean shouldersOnly)
        {
            var r=rig(variant);validateBody(variant,body,false);require(hands.rotations().keySet().equals(r.handJoints()),"Full actual 34-joint hand pose required");
            var locals=new HashMap<String,Quaternionf>();var positions=new HashMap<String,Vector3f>();var pivots=new HashMap<String,Vector3f>();
            for(var b:r.geo().values())
            {
                var q=body.rig.containsKey(b.name())?body.rotations.get(b.name()):hands.rotations().getOrDefault(b.name(),b.bind());
                unit(q);var euler=QuaternionChannelsR45.euler(q);locals.put(b.name(),new Quaternionf().rotationZYX(euler.z,euler.y,euler.x));
                positions.put(b.name(),body.rig.containsKey(b.name())?new Vector3f(body.positions.get(b.name())):new Vector3f());pivots.put(b.name(),body.rig.containsKey(b.name())?new Vector3f(body.rig.get(b.name()).pivot()):new Vector3f(b.pivot()));
            }
            var models=new HashMap<String,Matrix4f>();for(String name:r.geo().keySet())model(name,r.geo(),locals,positions,pivots,models,new HashSet<>());
            var parts=new ArrayList<Part>();
            for(var mesh:List.of(r.body(),r.hands()))for(var entry:new TreeMap<>(mesh.parts()).entrySet())
            {
                String name=entry.getKey();if(shouldersOnly&&(mesh!=r.body()||!Set.of("arm_l","arm_r").contains(name)))continue;if(mesh==r.body()&&(name.startsWith("hand_")||name.startsWith("finger_")||(HIDDEN_FACTORY.contains(name)&&!(linerVisible&&name.equals("dorsal_liner")))))continue;
                var part=entry.getValue();float[] values=skin(part,mesh.skins().get(name),name,models,locals);
                double[] xyz=new double[values.length/8*3];AABB bounds=null;Matrix4f matrix=models.get(name);
                for(int i=0,n=0;i<values.length;i+=8,n+=3)
                {
                    var point=matrix.transformPosition(new Vector3f(-(values[i]+part.pivot().x)/16,(values[i+1]+part.pivot().y)/16,(values[i+2]+part.pivot().z)/16)).mul(EvaScale.RENDER_SCALE);
                    finite(point);xyz[n]=point.x;xyz[n+1]=point.y;xyz[n+2]=point.z;var p=new Vec3(point.x,point.y,point.z);var box=new AABB(p,p);bounds=bounds==null?box:bounds.minmax(box);
                }
                parts.add(new Part(name,mesh.resource(),mesh.hash(),xyz,bounds));
            }
            return List.copyOf(parts);
        }
    }
    private static Matrix4f model(String name,Map<String,Bone> bones,Map<String,Quaternionf> locals,Map<String,Vector3f> positions,Map<String,Vector3f> pivots,Map<String,Matrix4f> cache,Set<String> active)
    {
        if(cache.containsKey(name))return new Matrix4f(cache.get(name));require(active.add(name),"Cyclic actual rig");var bone=bones.get(name);require(bone!=null,"Actual palette bone missing: "+name);
        var p=pivots.get(name);var matrix=new Matrix4f().translation(positions.get(name)).translate(p).rotate(locals.get(name)).translate(-p.x,-p.y,-p.z);
        if(bone.parent()!=null)matrix=model(bone.parent(),bones,locals,positions,pivots,cache,active).mul(matrix);active.remove(name);cache.put(name,matrix);return new Matrix4f(matrix);
    }
    private static Map<String,Bone> skeleton(JsonObject root)
    {
        var result=new LinkedHashMap<String,Bone>();var geometries=root.getAsJsonArray("minecraft:geometry");require(geometries.size()==1,"One actual GEO skeleton required");
        for(var value:geometries.get(0).getAsJsonObject().getAsJsonArray("bones"))
        {
            var b=value.getAsJsonObject();String name=b.get("name").getAsString();var p=vector(b.getAsJsonArray("pivot")).mul(-1,1,1).div(16);var e=b.has("rotation")?vector(b.getAsJsonArray("rotation")).mul((float)Math.PI/180):new Vector3f();
            var bone=new Bone(name,b.has("parent")?b.get("parent").getAsString():null,p,new Quaternionf().rotationZYX(e.z,-e.y,-e.x));require(result.putIfAbsent(name,bone)==null,"Duplicate actual GEO bone");
        }
        for(var b:result.values())require(b.parent()==null||result.containsKey(b.parent()),"Actual GEO parent missing");return Map.copyOf(result);
    }
    private static Mesh mesh(String resource,String hash,JsonObject root)
    {
        require(root.get("stride").getAsInt()==8,"Actual local triangle stride8 required");var parts=new LinkedHashMap<String,RawPart>();
        for(var entry:root.getAsJsonObject("parts").entrySet())
        {
            var o=entry.getValue().getAsJsonObject();var p=vector(o.getAsJsonArray("pivot"));float[] v=floats(o.getAsJsonArray("vertices"));require(v.length>0&&v.length%24==0,"Complete actual triangles required");parts.put(entry.getKey(),new RawPart(p,v));
        }
        Map<String,Skin> skins=automaticSkins(parts);if(root.has("jointSkins")){var authored=authoredSkins(root.getAsJsonObject("jointSkins"),parts);if(root.has("r37_mouth")){skins=new HashMap<>(skins);skins.putAll(authored);}else skins=authored;}
        return new Mesh(resource,hash,Map.copyOf(parts),Map.copyOf(skins));
    }
    private static Map<String,Skin> authoredSkins(JsonObject definitions,Map<String,RawPart> parts)
    {
        var out=new HashMap<String,Skin>();for(var entry:definitions.entrySet())
        {
            var p=parts.get(entry.getKey());require(p!=null,"Authored part absent");var d=entry.getValue().getAsJsonObject();int count=p.values().length/8;
            if(d.has("influences"))
            {
                var weights=new TreeMap<String,float[]>();float[] sums=new float[count];for(var row:d.getAsJsonObject("influences").entrySet()){var w=floats(row.getValue().getAsJsonArray());require(w.length==count,"Actual skin weight length");for(int n=0;n<count;n++){require(w[n]>=0&&w[n]<=1,"Actual skin weight range");sums[n]+=w[n];}weights.put(row.getKey(),w);}for(float sum:sums)require(Math.abs(sum-1)<=.0002F,"Actual skin sum differs");
                var inverse=new HashMap<String,Matrix4f>();if(d.has("inverseBindColumnMajor"))for(var row:d.getAsJsonObject("inverseBindColumnMajor").entrySet()){var values=floats(row.getValue().getAsJsonArray());require(weights.containsKey(row.getKey())&&values.length==16,"Actual inverse bind palette differs");var matrix=new Matrix4f().set(values);require(Math.abs(matrix.determinant())>=.0001F,"Singular actual inverse bind");inverse.put(row.getKey(),matrix);}require(inverse.isEmpty()||inverse.size()==weights.size(),"Incomplete actual inverse bind");
                out.put(entry.getKey(),new Skin("",new float[0],p.values().clone(),Collections.unmodifiableMap(weights),Map.copyOf(inverse),corrective(d,count)));
            }
            else{var w=floats(d.getAsJsonArray("weights"));require(w.length==count,"Actual pair-skin weights differ");for(float weight:w)require(weight>=0&&weight<=1,"Actual pair-skin weight range");out.put(entry.getKey(),new Skin(d.get("otherBone").getAsString(),w,p.values().clone(),Map.of(),Map.of(),null));}
        }
        return out;
    }
    private static Corrective corrective(JsonObject definition,int count)
    {
        if(!definition.has("contactCorrectiveR45"))return null;var c=definition.getAsJsonObject("contactCorrectiveR45");float degrees=c.get("activation_degrees").getAsFloat();require(Float.isFinite(degrees)&&degrees>0&&degrees<=60,"Actual corrective activation differs");
        var targets=new HashMap<String,Quaternionf>();for(var row:c.getAsJsonObject("local_quaternion_xyzw").entrySet()){require(row.getKey().startsWith("r45_hand_")&&definition.getAsJsonObject("influences").has(row.getKey()),"Actual corrective driver absent");var q=floats(row.getValue().getAsJsonArray());require(q.length==4,"Corrective quaternion width");var value=new Quaternionf(q[0],q[1],q[2],q[3]);require(Math.abs(value.lengthSquared()-1)<=.001F,"Invalid corrective quaternion");targets.put(row.getKey(),value.normalize());}require(!targets.isEmpty(),"Actual corrective drivers required");
        var rows=c.getAsJsonArray("vertex_index_position_normal_delta");float[] sparse=new float[rows.size()*7];var seen=new HashSet<Integer>();for(int i=0;i<rows.size();i++){var row=floats(rows.get(i).getAsJsonArray());require(row.length==7&&row[0]==(int)row[0]&&row[0]>=0&&row[0]<count&&seen.add((int)row[0]),"Corrective source vertex identity differs");for(int k=1;k<7;k++)require(Math.abs(row[k])<=2,"Unbounded actual corrective");System.arraycopy(row,0,sparse,i*7,7);}
        return new Corrective(Map.copyOf(targets),(float)Math.toRadians(degrees),sparse);
    }
    private static Vector3f restPoint(RawPart p,int n){return new Vector3f(p.values()[n]+p.pivot().x,p.values()[n+1]+p.pivot().y,p.values()[n+2]+p.pivot().z);}
    /** Exact renderer seam construction is kept, including its rounded shared
     * rest point. It changes source skin rest data, never substitutes geometry. */
    private static Map<String,Skin> automaticSkins(Map<String,RawPart> parts)
    {
        var out=new HashMap<String,Skin>();float epsilon=.002F*.002F;
        for(String joint:List.of("elbow","ankle","wrist"))for(String side:List.of("l","r"))
        {
            String upper=(joint.equals("elbow")?"arm_":joint.equals("ankle")?"shin_":"forearm_")+side,lower=(joint.equals("elbow")?"forearm_":joint.equals("ankle")?"foot_":"hand_")+side;var a=parts.get(upper);var b=parts.get(lower);if(a==null||b==null)continue;var seam=new ArrayList<Vector3f>();
            for(int i=0;i<a.values().length;i+=8){var point=restPoint(a,i);for(int j=0;j<b.values().length;j+=8){var other=restPoint(b,j);if(point.distanceSquared(other)>epsilon)continue;var centre=new Vector3f(point).add(other).mul(.5F);if(seam.stream().noneMatch(v->v.distanceSquared(centre)<epsilon))seam.add(centre);break;}}if(seam.size()<3)continue;
            for(String name:List.of(upper,lower)){var p=parts.get(name);float[] weights=new float[p.values().length/8],rest=p.values().clone();for(int i=0;i<weights.length;i++){var point=restPoint(p,i*8);float distance=Float.POSITIVE_INFINITY;Vector3f nearest=null;for(var s:seam){float d=point.distanceSquared(s);if(d<distance){distance=d;nearest=s;}}if(distance<epsilon){weights[i]=.5F;rest[i*8]=nearest.x-p.pivot().x;rest[i*8+1]=nearest.y-p.pivot().y;rest[i*8+2]=nearest.z-p.pivot().z;}else{float t=Math.max(0,1-(float)Math.sqrt(distance)/6);weights[i]=.5F*t*t*(3-2*t);}}merge(out,name,name.equals(upper)?lower:upper,weights,rest);}
        }
        if(parts.containsKey("head")&&parts.containsKey("torso_upper")){var p=parts.get("head");var weights=new float[p.values().length/8];for(int i=0;i<weights.length;i++){float y=p.values()[i*8+1]+p.pivot().y,z=p.values()[i*8+2]+p.pivot().z,blend=Math.max(0,Math.min(1,(p.pivot().y+1.5F-y)/7));if(y>p.pivot().y-3&&z<-6)blend=0;weights[i]=blend*blend*(3-2*blend);}merge(out,"head","torso_upper",weights,p.values().clone());}return out;
    }
    private static void merge(Map<String,Skin> out,String name,String other,float[] weights,float[] rest)
    {
        var previous=out.get(name);if(previous==null){out.put(name,new Skin(other,weights,rest,Map.of(),Map.of(),null));return;}var all=new TreeMap<String,float[]>();int count=weights.length;
        if(previous.influences().isEmpty()){all.put(previous.other(),previous.weights().clone());float[] own=new float[count];for(int i=0;i<count;i++)own[i]=1-previous.weights()[i];all.put(name,own);}else previous.influences().forEach((n,w)->all.put(n,w.clone()));
        var own=all.get(name);var added=all.computeIfAbsent(other,n->new float[count]);for(int i=0;i<count;i++){float take=Math.min(own[i],weights[i]);own[i]-=take;added[i]+=take;}out.put(name,new Skin("",new float[0],rest,Map.copyOf(all),Map.of(),null));
    }
    private static float[] skin(RawPart p,Skin skin,String name,Map<String,Matrix4f> models,Map<String,Quaternionf> locals)
    {
        if(skin==null)return p.values();var inverse=new Matrix4f(models.get(name)).invert();var inverseRotation=inverse.getUnnormalizedRotation(new Quaternionf()).normalize();
        if(skin.influences().isEmpty())
        {
            require(models.containsKey(skin.other()),"Actual pair-skin bone absent");var relative=new Matrix4f(inverse).mul(models.get(skin.other()));var q=relative.getUnnormalizedRotation(new Quaternionf()).normalize();if(q.w<0)q.mul(-1);var d=new Quaternionf(relative.m30(),relative.m31(),relative.m32(),0).mul(q).mul(.5F);var out=skin.rest().clone();
            for(int n=0;n<skin.weights().length;n++){float w=skin.weights()[n];if(w==0)continue;deform(p,skin.rest(),out,n,new float[]{q.x*w,q.y*w,q.z*w,1-w+q.w*w,d.x*w,d.y*w,d.z*w,d.w*w});}return out;
        }
        int count=skin.influences().size(),slot=0;float[][] transforms=new float[count][8],weights=new float[count][];int[] stable=new int[count];var names=skin.influences().keySet().stream().sorted().toList();
        for(var entry:skin.influences().entrySet())
        {
            require(models.containsKey(entry.getKey()),"Actual authored palette bone absent");var model=new Matrix4f(models.get(entry.getKey()));var bind=skin.inverseBind().get(entry.getKey());if(bind!=null)model.mul(bind);var global=model.getUnnormalizedRotation(new Quaternionf()).normalize();if(global.w<0)global.mul(-1);var relative=new Matrix4f(inverse).mul(model);var q=relative.getUnnormalizedRotation(new Quaternionf()).normalize();if(q.dot(new Quaternionf(inverseRotation).mul(global))<0)q.mul(-1);var d=new Quaternionf(relative.m30(),relative.m31(),relative.m32(),0).mul(q).mul(.5F);stable[slot]=names.indexOf(entry.getKey());transforms[slot]=new float[]{q.x,q.y,q.z,q.w,d.x,d.y,d.z,d.w};weights[slot++]=entry.getValue();
        }
        boolean dominantReview=Boolean.getBoolean("projectseele.r44DominantSkinReview");
        var out=skin.rest().clone();for(int n=0;n<skin.rest().length/8;n++)
        {
            int dominant=0;for(int j=1;j<count;j++)if(weights[j][n]>weights[dominant][n]||dominantReview&&weights[j][n]==weights[dominant][n]&&weights[j][n]>0&&stable[j]<stable[dominant])dominant=j;
            var reference=transforms[dominant];var blend=new float[8];for(int j=0;j<count;j++){float w=weights[j][n];if(w==0)continue;var t=transforms[j];if(t[0]*reference[0]+t[1]*reference[1]+t[2]*reference[2]+t[3]*reference[3]<0)w=-w;for(int k=0;k<8;k++)blend[k]+=t[k]*w;}deform(p,skin.rest(),out,n,blend);
        }
        if(skin.corrective()!=null)
        {
            var c=skin.corrective();float distance=0;for(var driver:c.targets().entrySet()){var actual=locals.get(driver.getKey());require(actual!=null,"Actual corrective joint absent");float dot=Math.min(1,Math.abs(actual.dot(driver.getValue())));distance=Math.max(distance,2*(float)Math.acos(dot));}float w=Math.max(0,1-distance/c.activation());w=w*w*(3-2*w);
            if(w>0)for(int i=0;i<c.sparse().length;i+=7){int at=(int)c.sparse()[i]*8;for(int k=0;k<3;k++)out[at+k]+=w*c.sparse()[i+1+k];}
        }
        return out;
    }
    private static void deform(RawPart p,float[] rest,float[] out,int vertex,float[] b)
    {
        float rx=b[0],ry=b[1],rz=b[2],rw=b[3],dx=b[4],dy=b[5],dz=b[6],dw=b[7];float inv=1F/(float)Math.sqrt(rx*rx+ry*ry+rz*rz+rw*rw);require(Float.isFinite(inv),"Actual DQS singular blend");rx*=inv;ry*=inv;rz*=inv;rw*=inv;dx*=inv;dy*=inv;dz*=inv;dw*=inv;float dot=rx*dx+ry*dy+rz*dz+rw*dw;dx-=rx*dot;dy-=ry*dot;dz-=rz*dot;dw-=rw*dot;
        float tx=2*(-dw*rx+dx*rw-dy*rz+dz*ry),ty=2*(-dw*ry+dx*rz+dy*rw-dz*rx),tz=2*(-dw*rz-dx*ry+dy*rx+dz*rw);int i=vertex*8;float x=-(rest[i]+p.pivot().x)/16,y=(rest[i+1]+p.pivot().y)/16,z=(rest[i+2]+p.pivot().z)/16,ax=2*(ry*z-rz*y),ay=2*(rz*x-rx*z),az=2*(rx*y-ry*x);
        out[i]=-(x+rw*ax+ry*az-rz*ay+tx)*16-p.pivot().x;out[i+1]=(y+rw*ay+rz*ax-rx*az+ty)*16-p.pivot().y;out[i+2]=(z+rw*az+rx*ay-ry*ax+tz)*16-p.pivot().z;
    }
    private static float[] floats(JsonArray source){require(source!=null,"Actual numeric array missing");var out=new float[source.size()];for(int i=0;i<out.length;i++){out[i]=source.get(i).getAsFloat();require(Float.isFinite(out[i]),"Nonfinite actual source value");}return out;}
    private static Vector3f vector(JsonArray source){var a=floats(source);require(a.length==3,"Actual vector width");return new Vector3f(a[0],a[1],a[2]);}
    private static void finite(Vector3f p){require(p!=null&&Float.isFinite(p.x)&&Float.isFinite(p.y)&&Float.isFinite(p.z),"Finite actual posed vertex required");}
    private static void unit(Quaternionf q){require(q!=null&&Float.isFinite(q.x)&&Float.isFinite(q.y)&&Float.isFinite(q.z)&&Float.isFinite(q.w)&&Math.abs(q.lengthSquared()-1)<.001F,"Actual unit joint rotation required");}
    /** Account only for saved Euler/float round-trip, not an angular admission
     * margin that could accept a visibly different factory pose. */
    private static boolean sameRotation(Quaternionf a,Quaternionf b)
    {double minus=(double)(a.x-b.x)*(a.x-b.x)+(double)(a.y-b.y)*(a.y-b.y)+(double)(a.z-b.z)*(a.z-b.z)+(double)(a.w-b.w)*(a.w-b.w),plus=(double)(a.x+b.x)*(a.x+b.x)+(double)(a.y+b.y)*(a.y+b.y)+(double)(a.z+b.z)*(a.z+b.z)+(double)(a.w+b.w)*(a.w+b.w);return Math.min(minus,plus)<=1e-12;}
    private static void require(boolean condition,String why){if(!condition)throw new IllegalStateException(why);}
    private EvaOriginalMeshGeometryR52(){}
}

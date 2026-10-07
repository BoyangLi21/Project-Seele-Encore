package com.projectseele.entity;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.util.WeakIdentityMap;
import net.minecraft.util.Mth;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.*;

/** Anatomical finger controls shared by rendering and contact queries.
 * The rig is a private candidate until geometry and weapon contact are admitted.
 */
public final class EvaAnatomicalHandsR45
{
    public static final String OWNER="ANATOMICAL_HANDS_R45";
    public record Joint(String name,String parent,String side,String digit,int index,
                        Vector3f pivot,Vector3f head,Matrix4f inverseBind,
                        Quaternionf neutral,float[][] limits) {}
    public record Grip(Vector3f palm,Vector3f along,Vector3f across,Quaternionf poseRotation,Vector3f poseTranslation) {}
    public record KnifeAttachment(Quaternionf rotation,Vector3f sourceCentre,Vector3f targetCentre,String mesh) {}
    public record KnifePose(Quaternionf rotation,Vector3f position) {}
    public record KnifeMechanism(String bodyMesh,String cover,float openDegrees,String carriage,String actuator,Vector3f presented,float actuatorLength,Vector3f actuatorPin,Vector3f hingeAxis,float storedPitchDegrees,float liftModel) {}
    public record SwordAttachment(KnifeAttachment grip,String meshSha256,Vector3f bladeBase,Vector3f bladeTip,float radius) {}
    public record SwordBladeR45(net.minecraft.world.phys.Vec3 base,net.minecraft.world.phys.Vec3 tip,double radius) {}
    public record CarryFrame(Vector3f along,Vector3f normal) {}
    public record Rig(List<Joint> joints,Map<String,Joint> named,JsonObject poses,Map<String,Grip> grips,KnifeAttachment knife,KnifeMechanism mechanism,SwordAttachment sword,Map<String,CarryFrame> carry) {}
    public record Pose(String left,String right,Map<String,Quaternionf> rotations) {}
    private static final Map<Integer,Optional<Rig>> RIGS=new HashMap<>();
    private static final Map<Integer,String> RIG_FINGERPRINTS_R45=new HashMap<>();
    private static final Map<String,String> SWORD_RESOURCE_HASHES_R45=new HashMap<>();
    private record ContractBytesR45(byte[] bytes,String source) {}
    private static final WeakIdentityMap<EvaUnit01Entity,Memory> STATES=new WeakIdentityMap<>();
    private static final class Memory
    {
        double time=Double.NaN,start;
        String selection="";
        Map<String,float[]> from=Map.of(),target=Map.of(),current=Map.of();
        Map<String,Quaternionf> heldRotations=Map.of();
        boolean holding;
        float thumbClearanceLeftDegrees,thumbClearanceRightDegrees;
        double releaseTime=Double.NaN;
    }
    public static boolean enabled(EvaUnit01Entity eva)
    {
        return !eva.isExperimentalUnit()&&rig(eva.getUnitVariant())!=null;
    }
    private static ContractBytesR45 contractBytesR45(int variant)throws Exception
    {
        String directory=System.getProperty("projectseele.handRigDirectoryR45","");
        if(!directory.isBlank())
        {
            Path file=Path.of(directory,"unit0"+variant,"hand_rig_contract.json");
            // Preserve the explicit private override; do not silently select a JAR rig behind it.
            return Files.isRegularFile(file)?new ContractBytesR45(CombatMotionResourcesR44.read(file,"anatomical-hand-rig-"+variant),file.toAbsolutePath().normalize().toString()):null;
        }
        String name="/assets/projectseele/hand_rigs/unit0"+variant+"/hand_rig_contract.json";
        try(var stream=EvaAnatomicalHandsR45.class.getResourceAsStream(name))
        {return stream==null?null:new ContractBytesR45(stream.readAllBytes(),"classpath:"+name);}
    }
    /** The fingerprint describes the same once-loaded contract used by server contact and client hands. */
    public static synchronized String contractFingerprintR45(int variant)
    {rig(variant);return RIG_FINGERPRINTS_R45.getOrDefault(variant,"ABSENT");}
    public static synchronized Rig rig(int variant)
    {
        return RIGS.computeIfAbsent(variant,key->{
            String source="unresolved unit0"+key;
            try
            {
                var resource=contractBytesR45(key);
                if(resource==null)return Optional.empty();
                source=resource.source();
                String hash=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(resource.bytes()));
                var root=JsonParser.parseString(new String(resource.bytes(),StandardCharsets.UTF_8)).getAsJsonObject();
                if(!Set.of("projectseele.anatomical-hands.r45.v1","projectseele.anatomical-hands.r45.v2").contains(root.get("schema").getAsString()))
                    throw new IllegalArgumentException("Unknown anatomical hand contract schema");
                if(root.get("rig").getAsInt()!=key)throw new IllegalArgumentException("Hand rig identity mismatch");
                Map<String,JsonObject> specs=new HashMap<>();
                for(var value:root.getAsJsonArray("new_bones"))
                {var b=value.getAsJsonObject();specs.put(b.get("name").getAsString(),b);}
                List<Joint> joints=new ArrayList<>();Map<String,Joint> named=new LinkedHashMap<>();
                for(String side:List.of("l","r"))
                    for(var digit:root.getAsJsonObject("hands").getAsJsonObject(side).getAsJsonObject("digits").entrySet())
                        for(var value:digit.getValue().getAsJsonObject().getAsJsonArray("joints"))
                        {
                            var j=value.getAsJsonObject();String name=j.get("name").getAsString();var b=specs.get(name);
                            if(!name.startsWith("r45_hand_"+side+"_")||b==null)throw new IllegalArgumentException("Invalid hand bone: "+name);
                            float[][] limits=new float[3][2];var ranges=j.getAsJsonArray("anatomical_limits_degrees");
                            for(int axis=0;axis<3;axis++)for(int bound=0;bound<2;bound++)limits[axis][bound]=ranges.get(axis).getAsJsonArray().get(bound).getAsFloat();
                            var q=j.getAsJsonArray("neutral_local_quaternion_xyzw");float[] inv=new float[16];
                            for(int i=0;i<16;i++)inv[i]=j.getAsJsonArray("inverse_bind_column_major").get(i).getAsFloat();
                            Joint joint=new Joint(name,b.get("parent").getAsString(),side,digit.getKey(),j.get("index").getAsInt(),
                                    vector(b.getAsJsonArray("pivot")).mul(-1,1,1).div(16),vector(j.getAsJsonArray("head_bind")),new Matrix4f().set(inv),
                                    new Quaternionf(q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat()).normalize(),limits);
                            joints.add(joint);named.put(name,joint);
                        }
                int expected=root.get("schema").getAsString().equals("projectseele.anatomical-hands.r45.v2")?34:30;
                if(joints.size()!=expected||named.size()!=expected)throw new IllegalArgumentException("Hand joint count differs from the admitted schema");
                if(expected==34)for(String side:List.of("l","r"))for(String digit:List.of("ring","little"))
                    if(!named.containsKey("r45_hand_"+side+"_cup_"+digit))throw new IllegalArgumentException("Missing palm cupping joint");

                Map<String,Grip> grips=new HashMap<>();
                for(String channel:List.of("weapon_grip_frames","cannon_grip_frames"))
                if(root.has(channel))for(String side:List.of("l","r"))
                {
                    var frame=root.getAsJsonObject(channel).getAsJsonObject(side);
                    var rotation=new Quaternionf();var translation=new Vector3f();
                    if(frame.has("pose_adjustment_r45"))
                    {
                        var adjustment=frame.getAsJsonObject("pose_adjustment_r45");
                        if(!adjustment.get("space").getAsString().equals("native_model_bind_about_measured_palm"))
                            throw new IllegalArgumentException("Unsupported fitted hand-contact space");
                        var q=adjustment.getAsJsonArray("rotation_xyzw");
                        if(q.size()!=4)throw new IllegalArgumentException("Invalid fitted hand rotation");
                        rotation.set(q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat());
                        translation=vector(adjustment.getAsJsonArray("translation_native"));
                        if(!Float.isFinite(rotation.lengthSquared())||Math.abs(rotation.lengthSquared()-1)>.01F
                                ||!Float.isFinite(translation.lengthSquared())||translation.lengthSquared()>.16F)
                            throw new IllegalArgumentException("Fitted hand-contact transform outside bounded contract");
                        rotation.normalize();
                    }
                    grips.put((channel.equals("cannon_grip_frames")?"cannon_":"")+side,new Grip(vector(frame.getAsJsonArray("palm_bind")),vector(frame.getAsJsonArray("along_bind")),vector(frame.getAsJsonArray("across_bind")),rotation,translation));
                }
                KnifeAttachment knife=null;
                if(root.has("knife_attachment_r45"))
                {
                    var k=root.getAsJsonObject("knife_attachment_r45");var q=k.getAsJsonArray("rotation_xyzw");
                    String mesh=k.get("source_mesh").getAsString().replace('\\','/');
                    mesh=mesh.substring(mesh.lastIndexOf('/')+1);
                    if(!mesh.matches("[a-z0-9_]+\\.mesh\\.json"))throw new IllegalArgumentException("Invalid knife candidate resource");
                    knife=new KnifeAttachment(new Quaternionf(q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat()).normalize(),
                            vector(k.getAsJsonArray("source_handle_centre")),vector(k.getAsJsonArray("target_handle_centre")),mesh);
                }
                KnifeMechanism mechanism=null;
                if(root.has("knife_mechanism_r45"))
                {
                    var k=root.getAsJsonObject("knife_mechanism_r45");String mesh=k.get("body_mesh").getAsString();
                    if(!mesh.matches("eva_unit0[012]_knife_cage_r45\\.mesh\\.json"))throw new IllegalArgumentException("Invalid knife cage resource");
                    var bone=k.getAsJsonArray("bones").get(0).getAsJsonObject();
                    var bones=k.getAsJsonArray("bones");boolean carrier=bones.size()>=3;
                    mechanism=new KnifeMechanism(mesh,bone.get("name").getAsString(),k.get("hinge_native_degrees").getAsFloat(),
                            carrier?bones.get(1).getAsJsonObject().get("name").getAsString():"",carrier?bones.get(2).getAsJsonObject().get("name").getAsString():"",
                            carrier?vector(k.getAsJsonArray("presented_authored")):new Vector3f(),carrier?k.get("actuator_length").getAsFloat():1,
                            k.has("carriage_actuator_offset_authored")?vector(k.getAsJsonArray("carriage_actuator_offset_authored")):new Vector3f(0,-5,6),
                            k.has("hinge_axis_native")?vector(k.getAsJsonArray("hinge_axis_native")).normalize():new Vector3f(1,0,0),
                            k.has("carriage_stored_pitch_degrees")?k.get("carriage_stored_pitch_degrees").getAsFloat():0,
                            k.has("carriage_lift_model")?k.get("carriage_lift_model").getAsFloat():0);
                }
                SwordAttachment sword=null;
                if(root.has("sword_attachment_r45"))
                {
                    var k=root.getAsJsonObject("sword_attachment_r45");var q=k.getAsJsonArray("rotation_xyzw");
                    String mesh=k.get("source_mesh").getAsString().replace('\\','/');mesh=mesh.substring(mesh.lastIndexOf('/')+1);
                    String expectedHash=k.get("source_mesh_sha256").getAsString();
                    if(key!=2||!"lance".equals(k.get("mesh_part").getAsString())||!"r".equals(k.get("grip_side").getAsString())
                            ||!"eva02_longsword.mesh.json".equals(mesh)||!expectedHash.matches("[a-f0-9]{64}"))
                        throw new IllegalArgumentException("Invalid independent Unit02 sword binding");
                    var rotation=new Quaternionf(q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat());
                    var sourceCentre=vector(k.getAsJsonArray("source_handle_centre"));var targetCentre=vector(k.getAsJsonArray("target_handle_centre"));
                    if(!Float.isFinite(rotation.lengthSquared())||Math.abs(rotation.lengthSquared()-1)>.01F
                            ||!Float.isFinite(sourceCentre.lengthSquared())||!Float.isFinite(targetCentre.lengthSquared()))
                        throw new IllegalArgumentException("Nonfinite or unnormalized sword attachment");
                    var bladeBase=vector(k.getAsJsonArray("blade_base_bind"));var bladeTip=vector(k.getAsJsonArray("blade_tip_bind"));
                    float radius=k.get("blade_radius_native").getAsFloat();
                    if(!Float.isFinite(bladeBase.lengthSquared())||!Float.isFinite(bladeTip.lengthSquared())
                            ||bladeBase.distance(bladeTip)<1||bladeBase.distance(bladeTip)>20||!Float.isFinite(radius)||radius<=0||radius>1)
                        throw new IllegalArgumentException("Invalid measured sword blade segment");
                    sword=new SwordAttachment(new KnifeAttachment(rotation.normalize(),sourceCentre,targetCentre,mesh),expectedHash,bladeBase,bladeTip,radius);
                }
                RIG_FINGERPRINTS_R45.put(key,hash);
                ProjectSeele.LOGGER.info("R45 anatomical hand contract resolved: variant={} source={} sha256={}",key,source,hash);
                Map<String,CarryFrame> carry=new HashMap<>();
                for(String side:List.of("l","r"))
                {
                    var hand=root.getAsJsonObject("hands").getAsJsonObject(side);
                    var along=vector(hand.getAsJsonArray("longitudinal_bind")).normalize();
                    var normal=vector(hand.getAsJsonArray("palmar_normal_bind"));normal.fma(-normal.dot(along),along).normalize();
                    if(!Float.isFinite(along.lengthSquared())||!Float.isFinite(normal.lengthSquared()))throw new IllegalArgumentException("Invalid natural hand frame");
                    carry.put(side,new CarryFrame(along,normal));
                }
                return Optional.of(new Rig(List.copyOf(joints),Map.copyOf(named),root.getAsJsonObject("pose_controls"),Map.copyOf(grips),knife,mechanism,sword,Map.copyOf(carry)));
            }
            catch(Exception error){throw new IllegalStateException("Rejected hand rig "+source,error);}
        }).orElse(null);
    }
    private static Vector3f vector(JsonArray a)
    {return new Vector3f(a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat());}
    public static KnifeAttachment knifeAttachment(EvaUnit01Entity e)
    {return enabled(e)?rig(e.getUnitVariant()).knife():null;}
    public static KnifeMechanism knifeMechanism(EvaUnit01Entity e)
    {return enabled(e)?rig(e.getUnitVariant()).mechanism():null;}
    public static KnifePose knifePose(EvaUnit01Entity e,Vector3f pivot,Quaternionf authored)
    {
        var k=knifeAttachment(e);if(k==null)return null;
        // Legacy knife clips contain the OLD grip basis (-90deg X, +12deg Z)
        // and even independent knife swings. New hand contacts already encode
        // their complete grip basis: composing those old offsets rotates the
        // handle through the fingers. The hand owns this rigid attachment.
        // A separately authored regrip must supply its own admitted hand pose;
        // the legacy reverse-knife flip is not a valid regrip for this rig.
        var rotation=new Quaternionf(k.rotation);
        var position=new Vector3f(k.targetCentre).sub(pivot)
                .sub(rotation.transform(new Vector3f(k.sourceCentre).sub(pivot)));
        return new KnifePose(rotation,position);
    }
    public static void attachKnife(EvaUnit01Entity e,EvaBodyPose.Sample body)
    {
        if((e.getWeapon()!=EvaUnit01Entity.WEAPON_KNIFE&&!EvaWeaponHandlingR45.active(e))||!body.rig.containsKey("knife"))return;
        var pose=knifePose(e,body.rig.get("knife").pivot(),body.rotations.get("knife"));if(pose==null)return;
        body.rotations.put("knife",pose.rotation);body.positions.put("knife",pose.position);body.dirty();
    }
    public static synchronized boolean swordAttachmentReadyR45(EvaUnit01Entity e)
    {
        if(e.isExperimentalUnit()||e.getUnitVariant()!=2||!enabled(e))return false;
        var sword=rig(2).sword();if(sword==null||!rig(2).poses().has("sword_right"))return false;
        String actual=SWORD_RESOURCE_HASHES_R45.computeIfAbsent(sword.grip().mesh(),name->{
            try(var stream=EvaAnatomicalHandsR45.class.getResourceAsStream("/assets/projectseele/mesh/"+name))
            {return stream==null?"ABSENT":HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(stream.readAllBytes()));}
            catch(Exception error){throw new IllegalStateException("Cannot verify common sword geometry",error);}
        });
        return actual.equals(sword.meshSha256());
    }

    public static boolean shieldAttachmentReadyR45(EvaUnit01Entity e)
    {
        return !e.isExperimentalUnit()&&e.getUnitVariant()==0&&enabled(e)
                &&EvaBodyPose.neutralForTransportR32(e).rig.containsKey("shield")
                &&EvaAnatomicalHandsR45.class.getResource("/assets/projectseele/mesh/yashima_shield.mesh.json")!=null;
    }
    /** Natural empty-hand carry is a base-pose adjustment. Actions and weapon
     * grips are composed afterwards, so release blending keeps its real origin. */
    public static void naturalCarryR45(EvaUnit01Entity e,EvaBodyPose.Sample body,float partial)
    {
        if(!enabled(e)||e.getWeapon()!=EvaUnit01Entity.WEAPON_FISTS||e.isBerserk()||!e.isPoweredOn()
                ||e.isNervLogisticsLocked()||e.isFirstBattleActive()||EvaShutdownR30.disabled(e)
                ||e.isVisuallyAirborneForRender()||e.getActivationTicks()>0)return;
        float low=Mth.clamp(e.rifleStanceLevel(partial)/.75F,0,1),weight=1-low*low*(3-2*low);
        if(weight<=0)return;
        for(String side:List.of("l","r"))
        {
            String hand="hand_"+side,forearm="forearm_"+side;
            if(!body.rig.containsKey(hand)||!body.rig.containsKey(forearm))continue;
            var frame=rig(e.getUnitVariant()).carry().get(side);
            var along=body.matrix(forearm).transformDirection(new Vector3f(body.rig.get(hand).pivot()).sub(body.rig.get(forearm).pivot())).normalize();
            var inward=body.matrix("torso_upper").transformDirection(new Vector3f(side.equals("l")?1:-1,0,0));
            inward.fma(-inward.dot(along),along);
            if(inward.lengthSquared()<1e-6F)continue;inward.normalize();
            // The measured palm axis used to inherit an oblique old wrist frame:
            // fingers pointed forward roughly fifty degrees even at rest.
            // Follow the forearm, with only a small relaxed palmar bend.
            along.mul((float)Math.cos(5*Mth.DEG_TO_RAD)).fma((float)Math.sin(5*Mth.DEG_TO_RAD),inward).normalize();
            inward.fma(-inward.dot(along),along).normalize();
            var source=new org.joml.Matrix3f().setColumn(0,frame.normal()).setColumn(1,frame.along())
                    .setColumn(2,new Vector3f(frame.normal()).cross(frame.along()));
            var target=new org.joml.Matrix3f().setColumn(0,inward).setColumn(1,along)
                    .setColumn(2,new Vector3f(inward).cross(along));
            var desired=new Quaternionf().setFromNormalized(target.mul(source.transpose())).normalize();
            String parent=body.rig.get(hand).parent();
            if(parent!=null)desired=body.matrix(parent).getUnnormalizedRotation(new Quaternionf()).normalize().invert().mul(desired);
            body.rotations.get(hand).slerp(desired,weight);body.dirty();
        }
    }
    public static void attachSwordR45(EvaUnit01Entity e,EvaBodyPose.Sample body)
    {
        if(e.getWeapon()!=EvaUnit01Entity.WEAPON_SWORD_R45||!swordAttachmentReadyR45(e))return;
        if(!body.rig.containsKey("lance")||!body.rig.containsKey("hand_r"))throw new IllegalStateException("Sword socket is absent from the actual rig");
        var attachment=rig(2).sword().grip();var socket=body.rig.get("lance");
        // The old lance parent is not the hand. Rebase the entire fitted rigid weapon
        // through the actual parent so this cannot recreate the chest-mounted sword.
        Matrix4f fitted=new Matrix4f(body.matrix("hand_r")).translate(attachment.targetCentre())
                .rotate(attachment.rotation()).translate(new Vector3f(attachment.sourceCentre()).negate());
        Matrix4f parent=socket.parent()==null?new Matrix4f():new Matrix4f(body.matrix(socket.parent()));
        Matrix4f local=parent.invert().mul(fitted);
        body.rotations.put("lance",local.getUnnormalizedRotation(new Quaternionf()).normalize());
        body.positions.put("lance",local.transformPosition(new Vector3f(socket.pivot())).sub(socket.pivot()));body.dirty();
    }
    public static SwordBladeR45 swordBladeWorldR45(EvaUnit01Entity e,float partial)
    {
        if(e.getWeapon()!=EvaUnit01Entity.WEAPON_SWORD_R45||!swordAttachmentReadyR45(e))return null;
        var sword=rig(2).sword();var pose=EvaBodyPose.sample(e,partial);
        var world=new Matrix4f(EvaRifleKinematics.world(e,partial)).mul(pose.matrix("lance"));
        var base=world.transformPosition(new Vector3f(sword.bladeBase()));var tip=world.transformPosition(new Vector3f(sword.bladeTip()));
        return new SwordBladeR45(new net.minecraft.world.phys.Vec3(base.x,base.y,base.z),
                new net.minecraft.world.phys.Vec3(tip.x,tip.y,tip.z),sword.radius()*EvaScale.RENDER_SCALE);
    }
    public static Quaternionf rotation(Joint j,float flex,float twist,float splay)
    {
        flex=Mth.clamp(flex,j.limits[0][0],j.limits[0][1]);
        twist=Mth.clamp(twist,j.limits[1][0],j.limits[1][1]);
        splay=Mth.clamp(splay,j.limits[2][0],j.limits[2][1]);
        float side=j.side.equals("l")?1:-1;
        return new Quaternionf(j.neutral).mul(new Quaternionf().rotationZYX(side*splay*Mth.DEG_TO_RAD,side*twist*Mth.DEG_TO_RAD,-flex*Mth.DEG_TO_RAD)).normalize();
    }
    private static String selection(EvaUnit01Entity e,String side)
    {
        String forced=System.getProperty("projectseele.handPoseR45","");
        if(!forced.isBlank())return forced;
        if(e.isFirstBattleActive())
        {
            float time=e.firstBattleSignals().time(e,0);
            if(time>=FirstBattleClip.DEATH_TICK/20F)return "relaxed";
            if(time>=16.3F)return "grab";
            if(time>=11.05F)return side.equals("r")?"fist":"support";
            return time>=5.1F?"grab":"spread";
        }
        if(EvaWeaponHandlingR45.active(e))return side.equals("r")?"knife":"relaxed";
        if(side.equals("r")&&e.getWeapon()==EvaUnit01Entity.WEAPON_KNIFE&&EvaWeaponHandlingR45.available(e))return "knife";
        if(e.isNervLogisticsLocked()||EvaShutdownR30.disabled(e))return "relaxed";
        if(e.isBerserk()&&!EvaBerserkMotionR34.silent(e))
            return EvaBerserkMotionR34.introduction(e)?"spread":EvaBerserkMotionR34.striking(e)?"grab":"relaxed";
        if(!e.isPoweredOn())return "relaxed";
        if(EvaMarineBraceR50.target(e)!=null)return "support";
        if(e.getWeapon()==EvaUnit01Entity.WEAPON_SWORD_R45)return side.equals("r")?"sword_right":"relaxed";
        if(e.getWeapon()==EvaUnit01Entity.WEAPON_SHIELD_R45)return side.equals("l")?"knife":"relaxed";
        if(EvaFieldActionsR45.active(e)&&e.getWeapon()==EvaUnit01Entity.WEAPON_FISTS)return "relaxed";
        if(e.getWeapon()==EvaUnit01Entity.WEAPON_CANNON&&rig(e.getUnitVariant()).poses.has("cannon_"+(side.equals("r")?"right":"left")))
            return "cannon_"+(side.equals("r")?"right":"left");
        if(e.getWeapon()==EvaUnit01Entity.WEAPON_RIFLE||e.getWeapon()==EvaUnit01Entity.WEAPON_CANNON)
            return side.equals("r")?"rifle_right":"rifle_left";
        if(e.getWeapon()==EvaUnit01Entity.WEAPON_KNIFE&&side.equals("r"))return "knife";
        if(e.getWeapon()==EvaUnit01Entity.WEAPON_LANCE||e.getWeapon()==EvaUnit01Entity.WEAPON_N2)return "grab";
        if(EvaCombatR31.action(e)==EvaCombatR31.REACH)return "spread";
        if(EvaCombatR31.action(e)==EvaCombatR31.HOLD||EvaCombatR31.action(e)==EvaCombatR31.THROW)return "grab";
        // A released crouch/prone key does not mean the palms have left the
        // floor. Keep the support hand through the actual get-up capture.
        if(e.isPilotProne()||EvaCapturedLocomotionR44.ownsMultiContactPoseR45(e))
        {
            String strike=EvaGameplayMotionR32.activeGroundClip(e,0);
            if(!strike.isEmpty()&&!strike.equals("kick")&&EvaGameplayMotionR32.side(e,strike).equals(side))return "fist";
            return "support";
        }
        if(e.hasLiveActionForRender(0)||!e.pilotLocomotionRequestedR45()&&EvaGameplayMotionR32.guardWeight(e)>.12F)return "fist";
        return "relaxed";
    }
    private static Map<String,float[]> controls(Rig rig,String left,String right)
    {
        Map<String,float[]> values=new LinkedHashMap<>();
        for(Joint j:rig.joints)
        {
            var p=rig.poses.getAsJsonObject(j.side.equals("l")?left:right);
            if(p==null)throw new IllegalArgumentException("Unknown anatomical hand pose");
            float[] v=new float[3];JsonArray explicit=null;
            if(p.has("bone_angles")&&p.getAsJsonObject("bone_angles").has(j.name))explicit=p.getAsJsonObject("bone_angles").getAsJsonArray(j.name);
            else if(j.digit.equals("thumb"))explicit=p.getAsJsonArray("thumb").get(j.index).getAsJsonArray();
            if(explicit!=null)for(int i=0;i<3;i++)v[i]=explicit.get(i).getAsFloat();
            else
            {
                v[0]=p.getAsJsonArray(p.has(j.digit)?j.digit:"fingers").get(j.index).getAsFloat();
                if(j.index==0&&p.has("splay")&&p.getAsJsonObject("splay").has(j.digit))v[2]=p.getAsJsonObject("splay").get(j.digit).getAsFloat();
            }
            for(int i=0;i<3;i++)v[i]=Mth.clamp(v[i],j.limits[i][0],j.limits[i][1]);values.put(j.name,v);
        }
        return values;
    }
    public static Pose sample(EvaUnit01Entity e,float partial)
    {
        Rig rig=rig(e.getUnitVariant());String left=selection(e,"l"),right=selection(e,"r");
        Map<String,float[]> wanted=controls(rig,left,right);
        if(System.getProperty("projectseele.handPoseR45","").isBlank()
                &&e.getWeapon()==EvaUnit01Entity.WEAPON_FISTS&&!e.isPilotProne()
                &&!e.isNervLogisticsLocked()&&e.isPoweredOn())
        {
            if(rig.poses.has("locomotion_walk")&&rig.poses.has("locomotion_run"))
            {
                var walking=controls(rig,"locomotion_walk","locomotion_walk");
                var running=controls(rig,"locomotion_run","locomotion_run");
                float move=Mth.clamp(e.rifleMoveBlend(partial),0,1),run=Mth.clamp(e.rifleRunBlend(partial),0,1);
                move=move*move*(3-2*move);run=run*run*(3-2*run);
                for(Joint joint:rig.joints)
                    if((joint.side.equals("l")?left:right).equals("relaxed"))
                        for(int i=0;i<3;i++)wanted.get(joint.name)[i]=Mth.lerp(move,wanted.get(joint.name)[i],
                                Mth.lerp(run,walking.get(joint.name)[i],running.get(joint.name)[i]));
            }
            else
            {
                // Retain the old profile's behaviour until its separate
                // locomotion hand controls have been authored and reviewed.
                float closure=.72F*Mth.clamp(e.rifleRunBlend(partial),0,1);
                if(closure>0)
                {
                    var fist=controls(rig,"fist","fist");
                    for(Joint joint:rig.joints)
                        if((joint.side.equals("l")?left:right).equals("relaxed"))
                            for(int i=0;i<3;i++)wanted.get(joint.name)[i]=Mth.lerp(closure,wanted.get(joint.name)[i],fist.get(joint.name)[i]);
                }
            }
        }
        if(EvaWeaponHandlingR45.active(e))
        {
            var opened=controls(rig,"relaxed",rig.poses.has("knife_approach")?"knife_approach":"open");
            for(Joint joint:rig.joints)if(joint.side.equals("r"))
                for(int i=0;i<3;i++)wanted.get(joint.name)[i]=Mth.lerp(EvaWeaponHandlingR45.jointClosure(e,joint.digit,joint.index,partial),opened.get(joint.name)[i],wanted.get(joint.name)[i]);
        }
        if(e.getWeapon()==EvaUnit01Entity.WEAPON_RIFLE&&System.getProperty("projectseele.handPoseR45","").isBlank()
                &&EvaBodyPose.hasSupportedStances())
        {
            float stance=e.rifleStanceLevel(partial);
            float support=stance>1&&stance<3?(float)Math.pow(Math.sin((stance-1)*Math.PI/2),2):0;
            support=supportFingerOpenR45(support);
            if(support>0)
            {
                var open=controls(rig,"support",right);
                for(Joint joint:rig.joints)if(joint.side.equals("l"))
                {
                    float[] value=wanted.get(joint.name),target=open.get(joint.name);
                    for(int i=0;i<3;i++)value[i]=Mth.lerp(support,value[i],target[i]);
                }
            }
        }
        double time=(double)e.level().getGameTime()+(e.level().isClientSide?partial:0);Memory state=STATES.get(e);
        if(state==null){state=new Memory();STATES.put(e,state);}
        if(EvaShutdownR30.displaysCapturedPoseR45(e))
        {
            var stored=EvaShutdownR30.pose(e);Map<String,Quaternionf> held=new LinkedHashMap<>();
            for(Joint joint:rig.joints)
            {
                var values=stored.getList(joint.name,net.minecraft.nbt.Tag.TAG_FLOAT);
                if(values.size()==9)
                    held.put(joint.name,new Quaternionf().rotationZYX(values.getFloat(2),values.getFloat(1),values.getFloat(0)));
                else if(state.heldRotations.containsKey(joint.name))
                    held.put(joint.name,new Quaternionf(state.heldRotations.get(joint.name)));
                else
                {
                    // Before the final client snapshot arrives, retain the last
                    // actual finger controls. Legacy saves without these bones
                    // cannot reconstruct an unrecorded anatomical hand pose.
                    var value=state.current.getOrDefault(joint.name,wanted.get(joint.name));
                    held.put(joint.name,rotation(joint,value[0],value[1],value[2]));
                }
            }
            state.heldRotations=Map.copyOf(held);state.holding=true;state.releaseTime=Double.NaN;state.time=time;
            return new Pose("frozen","frozen",state.heldRotations);
        }
        if(state.holding){state.holding=false;state.releaseTime=time;}
        {
            String key=left+":"+right;
            if(state.current.isEmpty()||time<state.time)
            {state.target=wanted;state.current=state.target;state.from=state.target;state.start=time;state.selection=key;}
            else if(!key.equals(state.selection))
            {
                float clearance=rig.poses.has("locomotion_run")
                        &&rig.poses.getAsJsonObject("locomotion_run").has("fist_thumb_clearance_degrees")
                        ?Mth.clamp(rig.poses.getAsJsonObject("locomotion_run").get("fist_thumb_clearance_degrees").getAsFloat(),0,20):0;
                state.thumbClearanceLeftDegrees=(state.selection.startsWith("relaxed:")&&left.equals("fist")
                        ||state.selection.startsWith("fist:")&&left.equals("relaxed"))?clearance:0;
                state.thumbClearanceRightDegrees=(state.selection.endsWith(":relaxed")&&right.equals("fist")
                        ||state.selection.endsWith(":fist")&&right.equals("relaxed"))?clearance:0;
                state.from=state.current;state.target=wanted;state.start=time;state.selection=key;
                // A late first draw must not restart an equip transition the
                // server has already completed. Native frame4299410 had a
                // ready-to-fire rifle but both hands still exactly relaxed.
                // This reconciles an already-held weapon; the actual pickup
                // performance remains a separate equipment animation.
                if(e.getWeapon()==EvaUnit01Entity.WEAPON_RIFLE&&left.equals("rifle_left")&&right.equals("rifle_right")
                        &&e.rifleHeldPoseReadinessR45(partial)>=.999F)state.start=time-4;
            }
            else state.target=wanted;
            float t=Mth.clamp((float)(time-state.start)/4,0,1);t=t*t*t*(10+t*(-15+6*t));
            Map<String,float[]> next=new LinkedHashMap<>();
            for(Joint j:rig.joints)
            {
                float[] v=new float[3];for(int i=0;i<3;i++)v[i]=Mth.lerp(t,state.from.get(j.name)[i],state.target.get(j.name)[i]);
                if(j.digit.equals("thumb")&&j.index==0)
                    v[2]+=(j.side.equals("l")?state.thumbClearanceLeftDegrees:state.thumbClearanceRightDegrees)*(float)Math.sin(Math.PI*t);
                next.put(j.name,v);
            }
            state.current=next;
        }
        state.time=time;Map<String,Quaternionf> rotations=new LinkedHashMap<>();
        for(Joint j:rig.joints)
        {float[] v=state.current.get(j.name);rotations.put(j.name,rotation(j,v[0],v[1],v[2]));}
        if(!state.heldRotations.isEmpty()&&Double.isFinite(state.releaseTime))
        {
            float blend=Mth.clamp((float)(time-state.releaseTime)/4,0,1);
            blend=blend*blend*(3-2*blend);
            for(var entry:state.heldRotations.entrySet())
                if(rotations.containsKey(entry.getKey()))
                    rotations.put(entry.getKey(),new Quaternionf(entry.getValue()).slerp(rotations.get(entry.getKey()),blend));
            if(blend>=1)state.heldRotations=Map.of();
        }
        return new Pose(left,right,Map.copyOf(rotations));
    }
    public static float supportPalmTurnR45(float travel)
    {
        float clear=Mth.clamp((travel-.35F)/.65F,0,1);
        return clear*clear*(3-2*clear);
    }
    public static float supportFingerOpenR45(float travel)
    {
        float open=Mth.clamp(travel/.20F,0,1);
        return open*open*(3-2*open);
    }
    public static float supportPalmTravelR45(float travel)
    {
        float clear=Mth.clamp((travel-.20F)/.80F,0,1);
        return clear*clear*(3-2*clear);
    }
    public static float supportGunClearanceR45(float travel)
    {
        // Full native-mesh sweep: opening in place cuts the foregrip; a
        // simultaneous .50m retreat clears all 41 sampled finger poses.
        // Use .60m and fade into the existing floor reach, reversing the
        // same path when the hand returns. Never move the weapon to follow.
        return .60F*supportFingerOpenR45(travel)*(1-supportPalmTravelR45(travel));
    }
    public static Vector3f contact(EvaUnit01Entity e,EvaBodyPose.Sample body,String side,float partial)
    {
        var rig=rig(e.getUnitVariant());var pose=sample(e,partial);Map<String,Matrix4f> matrices=new HashMap<>();
        Vector3f a=point(rig,pose,body,"r45_hand_"+side+"_index_2",matrices);
        Vector3f b=point(rig,pose,body,"r45_hand_"+side+"_middle_2",matrices);
        return a.lerp(b,.5F);
    }
    private static Vector3f point(Rig rig,Pose pose,EvaBodyPose.Sample body,String bone,Map<String,Matrix4f> cache)
    {Joint j=rig.named.get(bone);return matrix(rig,pose,body,bone,cache).mul(j.inverseBind).transformPosition(new Vector3f(j.head));}
    private static Matrix4f matrix(Rig rig,Pose pose,EvaBodyPose.Sample body,String name,Map<String,Matrix4f> cache)
    {
        if(!rig.named.containsKey(name))return body.matrix(name);
        if(cache.containsKey(name))return new Matrix4f(cache.get(name));
        Joint j=rig.named.get(name);var p=j.pivot;
        var m=matrix(rig,pose,body,j.parent,cache).translate(p).rotate(pose.rotations.get(name)).translate(-p.x,-p.y,-p.z);
        cache.put(name,m);return new Matrix4f(m);
    }
    private EvaAnatomicalHandsR45(){}
}

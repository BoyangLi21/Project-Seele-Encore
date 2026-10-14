package com.projectseele.world;
import com.google.gson.*;
import com.projectseele.entity.*;
import java.io.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import java.util.zip.GZIPOutputStream;
import net.minecraft.world.phys.*;
import net.minecraft.util.Mth;
import org.joml.Quaternionf;

/** Explicit canonical seated binding; an identity transform is forbidden for this occupied fixture. */
public final class ExportActualSeatedPlugR53
{
    static String sha(Path p)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(p)));}
    public static void main(String[] args)throws Exception
    {
        Path bodySource=Path.of(args[0]),profileSource=Path.of(args[1]),out=Path.of(args[2]);Files.createDirectories(out);System.setProperty("projectseele.dorsalPoseReview",profileSource.toAbsolutePath().toString());
        FullAssemblyGeometryR52.installClasspath();NervMappedPlugMechanicsR52.install();var field=FullAssemblyGeometryR52.class.getDeclaredField("installed");field.setAccessible(true);var full=(FullAssemblyGeometryR52.Provider)field.get(null);var maker=EvaOriginalMeshGeometryR52Test.class.getDeclaredMethod("body",JsonObject.class,int.class);maker.setAccessible(true);var data=JsonParser.parseString(Files.readString(bodySource)).getAsJsonObject();var vertical=EntryPlugKinematics.class.getDeclaredMethod("verticalSocketOrientation",Vec3.class,EvaDorsalProfile.Profile.class);vertical.setAccessible(true);var rearMethod=EntryPlugKinematics.class.getDeclaredMethod("rearDirectionForYaw",float.class);rearMethod.setAccessible(true);var rows=new ArrayList<Object>();
        for(int v=0;v<3;v++)
        {
            var body=(EvaBodyPose.Sample)maker.invoke(null,data,v);var profile=EvaDorsalProfile.byVariant(v);var world=EvaRifleKinematics.frameWorldR52(Vec3.ZERO,0);var posed=EvaMechanicalFrameMathR52.emptySocket(body,world,profile);var rear=(Vec3)rearMethod.invoke(null,0F);var orient=(RigidTransform)vertical.invoke(null,rear,profile);var marker=profile.centreBlocks();var socketOrigin=rear.scale(marker.z).add(rear.cross(new Vec3(0,1,0)).scale(marker.x)).add(0,marker.y,0);var socket=new RigidTransform(socketOrigin,orient.qx(),orient.qy(),orient.qz(),orient.qw());var canonical=socket.compose(RigidTransform.of(new Vec3(0,0,-EntryPlugKinematics.LOCK_DEPTH_BLOCKS),new Quaternionf()));
            double translationDifference=canonical.translation().distanceTo(posed.translation()),rotationDifference=canonical.rotationErrorDegrees(posed);if(translationDifference>1e-4||rotationDifference>.001)throw new AssertionError("Prepared posed-chest/socket and actual plant locked branch disagree "+v+" translation="+translationDifference+" rotation="+rotationDifference);
            var basis=RigidTransform.of(Vec3.ZERO,new Quaternionf().rotationY(180*Mth.DEG_TO_RAD));var local=basis.inverse().compose(canonical);if(local.translation().length()<10)throw new AssertionError("Occupied plug fixture cannot use identity/origin binding");var feet=NervOriginalCarrierR52.nominalBinding(v);var desired=RigidTransform.of(Vec3.ZERO,new Quaternionf(0,1,0,0));desired=new RigidTransform(desired.transformVector(feet.contactCentre()).scale(-1),desired.qx(),desired.qy(),desired.qz(),desired.qw());var placed=desired.compose(local);var parts=full.closedPlugParts(v);AABB bounds=null;
            Path binary=out.resolve("ACTUAL_SEATED_CLOSED_PLUG.variant"+v+".bin.gz");try(var stream=new DataOutputStream(new GZIPOutputStream(Files.newOutputStream(binary)))){stream.writeInt(parts.size());for(var p:parts.entrySet()){stream.writeUTF("plug/"+p.getKey());stream.writeUTF("PLUG");stream.writeInt(p.getValue().length);var a=p.getValue();for(int i=0;i<a.length;i+=3){var q=placed.transformPoint(new Vec3(a[i],a[i+1],a[i+2]));stream.writeDouble(q.x);stream.writeDouble(q.y);stream.writeDouble(q.z);bounds=bounds==null?new AABB(q,q):bounds.minmax(new AABB(q,q));}}}
            var matrix=new float[16];new org.joml.Matrix4f(world).mul(body.matrix("torso_upper")).get(matrix);var row=new LinkedHashMap<String,Object>();row.put("variant",v);row.put("selected_profile",profile);row.put("posed_chest_world_matrix_column_major",matrix);row.put("actual_plant_socket",socket);row.put("canonical_locked_world_at_entity_origin",canonical);row.put("independent_posed_locked_world",posed);row.put("branch_translation_difference_m",translationDifference);row.put("branch_rotation_difference_degrees",rotationDifference);row.put("plug_in_eva_local",local);row.put("foot_normalized_world_yaw180_placed_frame",placed);row.put("actual_closed_plug_bounds",bounds);row.put("source",binary.toAbsolutePath().toString());row.put("source_sha256",sha(binary));rows.add(row);System.out.println("Actual seated plug variant="+v+" local="+local+" bounds="+bounds);
        }
        var report=new LinkedHashMap<String,Object>();report.put("world_written",false);report.put("game_started",false);report.put("lock_depth_m",EntryPlugKinematics.LOCK_DEPTH_BLOCKS);report.put("body_pose_source",bodySource.toAbsolutePath().toString());report.put("body_pose_sha256",sha(bodySource));report.put("dorsal_profile_source",profileSource.toAbsolutePath().toString());report.put("dorsal_profile_sha256",sha(profileSource));report.put("full_assembly_source_sha256",NervOriginalCarrierR52.SOURCE_SHA);report.put("variants",rows);report.put("scope","Current selected delivered dorsal profile, current prepared factory chest pose, actual canonical verticalSocketOrientation and LOCK_DEPTH11 branch, independently compared with the production posed-chest emptySocket helper. Original actual closed plug vertices are placed by nonidentity plugInEva and normalized to true foot midpoint. Geometry fixture only; not a claim that occupied runtime capture has already been commissioned.");Files.writeString(out.resolve("ACTUAL_SEATED_PLUG_BINDING_RECEIPT.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));
    }
}

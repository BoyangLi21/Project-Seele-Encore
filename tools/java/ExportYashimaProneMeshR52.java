package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.*;
import java.nio.file.*;
import java.util.*;
import java.io.*;
import java.util.zip.GZIPOutputStream;
import org.joml.*;

/** Exact selected body/hand skin evaluator driven by actual native local bone/finger readback. No world writing. */
public final class ExportYashimaProneMeshR52
{
    private static Vector3f vec(JsonArray a){return new Vector3f(a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat());}
    private static Quaternionf quat(JsonArray a){return new Quaternionf(a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat(),a.get(3).getAsFloat());}
    public static void main(String[] args)throws Exception
    {
        Path assets=Path.of(args[0]),out=Path.of(args[4]);java.util.zip.ZipFile jar=Files.isRegularFile(assets)?new java.util.zip.ZipFile(assets.toFile()):null;
        String receiptText=args[1].equals("jar")?new String(jar.getInputStream(jar.getEntry("assets/projectseele/eva/eva_original_mesh_geometry_r52_sources.json")).readAllBytes(),java.nio.charset.StandardCharsets.UTF_8):Files.readString(Path.of(args[1]));
        var receipt=JsonParser.parseString(receiptText).getAsJsonObject();var hashes=new LinkedHashMap<String,String>();
        if(receipt.has("resources"))for(var e:receipt.getAsJsonObject("resources").entrySet())hashes.put(e.getKey(),e.getValue().getAsString());
        else for(var raw:receipt.getAsJsonArray("files")){var row=raw.getAsJsonObject();hashes.put(row.get("resource").getAsString(),row.get("sha256").getAsString());}
        var capture=JsonParser.parseString(Files.readString(Path.of(args[2]))).getAsJsonObject();var extra=JsonParser.parseString(Files.readString(Path.of(args[3]))).getAsJsonObject();
        var rig=new LinkedHashMap<String,EvaBodyPose.Bone>();
        for(var e:extra.getAsJsonObject("actual_local_bones").entrySet()){var row=e.getValue().getAsJsonObject();rig.put(e.getKey(),new EvaBodyPose.Bone(e.getKey(),row.has("parent")?row.get("parent").getAsString():null,vec(row.getAsJsonArray("pivot")),new Quaternionf()));}
        var pose=new EvaBodyPose.Sample(Map.copyOf(rig));
        // The main capture owns the exact same-frame FK and hand contacts. The later
        // extra capture supplies parent/pivot definitions only; mixing its changing
        // idle-arm state with the earlier contacts invents an enormous palm offset.
        var nativeMatrices=new HashMap<String,Matrix4f>();
        for(var e:capture.getAsJsonObject("bones").entrySet())
        {var a=e.getValue().getAsJsonObject().getAsJsonArray("matrix");var v=new float[16];for(int i=0;i<16;i++)v[i]=a.get(i).getAsFloat();nativeMatrices.put(e.getKey(),new Matrix4f().set(v));}
        for(var bone:rig.values())
        {
            var local=new Matrix4f(nativeMatrices.get(bone.name()));if(bone.parent()!=null)local=new Matrix4f(nativeMatrices.get(bone.parent())).invert().mul(local);
            var rotation=local.getUnnormalizedRotation(new Quaternionf()).normalize();var position=local.getTranslation(new Vector3f())
                    .sub(bone.pivot()).add(rotation.transform(new Vector3f(bone.pivot())));
            pose.rotations.put(bone.name(),rotation);pose.positions.put(bone.name(),position);
        }pose.dirty();
        float matrixError=0;for(var entry:nativeMatrices.entrySet())
        {var a=entry.getValue().get(new float[16]);var b=pose.matrix(entry.getKey()).get(new float[16]);for(int i=0;i<16;i++)matrixError=java.lang.Math.max(matrixError,java.lang.Math.abs(a[i]-b[i]));}
        if(matrixError>2e-5F)throw new IllegalStateException("Same native FK did not reconstruct: "+matrixError);
        // The approved production correction changes only the leg hinge
        // swivel and counter-rotates the original complete shoe matrices.
        EvaProneLegSupportR52.apply(1,pose,3,new Vector3f());
        var rotations=new LinkedHashMap<String,Quaternionf>();for(var e:capture.getAsJsonObject("actual_finger_quaternions").entrySet())rotations.put(e.getKey(),quat(e.getValue().getAsJsonArray()));
        if(args.length>5)
        {
            var fitRoot=JsonParser.parseString(Files.readString(Path.of(args[5]))).getAsJsonObject();var fit=fitRoot.getAsJsonObject("calibration");
            var gunGeometry=YashimaCannonGeometryR52.parse(fitRoot);YashimaCannonMeshR52.requireOriginal(fitRoot,gunGeometry);
            var physical=JsonParser.parseString(Files.readString(Path.of(args[6]))).getAsJsonObject().getAsJsonObject("models").getAsJsonObject("1");
            var profile=new com.projectseele.physics.CombatBodyProfiles.Profile("1",physical,pose.rig,null);var values=new float[16];for(int i=0;i<16;i++)values[i]=capture.getAsJsonArray("world_matrix").get(i).getAsFloat();var w=new Matrix4f().set(values);
            var inverse=new Matrix4f(w).invert();var errors=new JsonObject();
            for(String side:List.of("l","r"))
            {
                String hand="hand_"+side;Vector3f actual=inverse.transformPosition(vec(capture.getAsJsonArray(side.equals("l")?"left_hand_world":"right_hand_world")));
                var palmLocal=new Matrix4f(pose.matrix(hand)).invert().transformPosition(actual);var goal=vec(fit.getAsJsonArray(side.equals("l")?"grip_left_body_model":"grip_right_body_model"));
                if(fit.has("grip_left_body_normal"))
                {
                    var wrist=pose.matrix(hand).transformPosition(new Vector3f(pose.rig.get(hand).pivot()));var offset=pose.matrix(hand).transformPosition(new Vector3f(palmLocal)).sub(wrist);
                    var normal=YashimaCannonMeshR52.normalR52(side.equals("l")?gunGeometry.left():gunGeometry.right());
                    var desired=gunGeometry.base().transformDirection(normal.toVector3f()).rotateY(-(180-fitRoot.get("prone_yaw").getAsFloat())*(float)java.lang.Math.PI/180).negate().normalize();
                    var orientation=new Quaternionf().rotationTo(offset.normalize(),desired).mul(pose.matrix(hand).getUnnormalizedRotation(new Quaternionf()).normalize());
                    pose.rotations.put(hand,pose.matrix(pose.rig.get(hand).parent()).getUnnormalizedRotation(new Quaternionf()).normalize().invert().mul(orientation));pose.dirty();
                }
                for(int i=0;i<3;i++)
                {
                    var wrist=pose.matrix(hand).transformPosition(new Vector3f(pose.rig.get(hand).pivot()));var palm=pose.matrix(hand).transformPosition(new Vector3f(palmLocal));
                    com.projectseele.physics.AnatomicalLimbConstraints.reachHand(pose,profile,side,new Vector3f(goal).sub(palm.sub(wrist)));pose.dirty();
                }
                var contact=pose.matrix(hand).transformPosition(new Vector3f(palmLocal));
                errors.addProperty(side,contact.distance(goal)*5);
                for(var entry:Map.of(side+"_goal",goal,side+"_contact",contact,side+"_palm_local",palmLocal,
                        side+"_shoulder",pose.matrix("arm_"+side).transformPosition(new Vector3f(pose.rig.get("arm_"+side).pivot())),
                        side+"_wrist",pose.matrix(hand).transformPosition(new Vector3f(pose.rig.get(hand).pivot()))).entrySet())
                {var point=entry.getValue();var array=new JsonArray();array.add(point.x);array.add(point.y);array.add(point.z);errors.add(entry.getKey(),array);}
            }
            Files.createDirectories(out);Files.writeString(out.resolve("actual_anatomical_grip_fit.json"),new GsonBuilder().setPrettyPrinting().create().toJson(errors));
            var matrices=new JsonObject();for(String name:pose.rig.keySet())
            {var array=new JsonArray();for(float v:pose.matrix(name).get(new float[16]))array.add(v);matrices.add(name,array);}
            Files.writeString(out.resolve("actual_fitted_bone_matrices.json"),new GsonBuilder().setPrettyPrinting().create().toJson(matrices));
        }
        var provider=jar==null?EvaOriginalMeshGeometryR52.load(assets,hashes):EvaOriginalMeshGeometryR52.load(resource->{var entry=jar.getEntry("assets/projectseele/"+resource);if(entry==null)throw new IOException("Actual native source missing: "+resource);return jar.getInputStream(entry).readAllBytes();},hashes);
        var geometry=provider.evaluate(1,pose,new EvaAnatomicalHandsR45.Pose("actual_native_cannon","actual_native_cannon",Map.copyOf(rotations)));
        Files.createDirectories(out);int vertices=0;
        try(var stream=new DataOutputStream(new GZIPOutputStream(Files.newOutputStream(out.resolve("actual_native_prone_parts.bin.gz")))))
        {stream.writeInt(0x52353243);stream.writeInt(1);stream.writeInt(geometry.parts().size());for(var part:geometry.parts()){stream.writeUTF(part.bone());stream.writeUTF(part.sourceSHA256());stream.writeInt(part.triangles().length/3);vertices+=part.triangles().length/3;for(double v:part.triangles())stream.writeFloat((float)v);}}
        Files.writeString(out.resolve("mesh_export_scope.json"),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("source",provider.sourceFingerprint(),"native_pose_uuid",capture.get("uuid").getAsString(),"vertices",vertices,"scope","Exact source skin with real native bones and 34 real finger transforms; source-local metres; not station or campaign acceptance","world_written",false)));
        System.out.println("Actual native pose mesh exported: parts="+geometry.parts().size()+" vertices="+vertices);
    }
}

package com.projectseele.world;
import com.projectseele.world.NervAirTransportManifestR52.*;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.phys.Vec3;
/** Pure encoding shared by native aircraft samples and their save checks. */
public final class NervAircraftFrameCodecR52 {
    public static CompoundTag encodeRigid(RigidTransform f){var t=new CompoundTag();t.putDouble("X",f.translation().x);t.putDouble("Y",f.translation().y);t.putDouble("Z",f.translation().z);t.putFloat("QX",f.qx());t.putFloat("QY",f.qy());t.putFloat("QZ",f.qz());t.putFloat("QW",f.qw());return t;}
    public static CompoundTag encodeRigid(RigidTransform f,CompoundTag prior){var t=prior.copy();var known=encodeRigid(f);for(String key:known.getAllKeys())t.put(key,known.get(key).copy());return t;}
    public static RigidTransform decodeRigid(CompoundTag t){return new RigidTransform(new Vec3(t.getDouble("X"),t.getDouble("Y"),t.getDouble("Z")),t.getFloat("QX"),t.getFloat("QY"),t.getFloat("QZ"),t.getFloat("QW"));}
    public static CompoundTag encode(Frame f){return encode(f,new CompoundTag());}
    public static CompoundTag encode(Frame f,CompoundTag prior){var t=prior.copy();t.put("Plane",encodeRigid(f.plane(),t.getCompound("Plane")));if(f.cargo()!=null)t.put("Cargo",encodeRigid(f.cargo(),t.getCompound("Cargo")));else if(t.contains("Cargo")){t.put("DetachedCargoReferenceR52",t.getCompound("Cargo").copy());t.remove("Cargo");}t.putFloat("Hoist",f.rig().hoist());t.putFloat("Deployment",f.rig().deployment());t.putFloat("Jaws",f.rig().jaws());return t;}
    public static Frame decode(CompoundTag t){return new Frame(decodeRigid(t.getCompound("Plane")),t.contains("Cargo")?decodeRigid(t.getCompound("Cargo")):null,new Rig(t.getFloat("Hoist"),t.getFloat("Deployment"),t.getFloat("Jaws")));}
    private NervAircraftFrameCodecR52(){}
}

package com.projectseele.entity;

import java.util.*;
import net.minecraft.nbt.*;
import org.joml.Quaternionf;

/** One immutable anatomical pose feeds both the existing final renderer and
 * the mechanical geometry. Capture before enabling the mechanical frame. */
public final class EvaFrozenHandsR52
{
    public static final String KEY="AnatomicalHandsR52";
    private static final String SCHEMA="projectseele.r52.frozen-anatomical-hands.v1";

    public static CompoundTag capture(EvaUnit01Entity eva,float partial)
    {
        if(!EvaAnatomicalHandsR45.enabled(eva))throw new IllegalStateException("Actual anatomical hand rig unavailable");
        var pose=EvaAnatomicalHandsR45.sample(eva,partial);
        return encode(eva.getUnitVariant(),EvaAnatomicalHandsR45.contractFingerprintR45(eva.getUnitVariant()),pose);
    }
    public static CompoundTag encode(int variant,String contract,EvaAnatomicalHandsR45.Pose pose)
    {
        if(variant<0||variant>2||!contract.matches("[0-9a-f]{64}")||pose.rotations().size()!=34)
            throw new IllegalArgumentException("Original variant, actual contract and all 34 joints required");
        var tag=new CompoundTag();tag.putString("Schema",SCHEMA);tag.putInt("Variant",variant);tag.putString("ContractSHA256",contract);
        tag.putString("Left",pose.left());tag.putString("Right",pose.right());var bones=new CompoundTag();
        for(var entry:new TreeMap<>(pose.rotations()).entrySet())
        {
            if(!entry.getKey().startsWith("r45_hand_"))throw new IllegalArgumentException("Foreign frozen hand joint");
            var q=entry.getValue();validate(q);var row=new ListTag();
            for(float v:new float[]{q.x,q.y,q.z,q.w})row.add(FloatTag.valueOf(v));bones.put(entry.getKey(),row);
        }
        tag.put("Bones",bones);return tag;
    }
    public static EvaAnatomicalHandsR45.Pose decode(int variant,String contract,Set<String> actualJoints,CompoundTag tag)
    {
        if(!SCHEMA.equals(tag.getString("Schema"))||tag.getInt("Variant")!=variant||!tag.getString("ContractSHA256").equals(contract)
                ||actualJoints.size()!=34||!tag.getCompound("Bones").getAllKeys().equals(actualJoints))
            throw new IllegalStateException("Frozen anatomical pose/source/34-joint identity mismatch");
        var result=new LinkedHashMap<String,Quaternionf>();var bones=tag.getCompound("Bones");
        for(String name:new TreeSet<>(actualJoints))
        {
            var row=bones.getList(name,Tag.TAG_FLOAT);if(row.size()!=4)throw new IllegalStateException("Missing exact frozen hand quaternion: "+name);
            var q=new Quaternionf(row.getFloat(0),row.getFloat(1),row.getFloat(2),row.getFloat(3));validate(q);result.put(name,q);
        }
        return new EvaAnatomicalHandsR45.Pose(tag.getString("Left"),tag.getString("Right"),Collections.unmodifiableMap(result));
    }
    public static EvaAnatomicalHandsR45.Pose frozen(EvaUnit01Entity eva)
    {
        var rig=EvaAnatomicalHandsR45.rig(eva.getUnitVariant());if(rig==null)throw new IllegalStateException("Original anatomical rig unavailable");
        return decode(eva.getUnitVariant(),EvaAnatomicalHandsR45.contractFingerprintR45(eva.getUnitVariant()),rig.named().keySet(),
                EvaAirTransportR31.cradleStateR50(eva).getCompound(KEY));
    }
    private static void validate(Quaternionf q)
    {if(q==null||!Float.isFinite(q.x)||!Float.isFinite(q.y)||!Float.isFinite(q.z)||!Float.isFinite(q.w)||Math.abs(q.lengthSquared()-1)>.0001F)throw new IllegalArgumentException("Finite unit hand quaternion required");}
    private EvaFrozenHandsR52(){}
}

package com.projectseele.entity;

import com.projectseele.util.QuaternionChannelsR45;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.FloatTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Pure saved-pose codec, usable by the asset pipeline without entity registries. */
public final class EvaPoseSnapshotR50
{
    public static java.util.Set<String> bones(CompoundTag tag)
    {
        var names=new java.util.HashSet<>(tag.getAllKeys());names.remove("__exact_quaternions_r53");return java.util.Set.copyOf(names);
    }
    public static CompoundTag encode(EvaBodyPose.Sample sample)
    {
        CompoundTag out=new CompoundTag();
        CompoundTag exact=new CompoundTag();
        for(String name:sample.rotations.keySet())
        {
            var r=QuaternionChannelsR45.euler(sample.rotations.get(name));var p=sample.positions.get(name);
            ListTag values=new ListTag();
            for(float v:new float[]{r.x,r.y,r.z,-p.x*16,p.y*16,p.z*16,1,1,1})values.add(FloatTag.valueOf(v));
            out.put(name,values);
            var q=sample.rotations.get(name);ListTag quaternion=new ListTag();
            for(float v:new float[]{q.x,q.y,q.z,q.w})quaternion.add(FloatTag.valueOf(v));
            exact.put(name,quaternion);
        }
        out.put("__exact_quaternions_r53",exact);
        return out;
    }

    public static void decode(CompoundTag tag,EvaBodyPose.Sample sample)
    {
        var exact=tag.getCompound("__exact_quaternions_r53");
        for(String name:tag.getAllKeys())if(sample.rotations.containsKey(name))
        {
            var a=tag.getList(name,Tag.TAG_FLOAT);if(a.size()!=9)continue;
            var q=exact.getList(name,Tag.TAG_FLOAT);
            sample.rotations.put(name,q.size()==4?new Quaternionf(q.getFloat(0),q.getFloat(1),q.getFloat(2),q.getFloat(3))
                    :new Quaternionf().rotationZYX(a.getFloat(2),a.getFloat(1),a.getFloat(0)));
            sample.positions.put(name,new Vector3f(-a.getFloat(3),a.getFloat(4),a.getFloat(5)).div(16));
        }
        sample.dirty();
    }
    private EvaPoseSnapshotR50(){}
}

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
    public static CompoundTag encode(EvaBodyPose.Sample sample)
    {
        CompoundTag out=new CompoundTag();
        for(String name:sample.rotations.keySet())
        {
            var r=QuaternionChannelsR45.euler(sample.rotations.get(name));var p=sample.positions.get(name);
            ListTag values=new ListTag();
            for(float v:new float[]{r.x,r.y,r.z,-p.x*16,p.y*16,p.z*16,1,1,1})values.add(FloatTag.valueOf(v));
            out.put(name,values);
        }
        return out;
    }

    public static void decode(CompoundTag tag,EvaBodyPose.Sample sample)
    {
        for(String name:tag.getAllKeys())if(sample.rotations.containsKey(name))
        {
            var a=tag.getList(name,Tag.TAG_FLOAT);if(a.size()!=9)continue;
            sample.rotations.put(name,new Quaternionf().rotationZYX(a.getFloat(2),a.getFloat(1),a.getFloat(0)));
            sample.positions.put(name,new Vector3f(-a.getFloat(3),a.getFloat(4),a.getFloat(5)).div(16));
        }
        sample.dirty();
    }
    private EvaPoseSnapshotR50(){}
}

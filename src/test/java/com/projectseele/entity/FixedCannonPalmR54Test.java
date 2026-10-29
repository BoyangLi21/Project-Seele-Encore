package com.projectseele.entity;

import com.google.gson.JsonObject;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Checks contact factorization against the former world-space finger recursion, without loading assets. */
public final class FixedCannonPalmR54Test
{
    public static void main(String[] args)
    {
        var random=new Random(54);float maximum=0;int cases=0;
        for(int sample=0;sample<100;sample++)
        {
            var joints=new ArrayList<EvaAnatomicalHandsR45.Joint>();
            var named=new HashMap<String,EvaAnatomicalHandsR45.Joint>();
            var rotations=new HashMap<String,Quaternionf>();
            for(String side:List.of("l","r"))for(String digit:List.of("index","middle"))for(int index=1;index<=2;index++)
            {
                String name="r45_hand_"+side+"_"+digit+"_"+index;
                String parent=index==1?"hand_"+side:"r45_hand_"+side+"_"+digit+"_1";
                var pivot=vector(random);var joint=new EvaAnatomicalHandsR45.Joint(name,parent,side,digit,index,pivot,
                        vector(random),new Matrix4f().translation(vector(random)).rotate(rotation(random)),
                        new Quaternionf(),new float[3][2]);
                joints.add(joint);named.put(name,joint);rotations.put(name,rotation(random));
            }
            var rig=new EvaAnatomicalHandsR45.Rig(joints,named,new JsonObject(),Map.of(),null,null,null,Map.of());
            var pose=new EvaAnatomicalHandsR45.Pose("cannon","cannon",rotations);
            for(String side:List.of("l","r"))
            {
                var local=FixedCannonPoseR52.localPalm(rig,pose,side);
                for(int iteration=0;iteration<4;iteration++)
                {
                    var hand=new Matrix4f().translation(vector(random).mul(20)).rotate(rotation(random));
                    var original=point(rig,pose,hand,"r45_hand_"+side+"_index_2")
                            .lerp(point(rig,pose,hand,"r45_hand_"+side+"_middle_2"),.5F);
                    float error=original.distance(hand.transformPosition(new Vector3f(local)));
                    if(error>1e-4F)throw new AssertionError("Changed actual hand contact: "+error);
                    maximum=Math.max(maximum,error);cases++;
                }
            }
        }
        System.out.println("PASS: "+cases+" moving-hand contact cases; maximum model-space error="+maximum);
    }

    private static Vector3f point(EvaAnatomicalHandsR45.Rig rig,EvaAnatomicalHandsR45.Pose pose,Matrix4f hand,String name)
    {var joint=rig.named().get(name);return matrix(rig,pose,hand,name).mul(joint.inverseBind()).transformPosition(new Vector3f(joint.head()));}
    private static Matrix4f matrix(EvaAnatomicalHandsR45.Rig rig,EvaAnatomicalHandsR45.Pose pose,Matrix4f hand,String name)
    {
        var joint=rig.named().get(name);if(joint==null)return new Matrix4f(hand);
        var p=joint.pivot();return matrix(rig,pose,hand,joint.parent()).translate(p).rotate(pose.rotations().get(name)).translate(-p.x,-p.y,-p.z);
    }
    private static Vector3f vector(Random random)
    {return new Vector3f(random.nextFloat()*2-1,random.nextFloat()*2-1,random.nextFloat()*2-1);}
    private static Quaternionf rotation(Random random)
    {return new Quaternionf().rotationXYZ(random.nextFloat()*3,random.nextFloat()*3,random.nextFloat()*3);}
}

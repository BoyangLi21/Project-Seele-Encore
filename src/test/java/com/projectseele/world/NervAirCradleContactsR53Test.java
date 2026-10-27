package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.*;

/** Pure source contact selection; no world or completed recovery claim. */
public final class NervAirCradleContactsR53Test
{
    private static int checks;
    private static void check(boolean condition,String message)
    {checks++;if(!condition)throw new AssertionError(message);}
    public static void main(String[] args)
    {
        var names=List.of("arm_l","arm_r","leg_l","leg_r","shin_l","shin_r");
        var parts=new ArrayList<EvaOriginalMeshGeometryR52.Part>();var hints=new ArrayList<Vec3>();
        for(int i=0;i<6;i++)
        {
            double x=i%2==0?-10:10,z=(i/2)*8;var xyz=new double[27];
            for(int h=0;h<3;h++){double y=h==0?0:4+h;int n=h*9;double[] t={x-1,y,z-1,x+1,y,z-1,x,y,z+1};System.arraycopy(t,0,xyz,n,9);}
            parts.add(new EvaOriginalMeshGeometryR52.Part(names.get(i),"test","test",xyz,new AABB(x-1,0,z-1,x+1,6,z+1)));
            hints.add(new Vec3(x,5.1,z));
        }
        var body=new EvaOriginalMeshGeometryR52.Geometry(2,"test",parts);
        var original=NervAirCradleContactsR52.evaluate(body,hints);
        check(original.equals(NervAirCradleContactsR52.evaluate(body,hints,c->true)),"Unblocked original contacts remain unchanged");
        check(NervAirCradleContactsR52.valid(body,original),"Original contacts validate against source");
        var alternate=NervAirCradleContactsR52.evaluate(body,hints,c->c.get(2).skin().y>5.5&&c.get(4).skin().y>5.5);
        check(alternate.size()==6,"Search can change two obstructed pairs together");
        check(NervAirCradleContactsR52.valid(body,alternate),"Alternate contacts preserve actual paired source skin");
        int[] calls={0};check(NervAirCradleContactsR52.evaluate(body,hints,c->{calls[0]++;return false;}).isEmpty(),"No accepted combination returns explicit empty result");
        check(calls[0]<=256,"Whole contact predicate calls remain bounded");
        var bad=new ArrayList<>(original);var c=bad.get(0);
        bad.set(0,new NervAirCradleContactsR52.Contact(c.bone(),c.skin().add(0,.1,0),c.centre(),c.axis()));
        check(!NervAirCradleContactsR52.valid(body,bad),"Off-skin persisted contact is rejected");
        bad.set(0,new NervAirCradleContactsR52.Contact(c.bone(),c.skin(),c.centre().add(0,.1,0),c.axis()));
        check(!NervAirCradleContactsR52.valid(body,bad),"Changed jaw radius is rejected");
        bad.set(0,new NervAirCradleContactsR52.Contact(c.bone(),c.skin(),c.centre(),c.axis().scale(-1)));
        check(!NervAirCradleContactsR52.valid(body,bad),"Changed paired axis is rejected");
        bad.set(0,new NervAirCradleContactsR52.Contact("leg_l",c.skin(),c.centre(),c.axis()));
        check(!NervAirCradleContactsR52.valid(body,bad),"Changed source bone is rejected");
        check(!NervAirCradleContactsR52.valid(body,List.of()),"Missing persisted contacts are rejected");
        System.out.println("PASS R53 bounded skin contact alternatives: "+checks);
    }
}

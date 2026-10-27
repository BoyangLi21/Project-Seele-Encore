package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.*;

/** Moving the same rigid assembly must not repeat its immutable sole fit. */
public final class CarrierFootBearingMemoR54Test
{
    private static int checks;
    private static void check(boolean value,String reason){checks++;if(!value)throw new AssertionError(reason);}
    private static CarrierAssemblyR53.Surface deck(float height)throws Exception
    {
        float[] values=new float[24];float[] xyz={-10,height,-10,10,height,-10,0,height,10};
        for(int i=0;i<3;i++)System.arraycopy(xyz,i*3,values,i*8,3);
        var ctor=CarrierAssemblyR53.Surface.class.getDeclaredConstructor(float[].class,String.class);ctor.setAccessible(true);
        return ctor.newInstance(values,"test");
    }
    private static EvaOriginalMeshGeometryR52.Geometry body(double height)
    {
        var xyz=new double[]{-10,height,-10,10,height,-10,0,height,10};
        var parts=new ArrayList<EvaOriginalMeshGeometryR52.Part>();
        for(String bone:List.of("foot_l","foot_r"))parts.add(new EvaOriginalMeshGeometryR52.Part(bone,"test","test",xyz,new AABB(-10,height,-10,10,height,10)));
        return new EvaOriginalMeshGeometryR52.Geometry(1,"test",parts);
    }
    public static void main(String[] args)throws Exception
    {
        var padMesh=new NervRigidMeshSweepR52(new double[]{-1,0,-1,1,0,-1,0,0,1});
        var contacts=List.of(List.of(new Vec3(-1,0,-1),new Vec3(1,0,-1),new Vec3(0,0,1)));
        var pads=List.of(new CarrierFootBearingR53.Pad(1,"foot_l","left",padMesh,new double[0],contacts,0),
                new CarrierFootBearingR53.Pad(1,"foot_r","right",padMesh,new double[0],contacts,0));
        var source=new CarrierFootBearingR53.Source(pads,"source","deck");var body=body(0);
        var profile=new CarrierAssemblyR53.Profile(Map.of("deck",deck(0)),Vec3.ZERO,"profile");
        var mount=new CarrierMountProfileR53.State(true,0,0);var zero=RigidTransform.identity();
        var cacheField=CarrierFootBearingR53.class.getDeclaredField("BEARINGS");cacheField.setAccessible(true);
        Map<?,?> cache=(Map<?,?>)cacheField.get(null);cache.clear();
        check(CarrierFootBearingR53.bears(source,body,zero,zero,mount,profile),"finite real triangles bear");
        for(int i=0;i<100;i++)
        {
            var moved=new RigidTransform(new Vec3(32,-1000+i*8,300),0,1,0,0);
            check(CarrierFootBearingR53.bears(source,body,moved,moved,mount,profile),"common world motion retains same physical fit");
        }
        check(cache.size()==1,"same relative assembly reuses one bounded result");
        var raised=new RigidTransform(new Vec3(0,.01,0),0,0,0,1);
        check(!CarrierFootBearingR53.bears(source,body,raised,zero,mount,profile),"changed relative frame rechecks and rejects lost support");
        check(!CarrierFootBearingR53.bears(source,body(.01),zero,zero,mount,profile),"changed original body source is not cached as old soles");
        var changedDeck=new CarrierAssemblyR53.Profile(Map.of("deck",deck(.01F)),Vec3.ZERO,"profile");
        check(!CarrierFootBearingR53.bears(source,body,zero,zero,mount,changedDeck),"changed deck source rechecks despite same declared fingerprint");
        for(int i=0;i<40;i++)CarrierFootBearingR53.bears(source,body,new RigidTransform(new Vec3(0,i+.1,0),0,0,0,1),zero,mount,profile);
        check(cache.size()==32,"immutable memo remains bounded");
        check(CarrierFootBearingR53.bears(source,body,zero,zero,mount,profile),"eviction recomputes original support correctly");
        System.out.println("PASS immutable foot-bearing memo: "+checks);
    }
}

package com.projectseele.client.render;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;

/** Bakes the actual render source without starting a client or an OpenGL context. */
public final class ExportCraneProceduralR53
{
    public static void main(String[] args)throws Exception
    {
        var type=PlugGantryRenderer.class;var output=new LinkedHashMap<String,Object>();boolean refitted=args.length>1&&Boolean.parseBoolean(args[1]);
        var vertices=RigidMachineryPartR44.class.getDeclaredField("vertices");vertices.setAccessible(true);
        for(String part:List.of("top","yoke","sheave","wheel","links","rope"))
        {
            Object mesh;
            if(part.equals("rope"))
            {
                var builder=new RigidMachineryPartR44.Builder();var ctor=type.getDeclaredConstructor(RigidMachineryPartR44.Builder.class);ctor.setAccessible(true);var renderer=ctor.newInstance(builder);
                var cylinder=type.getDeclaredMethod("cylinder",net.minecraft.world.phys.Vec3.class,net.minecraft.world.phys.Vec3.class,double.class,double.class,int.class,int.class);cylinder.setAccessible(true);
                cylinder.invoke(renderer,new net.minecraft.world.phys.Vec3(0,0,0),new net.minecraft.world.phys.Vec3(0,1,0),1D,0D,0xadb7bb,12);mesh=builder.finish();
            }
            else if(part.equals("top")){var method=type.getDeclaredMethod("topMesh",boolean.class);method.setAccessible(true);mesh=method.invoke(null,refitted);}
            else{var method=type.getDeclaredMethod(part+"Mesh");method.setAccessible(true);mesh=method.invoke(null);}
            float[] values=(float[])vertices.get(mesh);var triangles=new ArrayList<Double>();
            for(int q=0;q<values.length;q+=44)for(int[] indices:new int[][]{{0,1,2},{0,2,3}})
            {
                var a=point(values,q+indices[0]*11);var b=point(values,q+indices[1]*11);var c=point(values,q+indices[2]*11);
                if(b.subtract(a).cross(c.subtract(a)).lengthSqr()<1e-20)continue;
                for(int i:indices)for(int k=0;k<3;k++)triangles.add((double)values[q+i*11+k]);
            }
            output.put(part,triangles);System.out.println(part+"="+triangles.size()/9);
        }
        var document=new LinkedHashMap<String,Object>();document.put("schema","projectseele.r52.actual-crane-procedural-triangles.v1");document.put("parts",output);document.put("tail_bearing_r53",true);if(refitted)document.put("raised_winch_deck_r53",com.projectseele.world.NervCraneBearingR53.WINCH_DECK);
        Files.writeString(Path.of(args[0]),new Gson().toJson(document));
    }
    private static net.minecraft.world.phys.Vec3 point(float[] v,int at){return new net.minecraft.world.phys.Vec3(v[at],v[at+1],v[at+2]);}
}

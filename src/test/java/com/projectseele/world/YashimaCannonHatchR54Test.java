package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.entity.SiloHatchMechanism;
import java.nio.file.Files;
import java.nio.file.Path;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;

/** Installed cannon source sweep; native blocks and actors are checked in the running level. */
public final class YashimaCannonHatchR54Test
{
    private static float progress(double t){return (float)(t*t*t*(t*(t*6-15)+10));}
    public static void main(String[] args)throws Exception
    {
        var p=TvYashimaStationR52.parse(JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject(),"projectseele:geofront");
        var hatch=NervSiloHatchGeometryR52.loadClasspath(new SiloHatchMechanism.Spec(39,53,80,80,1,-2.02));
        var frame=new RigidTransform(new Vec3(-1251.5,174.02,-1397.5),0,0,0,1);
        var meshMethod=YashimaCannonMeshR52.class.getDeclaredMethod("gun",float.class);meshMethod.setAccessible(true);
        var frameMethod=YashimaCannonMeshR52.class.getDeclaredMethod("frame",com.projectseele.entity.YashimaCannonGeometryR52.Geometry.class,Vec3.class,Quaternionf.class);frameMethod.setAccessible(true);
        var gun=(NervRigidMeshSweepR52)meshMethod.invoke(null,p.geometry().scale());var aim=new Quaternionf();
        var closed=(RigidTransform)frameMethod.invoke(null,p.geometry(),p.closed(),aim);int checks=0;
        for(int i=0;i<80;i++)
        {
            float from=progress(i/80D),to=progress((i+1)/80D);
            if(hatch.intersects(frame,from,to,gun,closed,closed))throw new AssertionError("Hatch stroke hits original closed gun at "+i);
            checks++;
            for(var piece:FixedCannonCradleR52.pieces(p.geometry(),p.cradle(),p.closed(),aim))
            {if(hatch.intersects(frame,from,to,piece.mesh(),piece.frame(),piece.frame()))throw new AssertionError("Hatch stroke hits cradle "+piece.part().name()+" at "+i);checks++;}
        }
        for(int i=0;i<100;i++)
        {
            var a=p.closed().lerp(p.raised(),i/100D);var b=p.closed().lerp(p.raised(),(i+1)/100D);
            if(hatch.intersects(frame,1,1,gun,(RigidTransform)frameMethod.invoke(null,p.geometry(),a,aim),(RigidTransform)frameMethod.invoke(null,p.geometry(),b,aim)))
                throw new AssertionError("Raised aperture blocks gun stroke at "+i);
            checks++;
        }
        System.out.println("PASS original cannon/hatch full stroke: "+checks);
    }
}

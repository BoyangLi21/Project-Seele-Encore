package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.entity.YashimaCannonGeometryR52;
import java.nio.file.Files;
import java.nio.file.Path;
import org.joml.Quaternionf;

/** The ordinary draw/bounds path accepts aim poses beyond diagnostic strut travel. */
public final class FixedCannonGameplayR54Test
{
    public static void main(String[] args)throws Exception
    {
        var root=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        var gun=YashimaCannonGeometryR52.parse(root);
        var cradle=FixedCannonCradleR52.Spec.parse(root.getAsJsonObject("cradle"));
        var position=YashimaCannonGeometryR52.vector(root.getAsJsonArray("raised_position"));
        int poses=0,diagnosticLimits=0;
        for(int yaw:new int[]{-90,-45,0,45,90})for(int pitch:new int[]{-80,-30,0,30,80})
        {
            var aim=new Quaternionf().rotationYXZ((float)Math.toRadians(yaw),(float)Math.toRadians(pitch),0);
            var bounds=FixedCannonCradleR52.bounds(gun,cradle,position,aim);
            if(bounds==null||!Double.isFinite(bounds.minX+bounds.minY+bounds.minZ+bounds.maxX+bounds.maxY+bounds.maxZ))
                throw new AssertionError("Non-finite ordinary aiming bounds at "+yaw+"/"+pitch);
            for(var piece:FixedCannonCradleR52.pieces(gun,cradle,position,aim))
                if(!Double.isFinite(piece.frame().translation().lengthSqr()+piece.frame().qx()+piece.frame().qy()+piece.frame().qz()+piece.frame().qw()))
                    throw new AssertionError("Non-finite displayed cradle frame");
            try{FixedCannonCradleR52.sweep(gun,cradle,position,position,aim,aim);}
            catch(IllegalArgumentException limit){diagnosticLimits++;}
            poses++;
        }
        if(diagnosticLimits==0)throw new AssertionError("Did not exercise the former strut-stroke crash");
        System.out.println("PASS ordinary cannon aiming: "+poses+" finite poses; "+diagnosticLimits+" exceed STRICT strut travel without interrupting gameplay");
    }
}

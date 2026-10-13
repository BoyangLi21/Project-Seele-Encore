package com.projectseele.world;
import com.google.gson.*;
import java.util.*;
import net.minecraft.world.phys.*;

/** Full existing source vertices on the declared whole-carrier actuator. */
public final class NervCarrierDeckTravelR52Test
{
    public static void main(String[] args)throws Exception
    {
        var receipt=JsonParser.parseString(new String(EvaOriginalMeshGeometryR52.classpathBytes("eva/full_assembly_geometry_r52_sources.json"),java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();var hashes=new HashMap<String,String>();receipt.getAsJsonObject("resources").entrySet().forEach(e->hashes.put(e.getKey(),e.getValue().getAsString()));var provider=FullAssemblyGeometryR52.load(EvaOriginalMeshGeometryR52::classpathBytes,hashes);var raised=provider.carrierParts(1,false,0,64);long checks=0;
        for(float rise:new float[]{0,.01F,.25F,.5F,.99F,1})
        {
            var actual=provider.carrierParts(rise,false,0,64);if(!actual.keySet().equals(raised.keySet()))throw new AssertionError("Whole imported carrier lost a source part");double travel=-64*(1-rise);
            for(String part:raised.keySet()){var a=actual.get(part);var b=raised.get(part);if(a.length!=b.length)throw new AssertionError("Actual carrier topology changed");for(int i=0;i<a.length;i+=3){if(Math.abs(a[i]-b[i])>.0001||Math.abs(a[i+2]-b[i+2])>.0001||Math.abs(a[i+1]-b[i+1]-travel)>.0001)throw new AssertionError("Actual whole-deck actuator mismatch "+part+" rise="+rise);checks++;}}
        }
        var legacy=provider.carrierParts(0,false,0);var deck=raised.get("deck");if(!Arrays.equals(legacy.get("deck"),deck))throw new AssertionError("Unclaimed legacy deck changed");
        var mesh=new NervRigidMeshSweepR52(deck);var bay=RigidTransform.identity();var stowed=new RigidTransform(new Vec3(0,-64,0),0,0,0,1);var floor=new AABB(-13,-1,-14,13,0,14);if(!mesh.intersects(stowed,bay,floor,.003))throw new AssertionError("Real floor obstruction disappeared from whole-deck sweep");
        System.out.println("Actual full carrier/deck 64m actuator PASS vertices="+checks+" source="+provider.sourceFingerprint()+"; floor remains blocking until real shutter opens; no world/native acceptance");
    }
}

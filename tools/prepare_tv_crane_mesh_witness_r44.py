"""Private native crane export hook; root owns integration, compile and MC."""
from pathlib import Path
import hashlib,json,difflib
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r44/hangar_machinery/personnel_crane_mesh_witness_v1'
SOURCE='''package com.projectseele.client.render;

import com.google.gson.*;
import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.entity.NervCarrierPlatformEntity;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import java.nio.file.*;
import java.util.*;

/** Reviewonly actual submitted crane quads and their current entity-relative frame. */
final class TvCraneMeshWitnessR44
{
    private record Frame(String uuid,int variant,long tick,float partial,Vec3 origin,Matrix4f inverse,JsonArray parts) { }
    private static final ThreadLocal<Frame> ACTIVE=new ThreadLocal<>();
    private static final Map<Integer,Long> LAST=new HashMap<>();
    private static final Map<Integer,Integer> COUNT=new HashMap<>();
    static void begin(NervCarrierPlatformEntity entity,float partial,PoseStack poses)
    {
        ACTIVE.remove();
        if(!Boolean.getBoolean("projectseele.r44NativeCraneMeshWitness")||!entity.isPlugCrane()
            ||!entity.level().dimension().location().toString().equals("projectseele:geofront"))return;
        int v=entity.getUnitVariant();long tick=entity.level().getGameTime();
        if(v<0||v>2||COUNT.getOrDefault(v,0)>=Integer.getInteger("projectseele.r44CraneWitnessMaximumPerBay",72)
            ||LAST.getOrDefault(v,Long.MIN_VALUE)==tick
            ||Math.floorMod(tick,Integer.getInteger("projectseele.r44CraneWitnessStride",20))!=0)return;
        LAST.put(v,tick);COUNT.merge(v,1,Integer::sum);
        ACTIVE.set(new Frame(entity.getStringUUID(),v,tick,partial,entity.getPosition(partial),
            new Matrix4f(poses.last().pose()).invert(),new JsonArray()));
    }
    static void part(float[] vertices,PoseStack poses)
    {
        var frame=ACTIVE.get();if(frame==null)return;
        Matrix4f relative=new Matrix4f(frame.inverse).mul(poses.last().pose());
        var triangles=new JsonArray();int quads=vertices.length/44;
        for(int q=0;q<quads;q++)for(int[] indices:new int[][]{{0,1,2},{0,2,3}})
        {
            Vector3f[] local=new Vector3f[3];var world=new JsonArray();
            for(int i=0;i<3;i++)
            {
                int k=q*44+indices[i]*11;
                local[i]=relative.transformPosition(new Vector3f(vertices[k],vertices[k+1],vertices[k+2]));
                var xyz=new JsonArray();xyz.add(frame.origin.x+local[i].x);xyz.add(frame.origin.y+local[i].y);xyz.add(frame.origin.z+local[i].z);world.add(xyz);
            }
            if(new Vector3f(local[1]).sub(local[0]).cross(new Vector3f(local[2]).sub(local[0])).lengthSquared()<1e-12F)continue;
            triangles.add(world);
        }
        var row=new JsonObject();row.addProperty("part_call_index",frame.parts.size());row.addProperty("source_quad_count",quads);
        row.add("actual_world_triangles",triangles);frame.parts.add(row);
    }
    static void end()
    {
        var frame=ACTIVE.get();ACTIVE.remove();if(frame==null)return;
        String target=System.getProperty("projectseele.r44CraneMeshWitnessPath","");
        if(target.isBlank())throw new IllegalStateException("Crane witness output must be explicit");
        var row=new JsonObject();row.addProperty("crane_uuid",frame.uuid);row.addProperty("variant",frame.variant);
        row.addProperty("world_tick",frame.tick);row.addProperty("partial",frame.partial);row.add("parts",frame.parts);
        row.addProperty("frame_basis","inverseinitialentityPose*submittedpartPose; entitygetPosition(partial) worldorigin added. No synthetic crane pose.");
        try{Path path=Path.of(target);Files.createDirectories(path.getParent());Files.writeString(path,new Gson().toJson(row)+"\\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);}
        catch(java.io.IOException e){throw new IllegalStateException("Crane witness export failed",e);}
    }
    private TvCraneMeshWitnessR44() { }
}
'''

def main():
    if OUT.exists():raise ValueError('Fresh witness proposal required')
    OUT.mkdir(parents=True);p=OUT/'source/com/projectseele/client/render/TvCraneMeshWitnessR44.java';p.parent.mkdir(parents=True);p.write_text(SOURCE,'utf8')
    diff=[];rows=[]
    for name,beforehook,afterhook in [
        ('PlugGantryRenderer.java','    {new PlugGantryRenderer(poses,buffers,light).draw(entity,partial);}',
         '    {TvCraneMeshWitnessR44.begin(entity,partial,poses);try{new PlugGantryRenderer(poses,buffers,light).draw(entity,partial);}finally{TvCraneMeshWitnessR44.end();}}'),
        ('RigidMachineryPartR44.java','        if (RigidMachineryGpuR44.draw(this, vertices, PAINT, poses, buffers, light)) return;',
         '        TvCraneMeshWitnessR44.part(vertices,poses);\n        if (RigidMachineryGpuR44.draw(this, vertices, PAINT, poses, buffers, light)) return;')]:
        path=ROOT/'src/main/java/com/projectseele/client/render'/name;before=path.read_text('utf8')
        if before.count(beforehook)!=1:raise ValueError('Witnesshooknotunique')
        after=before.replace(beforehook,afterhook);rel='src/main/java/com/projectseele/client/render/'+name
        diff.extend(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+rel,tofile='b/'+rel));rows.append({'path':rel,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (OUT/'unapplied_hooks.diff').write_text(''.join(diff),'utf8')
    (OUT/'manifest.json').write_text(json.dumps({'status':'PRIVATE_NATIVE_EXPORT_SOURCE_UNCOMPILED_UNAPPLIED','source_epochs':rows,'source_modified':False,'native_passed':False,'world_write':False,
        'purpose':'RootintegrationexportsallactualbakedmeshquadsbeforeGPUfastpathwithnativeworldframes. Bound72framesperbay/20tickdefaults, no synthetic crane state. Onlythecurrent actualPlugGantry draw thread context contributes; other rigid meshesignored.',
        'required':['rootcompileandinstallwitnessonly','rootactualfullinsert/eject/stow/recoverycranephaseexports','validateframebasisusingvisiblewheelatworldY-373andcanonicalCRANE_ATTACHMENT_P','newfixed/nativefloor-guard exactSATfromeveryactualpart, positivefindingsretained','continuoussourceenvelopebetweenframesandnativecold/sync'],'properties':['projectseele.r44NativeCraneMeshWitness=true','projectseele.r44CraneMeshWitnessPath=<explicit privatejsonl>','projectseele.r44CraneWitnessStride=20','projectseele.r44CraneWitnessMaximumPerBay=72']},indent=2),'utf8')
    print(OUT)

if __name__=='__main__':main()

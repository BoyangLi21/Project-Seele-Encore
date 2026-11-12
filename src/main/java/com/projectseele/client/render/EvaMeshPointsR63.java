package com.projectseele.client.render;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaBodyPose;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.resources.ResourceLocation;
import org.joml.Vector3f;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;

/**
 * The points of a unit's mesh that standing on the ground needs: for every body part the vertices farthest out
 * along 26 directions (ground contact), and every vertex of the two feet (foot placement).
 * <p>
 * They are taken from the mesh the game already holds for drawing the unit. Ground contact and foot placement
 * each used to read the mesh file again and parse it as one document. For Units 00 to 02 and UN-01 that file is
 * 3 to 30 MB. UN-00's is the owner's full source surface, 860 MB of text and 1.9 million triangles: with a
 * powered UN-00 in view the game stood still for five minutes and then ran out of a 6 GB heap, and a unit leaving
 * its rack asked for the file twice. Nothing is read here any more.
 */
final class EvaMeshPointsR63
{
    /** hulls: body part to its farthest vertices. feet: "l" and "r" to the foot's vertices, each once, in the mesh's order. */
    record Points(Map<String,Vector3f[]> hulls,Map<String,Vector3f[]> feet) {}
    private static final Points NONE=new Points(Map.of(),Map.of());
    private static final Map<Integer,Points> KNOWN=new HashMap<>();
    private static final List<Vector3f> DIRECTIONS=new ArrayList<>();
    static
    {
        for(int x=-1;x<=1;x++)for(int y=-1;y<=1;y++)for(int z=-1;z<=1;z++)
            if(x!=0||y!=0||z!=0)DIRECTIONS.add(new Vector3f(x,y,z).normalize());
    }

    /** Called from the render thread only, as the mesh itself is. Empty when the unit has no mesh to draw. */
    static Points of(EvaUnit01Entity eva,String[] hullParts)
    {
        return KNOWN.computeIfAbsent(EvaBodyPose.rigKey(eva),rig->
        {
            String asset=eva.isExperimentalUnit()?eva.experimentalAssetName():"eva_unit0"+rig;
            try{return take(asset,hullParts);}
            catch(RuntimeException failure){ProjectSeele.LOGGER.warn("R63 ground points unavailable for variant {} ({})",rig,asset,failure);return NONE;}
        });
    }

    /** On a resource reload: the meshes may have changed. */
    static void clear(){KNOWN.clear();}

    private static Points take(String asset,String[] hullParts)
    {
        long started=System.nanoTime();
        var resource=new ResourceLocation("projectseele","mesh/"+asset+".mesh.json");
        Map<String,Vector3f[]> hulls=new HashMap<>(),feet=new HashMap<>();
        // How far out the parts reach along the 26 directions, summed: what ground contact reads off the hulls.
        double reach=0;
        for(String name:hullParts)
        {
            // x, y, z of every vertex, in blocks of the model, the pivot already in.
            float[] at=LocalTriangleMeshLayer.nativeTrianglePositions(resource,name);
            if(at==null)continue;
            int[] far=new int[DIRECTIONS.size()];float[] score=new float[DIRECTIONS.size()];
            java.util.Arrays.fill(far,-1);java.util.Arrays.fill(score,Float.NEGATIVE_INFINITY);
            for(int i=0;i+2<at.length;i+=3)
                for(int d=0;d<score.length;d++)
                {
                    var direction=DIRECTIONS.get(d);float s=at[i]*direction.x+at[i+1]*direction.y+at[i+2]*direction.z;
                    if(s>score[d]){score[d]=s;far[d]=i;}
                }
            List<Vector3f> kept=new ArrayList<>();
            for(int d=0;d<far.length;d++)
            {
                if(far[d]<0)continue;
                reach+=score[d];
                var point=new Vector3f(at[far[d]],at[far[d]+1],at[far[d]+2]);
                if(!kept.contains(point))kept.add(point);
            }
            if(!kept.isEmpty())hulls.put(name,kept.toArray(Vector3f[]::new));
        }
        for(String side:List.of("l","r"))
        {
            float[] at=LocalTriangleMeshLayer.nativeTrianglePositions(resource,"foot_"+side);
            if(at==null)continue;
            // A triangle list repeats its corners; the lowest, foremost and rearmost vertex are the same without the repeats.
            LinkedHashSet<Vector3f> every=new LinkedHashSet<>();
            for(int i=0;i+2<at.length;i+=3)every.add(new Vector3f(at[i],at[i+1],at[i+2]));
            feet.put(side,every.toArray(Vector3f[]::new));
        }
        if(hulls.isEmpty()&&feet.isEmpty())return NONE;
        // The two sums let these points be compared with the mesh file itself (tools/groundpoints.py).
        ProjectSeele.LOGGER.info("R63 ground points of {} taken in {} ms: {} hull parts (reach {}), soles of {} and {} vertices (sum {})",asset,
                (System.nanoTime()-started)/1_000_000L,hulls.size(),String.format(java.util.Locale.ROOT,"%.3f",reach),
                feet.containsKey("l")?feet.get("l").length:0,feet.containsKey("r")?feet.get("r").length:0,String.format(java.util.Locale.ROOT,"%.3f",sum(feet)));
        return new Points(hulls,feet);
    }

    /** x + 2y + 3z over every point kept, in blocks of the model. */
    private static double sum(Map<String,Vector3f[]> points)
    {
        double total=0;
        for(var part:points.values())for(var v:part)total+=v.x+2D*v.y+3D*v.z;
        return total;
    }

    private EvaMeshPointsR63() {}
}

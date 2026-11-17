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
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Function;

/**
 * The points of a unit's mesh that standing on the ground needs: for every body part the vertices farthest out
 * along 26 directions (ground contact), and the vertices of the two feet (foot placement).
 * <p>
 * They are taken from the mesh the game already holds for drawing the unit. Ground contact and foot placement
 * each used to read the mesh file again and parse it as one document. For Units 00 to 02 and UN-01 that file is
 * 3 to 30 MB. UN-00's is the owner's full source surface, 860 MB of text and 1.9 million triangles: with a
 * powered UN-00 in view the game stood still for five minutes and then ran out of a 6 GB heap, and a unit leaving
 * its rack asked for the file twice. Nothing is read here any more.
 * <p>
 * A mesh that is parsed ahead on a background worker has its points taken there, as soon as it is parsed: taken
 * when the unit first stood, UN-00's four million vertices held the render thread for 0.6 seconds.
 */
final class EvaMeshPointsR63
{
    /** The body parts ground contact reads; the feet are among them. */
    static final String[] PARTS={"foot_l","foot_r","shin_l","shin_r","leg_l","leg_r","torso_lower","torso_upper",
            "arm_l","arm_r","forearm_l","forearm_r","hand_l","hand_r","head"};
    /**
     * hulls: body part to its farthest vertices. feet: "l" and "r" to the foot's vertices, each once, in the mesh's
     * order (the sole's rectangle is read off them once). outlines: what foot placement walks every frame for the
     * lowest, foremost and rearmost point of a foot: all of its vertices, or for a dense foot only the ones that
     * can be any of those.
     */
    record Points(Map<String,Vector3f[]> hulls,Map<String,Vector3f[]> feet,Map<String,Vector3f[]> outlines) {}
    private static final Points NONE=new Points(Map.of(),Map.of(),Map.of());
    private static final Map<Integer,Points> KNOWN=new HashMap<>();
    /** Taken off the render thread while the mesh was parsed ahead, by the mesh's resource. */
    private static final Map<ResourceLocation,Points> PREPARED=new ConcurrentHashMap<>();
    /** Counts the resource reloads: points prepared for the meshes of an earlier one are not kept. */
    private static volatile int generation;
    private static final float[][] DIRECTIONS;
    /**
     * A foot of more vertices than this is walked by its outline. The lowest point of a rigid body along any
     * direction is the vertex farthest out along it; the outline keeps the vertices farthest out along this many
     * directions spread evenly over the sphere (2.5 degrees apart: what lies between two of them is lower than
     * a kept vertex by less than a hundredth of a block of the drawn unit). UN-00's feet are 45,941 and 46,471
     * vertices, walked every frame; Units 00 to 02 have 119 or 120 and are walked whole.
     */
    private static final int OUTLINE_FROM=2000,OUTLINE_DIRECTIONS=2048;
    /** -Dprojectseele.footOutlineR63=false walks every vertex of a dense foot, to measure against. */
    private static final boolean OUTLINE=!"false".equals(System.getProperty("projectseele.footOutlineR63"));
    static
    {
        List<float[]> all=new ArrayList<>();
        for(int x=-1;x<=1;x++)for(int y=-1;y<=1;y++)for(int z=-1;z<=1;z++)
            if(x!=0||y!=0||z!=0){var v=new Vector3f(x,y,z).normalize();all.add(new float[]{v.x,v.y,v.z});}
        DIRECTIONS=all.toArray(float[][]::new);
    }

    /** Called from the render thread only, as the mesh itself is. Empty when the unit has no mesh to draw. */
    static Points of(EvaUnit01Entity eva,String[] hullParts)
    {
        return KNOWN.computeIfAbsent(EvaBodyPose.rigKey(eva),rig->
        {
            String asset=eva.isExperimentalUnit()?eva.experimentalAssetName():"eva_unit0"+rig;
            var resource=new ResourceLocation("projectseele","mesh/"+asset+".mesh.json");
            var prepared=PREPARED.get(resource);
            if(prepared!=null)return prepared;
            try{return take(resource,hullParts,name->LocalTriangleMeshLayer.partView(resource,name),"on the render thread");}
            catch(RuntimeException failure){ProjectSeele.LOGGER.warn("R63 ground points unavailable for variant {} ({})",rig,asset,failure);return NONE;}
        });
    }

    /** On a resource reload: the meshes may have changed. */
    static void clear(){generation++;KNOWN.clear();PREPARED.clear();}

    /** Read when a mesh's parse is started, and handed back with its points. */
    static int generation(){return generation;}

    /**
     * From the worker that parsed a mesh ahead: take its points there. parts gives a part's vertices where the mesh
     * holds them. A mesh without feet is not a unit's body.
     */
    static void prepare(ResourceLocation resource,int started,Function<String,LocalTriangleMeshLayer.PartView> parts)
    {
        try
        {
            Points points=take(resource,PARTS,parts,"with the mesh");
            if(points!=NONE&&started==generation)PREPARED.put(resource,points);
        }
        catch(RuntimeException failure){ProjectSeele.LOGGER.warn("R63 ground points of {} not prepared",resource,failure);}
    }

    private static Points take(ResourceLocation resource,String[] hullParts,Function<String,LocalTriangleMeshLayer.PartView> parts,String where)
    {
        long started=System.nanoTime();
        Map<String,Vector3f[]> hulls=new HashMap<>(),feet=new HashMap<>(),outlines=new HashMap<>();
        // How far out the parts reach along the 26 directions, summed: what ground contact reads off the hulls.
        double reach=0;
        for(String name:hullParts)
        {
            var at=parts.apply(name);
            if(at==null)continue;
            int[] far=farthest(at,DIRECTIONS);
            List<Vector3f> kept=new ArrayList<>();
            for(int d=0;d<far.length;d++)
            {
                if(far[d]<0)continue;
                float[] direction=DIRECTIONS[d];float x=at.x(far[d]),y=at.y(far[d]),z=at.z(far[d]);
                reach+=x*direction[0]+y*direction[1]+z*direction[2];
                var point=new Vector3f(x,y,z);
                if(!kept.contains(point))kept.add(point);
            }
            if(!kept.isEmpty())hulls.put(name,kept.toArray(Vector3f[]::new));
        }
        for(String side:List.of("l","r"))
        {
            var at=parts.apply("foot_"+side);
            if(at==null)continue;
            // A triangle list repeats its corners; the lowest, foremost and rearmost vertex are the same without the repeats.
            LinkedHashSet<Vector3f> every=new LinkedHashSet<>();
            for(int vertex=0;vertex<at.count();vertex++)every.add(new Vector3f(at.x(vertex),at.y(vertex),at.z(vertex)));
            Vector3f[] all=every.toArray(Vector3f[]::new);
            feet.put(side,all);
            outlines.put(side,OUTLINE&&all.length>OUTLINE_FROM?outline(all):all);
        }
        if(hulls.isEmpty()&&feet.isEmpty())return NONE;
        // The two sums let these points be compared with the mesh file itself (tools/groundpoints.py).
        ProjectSeele.LOGGER.info("R63 ground points of {} taken {} in {} ms: {} hull parts (reach {}), soles of {} and {} vertices (sum {}), walked by {} and {}",
                resource.getPath(),where,(System.nanoTime()-started)/1_000_000L,hulls.size(),String.format(java.util.Locale.ROOT,"%.3f",reach),
                count(feet,"l"),count(feet,"r"),String.format(java.util.Locale.ROOT,"%.3f",sum(feet)),count(outlines,"l"),count(outlines,"r"));
        return new Points(hulls,feet,outlines);
    }

    /** For each direction the first vertex of the part farthest out along it, or -1 without vertices. */
    private static int[] farthest(LocalTriangleMeshLayer.PartView at,float[][] directions)
    {
        int n=directions.length;
        float[] dx=new float[n],dy=new float[n],dz=new float[n],score=new float[n];int[] far=new int[n];
        for(int d=0;d<n;d++){dx[d]=directions[d][0];dy[d]=directions[d][1];dz[d]=directions[d][2];}
        java.util.Arrays.fill(far,-1);java.util.Arrays.fill(score,Float.NEGATIVE_INFINITY);
        for(int vertex=0,count=at.count();vertex<count;vertex++)
        {
            float x=at.x(vertex),y=at.y(vertex),z=at.z(vertex);
            for(int d=0;d<n;d++)
            {
                float s=x*dx[d]+y*dy[d]+z*dz[d];
                if(s>score[d]){score[d]=s;far[d]=vertex;}
            }
        }
        return far;
    }

    /** For each direction the index (of its x) of the first of the points (x, y, z in turn) farthest out along it. */
    private static int[] farthest(float[] at,float[][] directions)
    {
        int n=directions.length;
        float[] dx=new float[n],dy=new float[n],dz=new float[n],score=new float[n];int[] far=new int[n];
        for(int d=0;d<n;d++){dx[d]=directions[d][0];dy[d]=directions[d][1];dz[d]=directions[d][2];}
        java.util.Arrays.fill(far,-1);java.util.Arrays.fill(score,Float.NEGATIVE_INFINITY);
        for(int i=0;i+2<at.length;i+=3)
        {
            float x=at[i],y=at[i+1],z=at[i+2];
            for(int d=0;d<n;d++)
            {
                float s=x*dx[d]+y*dy[d]+z*dz[d];
                if(s>score[d]){score[d]=s;far[d]=i;}
            }
        }
        return far;
    }

    /** The vertices farthest out along the outline's directions, each once, in the order they came in. */
    private static Vector3f[] outline(Vector3f[] all)
    {
        float[] at=new float[all.length*3];
        for(int i=0;i<all.length;i++){at[i*3]=all[i].x;at[i*3+1]=all[i].y;at[i*3+2]=all[i].z;}
        float[][] directions=new float[OUTLINE_DIRECTIONS+DIRECTIONS.length][];
        // Evenly over the sphere, along a spiral; the 26 are added so that straight down is always among them.
        double golden=Math.PI*(3-Math.sqrt(5));
        for(int i=0;i<OUTLINE_DIRECTIONS;i++)
        {
            double y=1-2*(i+.5)/OUTLINE_DIRECTIONS,ring=Math.sqrt(1-y*y),turn=golden*i;
            directions[i]=new float[]{(float)(Math.cos(turn)*ring),(float)y,(float)(Math.sin(turn)*ring)};
        }
        System.arraycopy(DIRECTIONS,0,directions,OUTLINE_DIRECTIONS,DIRECTIONS.length);
        java.util.TreeSet<Integer> kept=new java.util.TreeSet<>();
        for(int index:farthest(at,directions))if(index>=0)kept.add(index/3);
        Vector3f[] result=new Vector3f[kept.size()];int n=0;
        for(int index:kept)result[n++]=all[index];
        return result;
    }

    private static int count(Map<String,Vector3f[]> points,String side){return points.containsKey(side)?points.get(side).length:0;}

    /** x + 2y + 3z over every point kept, in blocks of the model. */
    private static double sum(Map<String,Vector3f[]> points)
    {
        double total=0;
        for(var part:points.values())for(var v:part)total+=v.x+2D*v.y+3D*v.z;
        return total;
    }

    private EvaMeshPointsR63() {}
}

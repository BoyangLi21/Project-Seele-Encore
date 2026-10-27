package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.*;

/** Offline candidate only. Does not grant an actor, lease or flight admission.
 * For a fixed translation, each initial triangle/block contact must
 * lose embedded material monotonically and be completely clear at the end.
 * This intentionally cannot certify joint motion, rotation or moving actors. */
public final class RescueTranslationEgressR53
{
    public record Part(String name,double[] worldTriangles)
    {
        public Part
        {
            Objects.requireNonNull(name);
            if(worldTriangles.length==0||worldTriangles.length%9!=0||Arrays.stream(worldTriangles).anyMatch(v->!Double.isFinite(v)))
                throw new IllegalArgumentException("Complete finite world triangles required");
            worldTriangles=worldTriangles.clone();
        }
        @Override public double[] worldTriangles(){return worldTriangles.clone();}
    }
    public record Result(boolean proved,String reason,String part,int triangle,int obstacle,
                         int initialContacts,int sweptPairs,double outwardRounding){}

    public static Result prove(List<Part> parts,List<AABB> blocks,Vec3 delta,double maximumTravel)
    {
        if(parts==null||parts.isEmpty()||blocks==null||delta==null||!Double.isFinite(delta.lengthSqr())
                ||!Double.isFinite(maximumTravel)||maximumTravel<=0||delta.length()==0||delta.length()>maximumTravel)
            throw new IllegalArgumentException("Finite bounded escape and complete immutable source required");
        int axis=-1,axes=0;
        for(int n=0;n<3;n++)if(at(delta,n)!=0){axis=n;axes++;}
        double extent=1;
        for(var part:parts)for(double value:part.worldTriangles)extent=Math.max(extent,Math.abs(value));
        for(var b:blocks)
        {
            for(double v:new double[]{b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ})
            {if(!Double.isFinite(v))throw new IllegalArgumentException("Finite actual obstacle required");extent=Math.max(extent,Math.abs(v));}
            if(b.getXsize()<=0||b.getYsize()<=0||b.getZsize()<=0)throw new IllegalArgumentException("Positive actual block volume required");
        }
        // Guard comparisons outward; no obstacle deflation or source-contact skip.
        double rounding=Math.max(1e-9,Math.ulp(extent+delta.length())*64);
        int contacts=0,pairs=0;boolean positive=at(delta,axis)>0;
        for(var part:parts)for(int n=0;n<part.worldTriangles.length;n+=9)
        {
            var source=new Vec3[3];var chord=new Vec3[6];var stationary=new Vec3[6];var end=new Vec3[6];
            for(int k=0;k<3;k++)
            {
                int i=n+k*3;source[k]=new Vec3(part.worldTriangles[i],part.worldTriangles[i+1],part.worldTriangles[i+2]);
                chord[k]=stationary[k]=stationary[k+3]=source[k];chord[k+3]=end[k]=end[k+3]=source[k].add(delta);
            }
            AABB broad=new AABB(source[0],source[0]);for(var p:chord)broad=broad.minmax(new AABB(p,p));broad=broad.inflate(rounding);
            for(int j=0;j<blocks.size();j++)
            {
                var block=blocks.get(j).inflate(rounding);if(!broad.intersects(block))continue;
                pairs++;
                if(!TriangleSweepMeshR52.convexSweepBox(chord,0,block))continue;
                if(!TriangleSweepMeshR52.convexSweepBox(stationary,0,block))
                    return new Result(false,"new_contact_in_sweep",part.name,n/9,j,contacts,pairs,rounding);
                contacts++;
                if(TriangleSweepMeshR52.convexSweepBox(end,0,block))
                    return new Result(false,"endpoint_still_embedded",part.name,n/9,j,contacts,pairs,rounding);
                if(axes>1)
                {
                    // Hold the material triangle fixed. The block's entry
                    // faces translate by -delta. Any crossing of those swept
                    // faces is newly embedded material, even if this triangle
                    // already intersected another part of the same block.
                    if(enters(stationary,block,delta,rounding))
                        return new Result(false,"material_enters_before_exit",part.name,n/9,j,contacts,pairs,rounding);
                    continue;
                }
                // In body material coordinates the two perpendicular slabs do
                // not change. Clip there, then forbid entry through the near
                // moving face. The remaining occupied interval only shrinks.
                List<Vec3> clipped=new ArrayList<>(List.of(source));
                for(int a=0;a<3;a++)if(a!=axis)
                {clipped=clip(clipped,a,low(block,a),true);clipped=clip(clipped,a,high(block,a),false);}
                if(clipped.isEmpty())return new Result(false,"ambiguous_clipping",part.name,n/9,j,contacts,pairs,rounding);
                double minimum=Double.POSITIVE_INFINITY,maximum=Double.NEGATIVE_INFINITY;
                for(var p:clipped){minimum=Math.min(minimum,at(p,axis));maximum=Math.max(maximum,at(p,axis));}
                if(positive?minimum<low(block,axis)+rounding:maximum>high(block,axis)-rounding)
                    return new Result(false,"material_enters_before_exit",part.name,n/9,j,contacts,pairs,rounding);
            }
        }
        return new Result(true,contacts==0?"strictly_clear":"monotone_source_exit","",-1,-1,contacts,pairs,rounding);
    }
    private static boolean enters(Vec3[] stationary,AABB block,Vec3 delta,double rounding)
    {
        for(int axis=0;axis<3;axis++)
        {
            if(at(delta,axis)==0)continue;double plane=at(delta,axis)>0?low(block,axis):high(block,axis);
            int a=(axis+1)%3,b=(axis+2)%3;var face=new Vec3[4];
            for(int corner=0;corner<4;corner++)
            {
                double[] v=new double[3];v[axis]=plane;v[a]=(corner&1)==0?low(block,a):high(block,a);v[b]=(corner&2)==0?low(block,b):high(block,b);face[corner]=new Vec3(v[0],v[1],v[2]);
            }
            for(var indices:new int[][]{{0,1,3},{0,3,2}})
            {
                var swept=new Vec3[6];for(int k=0;k<3;k++){swept[k]=face[indices[k]];swept[k+3]=swept[k].subtract(delta);}
                if(TriangleSweepMeshR52.convexSweepPair(stationary,swept,new Vec3(rounding,rounding,rounding)))return true;
            }
        }
        return false;
    }
    private static List<Vec3> clip(List<Vec3> polygon,int axis,double plane,boolean lower)
    {
        if(polygon.isEmpty())return polygon;var out=new ArrayList<Vec3>();var previous=polygon.get(polygon.size()-1);
        boolean was=lower?at(previous,axis)>=plane:at(previous,axis)<=plane;
        for(var next:polygon)
        {
            boolean is=lower?at(next,axis)>=plane:at(next,axis)<=plane;
            if(was!=is){double t=(plane-at(previous,axis))/(at(next,axis)-at(previous,axis));out.add(previous.add(next.subtract(previous).scale(t)));}
            if(is)out.add(next);previous=next;was=is;
        }
        return out;
    }
    private static double at(Vec3 p,int a){return a==0?p.x:a==1?p.y:p.z;}
    private static double low(AABB b,int a){return a==0?b.minX:a==1?b.minY:b.minZ;}
    private static double high(AABB b,int a){return a==0?b.maxX:a==1?b.maxY:b.maxZ;}
    private RescueTranslationEgressR53(){}
}

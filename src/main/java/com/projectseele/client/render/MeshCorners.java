package com.projectseele.client.render;

import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;

/**
 * A triangle soup repeats a surface point once per touching triangle. Corners with
 * equal position, normal and skinning influences transform to the same result, so
 * each group only needs transforming once and only UVs stay per corner.
 *
 * @param sources one corner of each group
 * @param inputs the group of every corner
 */
public record MeshCorners(int[] sources,int[] inputs)
{
    private record Key(int[] bits)
    {
        @Override public boolean equals(Object other){return other instanceof Key key&&Arrays.equals(bits,key.bits);}
        @Override public int hashCode(){return Arrays.hashCode(bits);}
    }

    /** @param vertices eight floats per corner with the position at 0 and the normal at 5 */
    public static MeshCorners of(float[] vertices){return of(vertices,null,null);}

    /** @param indices four bone indices per corner, or null for an unskinned mesh */
    public static MeshCorners of(float[] vertices,int[] indices,float[] weights)
    {
        int corners=vertices.length/8;int[] inputs=new int[corners],sources=new int[corners];
        Map<Key,Integer> seen=new HashMap<>();
        for(int corner=0;corner<corners;corner++)
        {
            int i=corner*8,j=corner*4;int[] bits=new int[indices==null?6:14];
            for(int k=0;k<3;k++){bits[k]=Float.floatToRawIntBits(vertices[i+k]);bits[3+k]=Float.floatToRawIntBits(vertices[i+5+k]);}
            if(indices!=null)for(int k=0;k<4;k++){bits[6+k]=indices[j+k];bits[10+k]=Float.floatToRawIntBits(weights[j+k]);}
            Key key=new Key(bits);Integer known=seen.get(key);
            if(known==null){known=seen.size();seen.put(key,known);sources[known]=corner;}
            inputs[corner]=known;
        }
        return new MeshCorners(Arrays.copyOf(sources,seen.size()),inputs);
    }
}

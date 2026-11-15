package com.projectseele.world;

import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/** Rail pieces with the same local shape share its arrays; every piece still reads exactly what the source wrote. */
public final class UprightSteelSharingR64Test
{
    private static int checks;
    private static void check(boolean value,String why){checks++;if(!value)throw new AssertionError(why);}

    /** Two triangles, six numbers a vertex (position, then colour). */
    private static double[] shape(double first,double red)
    {
        double[] xyz={first,0,0, 1,0,0, 0,0,1, 1,0,0, 1,0,1, 0,0,1};
        double[] rgb=new double[36];
        for(int v=0;v<6;v++){rgb[v*6]=xyz[v*3];rgb[v*6+1]=xyz[v*3+1];rgb[v*6+2]=xyz[v*3+2];rgb[v*6+3]=red;rgb[v*6+4]=.43;rgb[v*6+5]=.48;}
        return rgb;
    }

    private static String piece(String name,String leg,String component,double x,String numbers)
    {
        return "{\"name\":\""+name+"\",\"leg\":\""+leg+"\",\"side\":1,\"component\":\""+component+"\",\"frame\":{\"translation\":["+x
                +",2,3],\"quaternion_xyzw\":[0,0,0,1]},\"triangles_rgb\":["+numbers+"]}";
    }

    private static String numbers(double[] values)
    {
        var text=new StringBuilder();
        for(double value:values)text.append(text.length()==0?"":",").append(Double.toString(value));
        return text.toString();
    }

    public static void main(String[] args)throws Exception
    {
        double[] plain=shape(0,.36),negativeZero=shape(-0D,.36),otherColour=shape(0,.37);
        String document="{\"schema\":\"projectseele.r52.upright-captured-paths.v1\",\"supports_complete\":true,\"pieces\":["
                +piece("rail/0","unit0/exit1","head",10,numbers(plain))+","
                +piece("rail/1","unit0/exit1","head",11,numbers(plain))+","
                +piece("rail/2","unit0/exit2","web",12,numbers(negativeZero))+","
                +piece("rail/3","unit0/exit1","head",13,numbers(otherColour))+","
                +piece("rail/4","unit0/exit2","web",14,numbers(plain))
                +"],\"anchors\":[{\"leg\":\"unit0/exit1\",\"at\":[10,2,3],\"state\":\"minecraft:stone\",\"bearing\":[10,2.5,3.5],\"normal\":[-1,0,0],\"seat_piece\":\"rail/0\"}]}";
        List<NervUprightGuidewayR52.RailPiece> pieces=new ArrayList<>();List<NervUprightGuidewayR52.Anchor> anchors=new ArrayList<>();
        NervUprightGuidewayR52.readVisualR52(new ByteArrayInputStream(document.getBytes(StandardCharsets.UTF_8)),"",pieces::add,anchors::add);
        check(pieces.size()==5&&anchors.size()==1,"Every piece and anchor must be read");

        double[][] written={plain,plain,negativeZero,otherColour,plain};
        for(int i=0;i<pieces.size();i++)
        {
            var steel=pieces.get(i).steel();
            check(steel.rgb().length==36,"Vertex count changed");
            for(int n=0;n<36;n++)
                check(Double.doubleToRawLongBits(steel.rgb()[n])==Double.doubleToRawLongBits(written[i][n]),"Piece "+i+" reads a different number at "+n);
            double[] xyz=steel.mesh().triangles();
            check(xyz.length==18,"Mesh triangle count changed");
            for(int v=0;v<6;v++)for(int k=0;k<3;k++)
                check(Double.doubleToRawLongBits(xyz[v*3+k])==Double.doubleToRawLongBits(written[i][v*6+k]),"Piece "+i+" mesh differs from its vertices");
            check(steel.frame().translation().x==10+i,"Piece "+i+" lost its own frame");
            check(steel.name().equals("rail/"+i)&&pieces.get(i).name().equals("rail/"+i),"Piece "+i+" lost its name");
        }
        var first=pieces.get(0).steel();
        check(pieces.get(1).steel().rgb()==first.rgb()&&pieces.get(1).steel().mesh()==first.mesh(),"Equal shapes on one leg must share");
        check(pieces.get(4).steel().rgb()==first.rgb()&&pieces.get(4).steel().mesh()==first.mesh(),"Equal shapes on different legs must share");
        check(pieces.get(2).steel().rgb()!=first.rgb()&&pieces.get(2).steel().mesh()!=first.mesh(),"0.0 and -0.0 are different coordinates");
        check(pieces.get(3).steel().rgb()!=first.rgb()&&pieces.get(3).steel().mesh()!=first.mesh(),"A different colour is a different shape");
        check(!Arrays.equals(pieces.get(2).steel().rgb(),first.rgb()),"The -0.0 shape must keep its sign bit");
        check(pieces.get(0).leg()==pieces.get(1).leg()&&pieces.get(0).leg()==pieces.get(3).leg()&&pieces.get(2).leg()==pieces.get(4).leg(),"Equal leg names must be one string");
        check(pieces.get(0).leg().equals("unit0/exit1")&&pieces.get(2).leg().equals("unit0/exit2")&&pieces.get(2).component().equals("web"),"Leg or component text changed");
        // The shared mesh answers each piece in that piece's own frame.
        var a=pieces.get(0).steel();var b=pieces.get(1).steel();
        check(Math.abs(a.mesh().envelope(a.frame(),a.frame()).minX-10)<1e-9&&Math.abs(b.mesh().envelope(b.frame(),b.frame()).minX-11)<1e-9
                &&Math.abs(a.mesh().envelope(a.frame(),a.frame()).minX-10)<1e-9,"A shared mesh must not remember another piece's frame");
        System.out.println("Upright steel sharing checks passed: "+checks);
    }
}

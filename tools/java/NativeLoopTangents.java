import java.nio.file.*;
import java.util.*;
import org.mtr.core.data.*;
import org.mtr.core.tool.Angle;
import org.mtr.libraries.com.google.gson.*;

/** Fit continuous native tangents to an ordered offline loop, fixing platforms. */
public final class NativeLoopTangents
{
    private static final Angle[] A={Angle.E,Angle.SEE,Angle.SE,Angle.SSE,Angle.S,Angle.SSW,Angle.SW,Angle.SWW,
            Angle.W,Angle.NWW,Angle.NW,Angle.NNW,Angle.N,Angle.NNE,Angle.NE,Angle.NEE};
    private static Position pos(JsonArray a){return new Position(a.get(0).getAsLong(),a.get(1).getAsLong(),a.get(2).getAsLong());}
    private static int index(String a){return Arrays.asList(A).indexOf(Angle.valueOf(a));}
    private static int distance(int a,int b){return Math.abs((a-b+24)%16-8);}
    public static void main(String[] args)throws Exception
    {
        Path source=Path.of(args[0]),output=Path.of(args[1]);int count=Integer.parseInt(args[2]);
        JsonObject plan=JsonParser.parseString(Files.readString(source)).getAsJsonObject();JsonArray rails=plan.getAsJsonArray("rails");
        Position[] points=new Position[count+1];int[] preferred=new int[count+1],fixed=new int[count+1];Arrays.fill(fixed,-1);
        for(int i=0;i<count;i++)
        {
            JsonObject r=rails.get(i).getAsJsonObject();Position start=pos(r.getAsJsonArray("from")),end=pos(r.getAsJsonArray("to"));
            if(i>0&&!start.equals(points[i]))throw new IllegalArgumentException("Loop is not ordered");
            points[i]=start;points[i+1]=end;preferred[i]=index(r.get("from_angle").getAsString());preferred[i+1]=(index(r.get("to_angle").getAsString())+8)%16;
            if(r.get("kind").getAsString().equals("platform")){fixed[i]=preferred[i];fixed[i+1]=preferred[i+1];}
        }
        if(!points[0].equals(points[count]))throw new IllegalArgumentException("Expected a closed loop");
        fixed[0]=preferred[0];fixed[count]=preferred[0];
        double[][] cost=new double[count+1][16];int[][] previous=new int[count+1][16];for(double[] row:cost)Arrays.fill(row,Double.POSITIVE_INFINITY);
        cost[0][fixed[0]]=0;
        for(int i=0;i<count;i++)for(int a=0;a<16;a++)if(Double.isFinite(cost[i][a]))for(int b=0;b<16;b++)
        {
            if(fixed[i+1]>=0&&fixed[i+1]!=b||distance(b,preferred[i+1])>3)continue;
            RailMath curve=new RailMath(points[i],A[a],points[i+1],A[(b+8)%16],Rail.Shape.QUADRATIC,100);
            double length=curve.getLength(),straight=Math.hypot(points[i+1].getX()-points[i].getX(),points[i+1].getZ()-points[i].getZ());
            if(!Double.isFinite(length)||length<=0||length>straight*1.8)continue;
            double next=cost[i][a]+distance(b,preferred[i+1])*distance(b,preferred[i+1])*10+(length-straight)/Math.max(1,straight);
            if(next<cost[i+1][b]){cost[i+1][b]=next;previous[i+1][b]=a;}
        }
        if(!Double.isFinite(cost[count][fixed[count]]))throw new IllegalStateException("Move the control nodes; no bounded continuous tangent solution");
        int[] chosen=new int[count+1];chosen[count]=fixed[count];for(int i=count;i>0;i--)chosen[i-1]=previous[i][chosen[i]];
        int changed=0;
        for(int i=0;i<count;i++)
        {
            JsonObject r=rails.get(i).getAsJsonObject();r.addProperty("from_angle",A[chosen[i]].name());r.addProperty("to_angle",A[(chosen[i+1]+8)%16].name());
            if(chosen[i]!=preferred[i])changed++;
        }
        Files.writeString(output,new GsonBuilder().setPrettyPrinting().create().toJson(plan));
        System.out.println("Native loop tangents fitted: "+changed+" shared nodes; platforms unchanged");
    }
}

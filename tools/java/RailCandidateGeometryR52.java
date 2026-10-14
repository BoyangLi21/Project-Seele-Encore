import java.nio.file.*;
import org.mtr.core.data.*;
import org.mtr.core.tool.Angle;
import org.mtr.libraries.com.google.gson.*;

/** Read-only native MTR curve evaluation. No simulator/database/world writes. */
public final class RailCandidateGeometryR52
{
    private static Position point(JsonArray p){return new Position(p.get(0).getAsLong(),p.get(1).getAsLong(),p.get(2).getAsLong());}
    public static void main(String[] args)throws Exception
    {
        var input=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();var result=new JsonArray();
        double spacing=args.length>2?Double.parseDouble(args[2]):1;
        if(!Double.isFinite(spacing)||spacing<0.05||spacing>1)throw new IllegalArgumentException("Bounded native sample interval required");
        for(var raw:input.getAsJsonArray("segments"))
        {
            var row=raw.getAsJsonObject();var math=new RailMath(point(row.getAsJsonArray("from")),Angle.valueOf(row.get("from_angle").getAsString()),
                    point(row.getAsJsonArray("to")),Angle.valueOf(row.get("to_angle").getAsString()),Rail.Shape.valueOf(row.get("shape").getAsString()),row.get("vertical_radius").getAsDouble());
            double length=math.getLength();if(!Double.isFinite(length)||length<=0)
            {var invalid=new JsonObject();invalid.add("id",row.get("id"));invalid.addProperty("valid",false);invalid.addProperty("error","Invalid native rail length");result.add(invalid);continue;}
            var samples=new JsonArray();double lastX=0,lastY=0,lastZ=0,maximumGrade=0;
            int count=(int)Math.ceil(length/spacing);
            for(int n=0;n<=count;n++)
            {
                var v=math.getPosition(length*n/count,false);
                if(!Double.isFinite(v.x+v.y+v.z))throw new IllegalArgumentException("Nonfinite native sample");
                if(n>0){double horizontal=Math.hypot(v.x-lastX,v.z-lastZ);if(horizontal>1e-8)maximumGrade=Math.max(maximumGrade,Math.abs(v.y-lastY)/horizontal);}
                var p=new JsonArray();p.add(v.x);p.add(v.y);p.add(v.z);samples.add(p);lastX=v.x;lastY=v.y;lastZ=v.z;
            }
            var out=new JsonObject();out.add("id",row.get("id"));out.addProperty("valid",true);out.addProperty("native_length",length);out.addProperty("maximum_sampled_grade",maximumGrade);
            out.addProperty("effective_vertical_radius",math.getVerticalRadius());out.add("points",samples);result.add(out);
        }
        Files.writeString(Path.of(args[1]),new Gson().toJson(result));System.out.println("Evaluated "+result.size()+" actual MTR curves; world/database untouched");
    }
}

import java.nio.file.*;
import java.lang.reflect.Method;
import org.mtr.core.data.*;
import org.mtr.core.tool.Angle;
import org.mtr.libraries.com.google.gson.*;

/** Pure pinned MTR RailMath; never creates a simulator or writes a database. */
public final class NativeHQGeometryCandidate
{
    private static Position pos(JsonArray a) { return new Position(a.get(0).getAsLong(),a.get(1).getAsLong(),a.get(2).getAsLong()); }
    public static void main(String[] args) throws Exception
    {
        var input=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        var output=new JsonArray();double step=Double.parseDouble(args[2]);
        if(step<.05||step>1)throw new IllegalArgumentException("Bounded sample step required");
        Method valid=RailMath.class.getDeclaredMethod("isValid");valid.setAccessible(true);
        for(var raw:input.getAsJsonArray("segments"))
        {
            var r=raw.getAsJsonObject();var math=new RailMath(pos(r.getAsJsonArray("from")),Angle.valueOf(r.get("from_angle").getAsString()),pos(r.getAsJsonArray("to")),Angle.valueOf(r.get("to_angle").getAsString()),Rail.Shape.valueOf(r.get("shape").getAsString()),r.get("vertical_radius").getAsDouble());
            double length=math.getLength();var row=new JsonObject();row.add("id",r.get("id"));
            row.addProperty("valid",(boolean)valid.invoke(math)&&Double.isFinite(length)&&length>0);
            row.addProperty("native_length",length);row.addProperty("horizontal_radii",math.getHorizontalRadii().toString());
            row.addProperty("effective_vertical_radius",math.getVerticalRadius());
            var points=new JsonArray();double px=0,py=0,pz=0,grade=0;
            if(Double.isFinite(length)&&length>0)
            {
                int n=(int)Math.ceil(length/step);
                for(int i=0;i<=n;i++)
                {
                    var v=math.getPosition(length*i/n,false);var a=new JsonArray();a.add(v.x);a.add(v.y);a.add(v.z);points.add(a);
                    if(i>0&&Math.hypot(v.x-px,v.z-pz)>1e-9)grade=Math.max(grade,Math.abs(v.y-py)/Math.hypot(v.x-px,v.z-pz));
                    px=v.x;py=v.y;pz=v.z;
                }
            }
            row.add("points",points);row.addProperty("maximum_sampled_grade",grade);output.add(row);
        }
        Files.writeString(Path.of(args[1]),new Gson().toJson(output));
        System.out.println("Read-only native geometry: "+output.size()+" rails");
    }
}

import java.nio.file.*;
import org.mtr.core.data.Rail;
import org.mtr.core.serializer.JsonReader;
import org.mtr.libraries.com.google.gson.*;

/** Evaluate exact serialized native rail members without a simulator or writes to a save. */
public final class SavedRailGeometrySurvey {
    public static void main(String[] args) throws Exception {
        JsonArray input=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonArray();
        JsonArray output=new JsonArray();
        double spacing=args.length>2?Double.parseDouble(args[2]):.25;
        if(!Double.isFinite(spacing)||spacing<.05||spacing>1)throw new IllegalArgumentException("Invalid bounded sampling interval");
        for(JsonElement entry:input){
            JsonObject item=entry.getAsJsonObject();
            Rail rail=new Rail(new JsonReader(item.getAsJsonObject("data")));
            JsonObject row=new JsonObject();row.add("id",item.get("id"));row.addProperty("valid",rail.isValid());
            String nativeId=rail.getHexId();
            row.addProperty("native_relative_path","projectseele/geofront/rails/"+nativeId.substring(Math.max(0,nativeId.length()-2))+"/"+nativeId);
            if(!rail.isValid()){output.add(row);continue;}
            double length=rail.railMath.getLength(),grade=0;int count=(int)Math.ceil(length/spacing);
            JsonArray points=new JsonArray();double px=0,py=0,pz=0;
            for(int i=0;i<=count;i++){
                var q=rail.railMath.getPosition(length*i/count,false);JsonArray point=new JsonArray();
                point.add(q.x);point.add(q.y);point.add(q.z);points.add(point);
                if(i>0){double horizontal=Math.hypot(q.x-px,q.z-pz);if(horizontal>1e-8)grade=Math.max(grade,Math.abs(q.y-py)/horizontal);}
                px=q.x;py=q.y;pz=q.z;
            }
            row.addProperty("length",length);row.addProperty("maximum_sampled_grade",grade);
            row.addProperty("effective_vertical_radius",rail.railMath.getVerticalRadius());row.add("points",points);output.add(row);
        }
        Files.writeString(Path.of(args[1]),new Gson().toJson(output));
        System.out.println("Evaluated "+output.size()+" exact saved Rail objects; no simulator or world writes");
    }
}

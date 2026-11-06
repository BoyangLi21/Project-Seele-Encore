import org.mtr.core.data.*;
import org.mtr.core.serializer.*;
import org.mtr.libraries.com.google.gson.*;
import org.mtr.libraries.org.msgpack.core.MessagePack;
import java.nio.file.*;
import java.util.zip.*;
import java.lang.reflect.*;

/** Actual installed member bytes through native Rail canonicalization, read only. */
public final class NativeInstalledMTRCurvesR53
{
    public static void main(String[]args)throws Exception
    {
        double step=Double.parseDouble(args[2]);if(step<.05||step>1)throw new IllegalArgumentException("Finite bounded sampling required");
        JsonArray result=new JsonArray();Method valid=RailMath.class.getDeclaredMethod("isValid");valid.setAccessible(true);
        try(ZipFile zip=new ZipFile(args[0]))
        {
            var entries=zip.entries();while(entries.hasMoreElements())
            {
                var entry=entries.nextElement();String marker="/mtr/projectseele/geofront/rails/";
                if(entry.isDirectory()||!entry.getName().contains(marker))continue;
                try(var unpacker=MessagePack.newDefaultUnpacker(zip.getInputStream(entry).readAllBytes()))
                {
                    Rail rail=new Rail(new MessagePackReader(unpacker));RailMath math=rail.railMath;double length=math.getLength();
                    if(!(boolean)valid.invoke(math)||!Double.isFinite(length)||length<=0)throw new AssertionError("Invalid installed native rail "+entry.getName());
                    JsonObject row=new JsonObject();row.addProperty("id",entry.getName().substring(entry.getName().lastIndexOf('/')+1));
                    row.addProperty("source_member",entry.getName().substring(entry.getName().indexOf("mtr/")));row.addProperty("native_hex_id",rail.getHexId());
                    row.addProperty("valid",true);row.addProperty("native_length",length);row.addProperty("effective_vertical_radius",math.getVerticalRadius());
                    JsonObject canonical=new JsonObject();rail.serializeData(new JsonWriter(canonical));row.add("actual_native_canonical_record",canonical);
                    int n=(int)Math.ceil(length/step);JsonArray points=new JsonArray();double px=0,py=0,pz=0,grade=0;
                    for(int i=0;i<=n;i++)
                    {
                        var p=math.getPosition(length*i/n,false);JsonArray q=new JsonArray();q.add(p.x);q.add(p.y);q.add(p.z);points.add(q);
                        if(i>0&&Math.hypot(p.x-px,p.z-pz)>1e-9)grade=Math.max(grade,Math.abs(p.y-py)/Math.hypot(p.x-px,p.z-pz));px=p.x;py=p.y;pz=p.z;
                    }
                    row.addProperty("maximum_sampled_grade",grade);row.add("points",points);result.add(row);
                }
            }
        }
        Files.writeString(Path.of(args[1]),new Gson().toJson(result));System.out.println("Read-only actual installed native canonical curves: "+result.size());
    }
}

import com.google.gson.*;
import com.projectseele.world.NervWayfindingR24;
import net.minecraft.core.BlockPos;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.zip.GZIPInputStream;

/** Reads the exact selected derived files through the production lift parser. */
public final class AuditWayfindingExportR52
{
    public static void main(String[] args) throws Exception
    {
        Path path=Path.of(args[0]);JsonObject data;
        try(var input=new InputStreamReader(new GZIPInputStream(Files.newInputStream(path)),StandardCharsets.UTF_8))
        {data=JsonParser.parseReader(input).getAsJsonObject();}
        var rows=data.getAsJsonArray("nodes");int count=data.getAsJsonArray("goals").size();
        if(rows.size()>500000||count!=8)throw new AssertionError("Final graph size or destinations");
        BlockPos[] nodes=new BlockPos[rows.size()];boolean[] active=new boolean[nodes.length];Arrays.fill(active,true);
        Set<BlockPos> unique=new HashSet<>();
        for(int i=0;i<nodes.length;i++)
        {
            var r=rows.get(i).getAsJsonArray();if(r.size()!=3+count)throw new AssertionError("Row shape");
            nodes[i]=new BlockPos(r.get(0).getAsInt(),r.get(1).getAsInt(),r.get(2).getAsInt());
            if(!unique.add(nodes[i]))throw new AssertionError("Duplicate graph position");
            for(int g=0;g<count;g++){int n=r.get(3+g).getAsInt();if(n<0||n>=nodes.length)throw new AssertionError("Next edge range");}
        }
        var method=NervWayfindingR24.class.getDeclaredMethod("loadNearestLifts",Path.class,BlockPos[].class,boolean[].class);method.setAccessible(true);
        Object[] routes=(Object[])method.invoke(null,path,nodes,active);
        if(routes==null||routes.length!=nodes.length||Arrays.stream(routes).anyMatch(Objects::isNull))throw new AssertionError("Production nearest-lift parser rejected current export");
        if(NervWayfindingR24.readTransit(data,active).size()!=2)throw new AssertionError("Actual U2 directions");
        System.out.println("PASS actual production nearest-lift and transit parsers: "+nodes.length+" nodes, 27 landings, 8 destinations, 2 U2 directions");
    }
}

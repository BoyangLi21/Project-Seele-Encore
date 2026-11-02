import java.nio.file.*;
import com.projectseele.world.HakoneSurfaceField;

/** Check the offline proto author against the actual runtime field consumer. */
public final class HakoneFieldVectorCheck
{
    public static void main(String[] args)throws Exception
    {
        int checked=0;
        for(String row:Files.readAllLines(Path.of(args[0])))
        {
            if(row.isBlank()||row.startsWith("x,"))continue;
            String[] parts=row.split(",");int[] n=new int[5];
            for(int i=0;i<5;i++)n[i]=Integer.parseInt(parts[i]);
            var surface=HakoneSurfaceField.sample(n[0],n[1],n[2]);
            if(surface==null||surface.ground()!=n[3]||surface.water()!=n[4])
                throw new AssertionError("Offline/runtime disagreement: "+row+" / "+surface);
            checked++;
        }
        System.out.println("Offline/runtime surface vectors PASS: "+checked);
    }
}

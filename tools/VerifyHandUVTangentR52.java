import com.google.gson.*;
import net.irisshaders.iris.vertices.NormalHelper;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;

/** Isolated real-Oculus UV/tangent regression. No Minecraft or GL context. */
public final class VerifyHandUVTangentR52
{
    private static float get(JsonArray a, int i) { return a.get(i).getAsFloat(); }
    private static float[] normal(JsonArray a, int base)
    {
        return new float[]{get(a, base + 5), get(a, base + 6), get(a, base + 7)};
    }
    private static int packed(JsonArray a, int base, float[] n)
    {
        return NormalHelper.computeTangent(n[0], n[1], n[2],
                get(a, base), get(a, base+1), get(a, base+2), get(a, base+3), get(a, base+4),
                get(a, base+8), get(a, base+9), get(a, base+10), get(a, base+11), get(a, base+12),
                get(a, base+16), get(a, base+17), get(a, base+18), get(a, base+19), get(a, base+20));
    }
    private static double crossLength(int packed, float[] n)
    {
        double x=(byte)packed, y=(byte)(packed >> 8), z=(byte)(packed >> 16);
        double nt=Math.sqrt(x*x+y*y+z*z), nn=Math.sqrt(n[0]*n[0]+n[1]*n[1]+n[2]*n[2]);
        if(nt==0 || nn==0)throw new AssertionError("Zero tangent or normal");
        double c=(x*n[0]+y*n[1]+z*n[2])/(nt*nn);
        return Math.sqrt(Math.max(0,1-c*c));
    }
    private static float[] face(JsonArray a,int base)
    {
        float x=get(a,base+8)-get(a,base), y=get(a,base+9)-get(a,base+1), z=get(a,base+10)-get(a,base+2);
        float u=get(a,base+16)-get(a,base), v=get(a,base+17)-get(a,base+1), w=get(a,base+18)-get(a,base+2);
        return new float[]{y*w-z*v,z*u-x*w,x*v-y*u};
    }
    private static void finiteUnpackedTangent(JsonArray a,int b)
    {
        float du1=get(a,b+11)-get(a,b+3), dv1=get(a,b+12)-get(a,b+4);
        float du2=get(a,b+19)-get(a,b+3), dv2=get(a,b+20)-get(a,b+4);
        float determinant=du1*dv2-du2*dv1;
        if(!Float.isFinite(determinant)||determinant==0)throw new AssertionError("UV determinant");
        float inv=1/determinant, length=0;
        for(int j=0;j<3;j++)
        {
            float t=inv*(dv2*(get(a,b+8+j)-get(a,b+j))-dv1*(get(a,b+16+j)-get(a,b+j)));
            if(!Float.isFinite(t))throw new AssertionError("Nonfinite raw tangent");
            length+=t*t;
        }
        if(!Float.isFinite(length)||length==0)throw new AssertionError("Nonfinite or zero tangent length");
    }
    public static void main(String[] args) throws Exception
    {
        JsonObject report=new JsonObject(); report.addProperty("schema","projectseele.r52.actual-oculus-hand-tangent.v1");
        JsonArray units=new JsonArray(); long total=0, zeroBefore=0, nativeCalls=0; double minimum=1;
        for(int unit=0;unit<(args.length>3?1:3);unit++)
        {
            String relative=args.length>3?args[3]:"assets/projectseele/mesh/eva_unit0"+unit+"_anatomical_hands_r45.mesh.json";
            JsonObject before=JsonParser.parseString(Files.readString(Path.of(args[0]).resolve(relative))).getAsJsonObject();
            JsonObject after=JsonParser.parseString(Files.readString(Path.of(args[1]).resolve(relative))).getAsJsonObject();
            long triangles=0; double unitMinimum=1;
            for(var entry:after.getAsJsonObject("parts").entrySet())
            {
                if(args.length>4 && !java.util.Arrays.asList(args[4].split(",")).contains(entry.getKey()))continue;
                JsonArray a=entry.getValue().getAsJsonObject().getAsJsonArray("vertices");
                JsonArray old=before.getAsJsonObject("parts").getAsJsonObject(entry.getKey()).getAsJsonArray("vertices");
                if(a.size()%24!=0)throw new AssertionError("Triangle stream");
                for(int b=0;b<a.size();b+=24)
                {
                    if(args.length>3)
                    {
                        boolean changed=false;
                        for(int v=0;v<3;v++)for(int uv=3;uv<=4;uv++)
                            changed|=!a.get(b+v*8+uv).equals(old.get(b+v*8+uv));
                        if(!changed)continue;
                    }
                    finiteUnpackedTangent(a,b); triangles++; total++;
                    float[][] normals={face(a,b),normal(a,b),normal(a,b+8),normal(a,b+16)};
                    for(float[] n:normals)
                    {
                        int oldT=packed(old,b,n), newT=packed(a,b,n); nativeCalls+=2;
                        if((oldT&0xffffff)==0)zeroBefore++;
                        else if(args.length<=3)throw new AssertionError("Expected frozen constant-UV regression");
                        double c=crossLength(newT,n); unitMinimum=Math.min(unitMinimum,c);
                        if(!Double.isFinite(c)||c<0.6)throw new AssertionError("Tangent parallel to vertex normal: "+c);
                        if(Math.abs((byte)(newT>>24))!=127)throw new AssertionError("Invalid tangent handedness");
                    }
                }
            }
            minimum=Math.min(minimum,unitMinimum);
            JsonObject u=new JsonObject();u.addProperty("unit",unit);u.addProperty("triangles",triangles);
            u.addProperty("minimum_packed_tangent_normal_cross_length",unitMinimum);units.add(u);
        }
        report.add("units",units); report.addProperty("triangles",total);
        report.addProperty("actual_NormalHelper_calls_before_and_after",nativeCalls);
        report.addProperty("zero_tangent_cases_before",zeroBefore);
        report.addProperty("nonzero_tangent_cases_before",nativeCalls/2-zeroBefore);
        report.addProperty("zero_or_nonfinite_tangent_cases_after",0);
        report.addProperty("minimum_packed_tangent_normal_cross_length",minimum);
        report.addProperty("native_game_or_GL_started",false);
        Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(report)+"\n",StandardCharsets.UTF_8);
        System.out.println("PASS real Oculus: "+total+" triangles / "+nativeCalls+" calls, minimum normal cross="+minimum);
    }
}

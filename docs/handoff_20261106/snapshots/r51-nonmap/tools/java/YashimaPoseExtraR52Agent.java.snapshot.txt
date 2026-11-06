import java.lang.instrument.Instrumentation;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;

/** Additional readback of the already explicitly scoped native pose actor; no entity construction or world copying. */
public final class YashimaPoseExtraR52Agent
{
    private static double[] xyz(Object v)throws Exception{return new double[]{v.getClass().getField("x").getFloat(v),v.getClass().getField("y").getFloat(v),v.getClass().getField("z").getFloat(v)};}
    private static float[] quat(Object q)throws Exception{return new float[]{q.getClass().getField("x").getFloat(q),q.getClass().getField("y").getFloat(q),q.getClass().getField("z").getFloat(q),q.getClass().getField("w").getFloat(q)};}
    private static Method execute(Object object)throws Exception{for(String name:new String[]{"execute","m_18701_"})try{return object.getClass().getMethod(name,Runnable.class);}catch(NoSuchMethodException ignored){}throw new NoSuchMethodException("native execute");}
    public static void agentmain(String arg,Instrumentation instrumentation)throws Exception
    {
        if(!"yashima-pose-r52".equals(System.getProperty("projectseele.regionalBuild")))throw new IllegalStateException("Not the explicitly existing pose fixture");
        var classes=new HashMap<String,Class<?>>();for(var c:instrumentation.getAllLoadedClasses())classes.put(c.getName(),c);
        var previous=classes.get("YashimaPoseCaptureR52Agent");var ef=previous.getDeclaredField("eva");var sf=previous.getDeclaredField("server");var mf=previous.getDeclaredField("minecraft");ef.setAccessible(true);sf.setAccessible(true);mf.setAccessible(true);
        Object eva=ef.get(null),server=sf.get(null),minecraft=mf.get(null);if(eva==null||server==null)throw new IllegalStateException("Explicit native pose actor not initialized");
        Path output=Path.of(System.getProperty("projectseele.poseCaptureOutputR52"));
        execute(server).invoke(server,(Runnable)()->{try{
            var ec=classes.get("com.projectseele.entity.EvaUnit01Entity");var bc=classes.get("com.projectseele.entity.EvaBodyPose");Object pose=bc.getMethod("sample",ec,float.class).invoke(null,eva,0F);
            Object world=classes.get("com.projectseele.entity.EvaRifleKinematics").getMethod("world",ec,float.class).invoke(null,eva,0F);
            var result=new LinkedHashMap<String,Object>();var feet=new LinkedHashMap<String,Object>();
            for(String side:List.of("l","r")){Object v=bc.getMethod("lowestRigidFootR44",ec,pose.getClass(),String.class).invoke(null,eva,pose,side);if(v==null)throw new IllegalStateException("Actual source shoe support absent");Object p=world.getClass().getMethod("transformPosition",classes.get("org.joml.Vector3f")).invoke(world,v);feet.put(side,xyz(p));}result.put("actual_lowest_shoe_vertices_world",feet);
            @SuppressWarnings("unchecked") Map<String,Object> rig=(Map<String,Object>)pose.getClass().getField("rig").get(pose);
            @SuppressWarnings("unchecked") Map<String,Object> rotations=(Map<String,Object>)pose.getClass().getField("rotations").get(pose);
            @SuppressWarnings("unchecked") Map<String,Object> positions=(Map<String,Object>)pose.getClass().getField("positions").get(pose);var bones=new LinkedHashMap<String,Object>();
            for(var b:rig.entrySet()){var row=new LinkedHashMap<String,Object>();row.put("parent",b.getValue().getClass().getMethod("parent").invoke(b.getValue()));row.put("pivot",xyz(b.getValue().getClass().getMethod("pivot").invoke(b.getValue())));row.put("quaternion_xyzw",quat(rotations.get(b.getKey())));row.put("position",xyz(positions.get(b.getKey())));bones.put(b.getKey(),row);}result.put("actual_local_bones",bones);
            Object gson=classes.get("com.google.gson.Gson").getConstructor().newInstance();Files.writeString(output.resolve("native_prone_cannon_extra.json"),(String)gson.getClass().getMethod("toJson",Object.class).invoke(gson,result));
        }catch(Throwable failure){try{Files.writeString(output.resolve("extra_failure.txt"),failure.toString());}catch(Exception ignored){}throw new RuntimeException(failure);}});
        execute(minecraft).invoke(minecraft,(Runnable)()->{try{Object options=null;var ot=classes.get("net.minecraft.client.Options");for(var f:minecraft.getClass().getFields())if(f.getType()==ot)options=f.get(minecraft);var ct=classes.get("net.minecraft.client.CameraType");Object third=Enum.valueOf((Class)ct,"THIRD_PERSON_BACK");for(var m:ot.getMethods())if(m.getParameterCount()==1&&m.getParameterTypes()[0]==ct&&m.getReturnType()==void.class){m.invoke(options,third);break;}}catch(Exception error){throw new RuntimeException(error);}});
    }
}

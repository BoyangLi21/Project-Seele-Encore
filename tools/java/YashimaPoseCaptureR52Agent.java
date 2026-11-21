import java.lang.instrument.Instrumentation;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.Consumer;
import org.objectweb.asm.*;

/** One explicitly named existing flat native fixture; samples production pose/FK, never construction WORLD_R52. */
public final class YashimaPoseCaptureR52Agent
{
    private static Map<String,Class<?>> classes;private static Object minecraft,server,eva,player;private static double[] before;private static Object mode;
    private static final String TAG="seele_yashima_pose_capture_r52";
    private static final String HOOK="seele.yashima.powered.render.capture.r52";
    private static long serverStable=-1,clientStable=-1;private static volatile boolean requested,captured;private static ScheduledExecutorService monitor;
    private static Instrumentation instrumentation;
    private static Method method(Class<?> type,String[] names,Class<?>... parameters)throws Exception
    {for(String name:names)try{return type.getMethod(name,parameters);}catch(NoSuchMethodException ignored){}throw new NoSuchMethodException(type+" "+Arrays.toString(names));}
    private static Method returns(Class<?> type,String result,int argc)throws Exception
    {for(var m:type.getMethods())if(m.getParameterCount()==argc&&m.getReturnType().getName().equals(result))return m;throw new NoSuchMethodException(type+" returns "+result);}
    private static Object call(Object target,String[] names,Class<?>[] parameters,Object... args)throws Exception
    {return method(target.getClass(),names,parameters).invoke(target,args);}
    private static double[] xyz(Object v)throws Exception
    {if(!v.getClass().getName().equals("org.joml.Vector3f"))v=returns(v.getClass(),"org.joml.Vector3f",0).invoke(v);return new double[]{v.getClass().getField("x").getFloat(v),v.getClass().getField("y").getFloat(v),v.getClass().getField("z").getFloat(v)};}
    private static void json(Path path,Object value)throws Exception
    {var gson=classes.get("com.google.gson.Gson").getConstructor().newInstance();String text=(String)gson.getClass().getMethod("toJson",Object.class).invoke(gson,value);Files.createDirectories(path.getParent());Files.writeString(path,text);}
    public static void agentmain(String arg,Instrumentation instrumentation)throws Exception
    {
        YashimaPoseCaptureR52Agent.instrumentation=instrumentation;
        if(!"yashima-pose-r52".equals(System.getProperty("projectseele.regionalBuild")))throw new IllegalStateException("Wrong explicitly isolated calibration mode");
        if(arg.equals("setup"))System.setProperty("projectseele.poseCaptureOutputR52",Path.of(System.getProperty("projectseele.poseCaptureOutputR52")).resolveSibling("calibration_powered").toAbsolutePath().toString());
        classes=new HashMap<>();for(var c:instrumentation.getAllLoadedClasses())classes.put(c.getName(),c);
        Class<?> mc=classes.get("net.minecraft.client.Minecraft");minecraft=returns(mc,"net.minecraft.client.Minecraft",0).invoke(null);
        server=returns(mc,"net.minecraft.client.server.IntegratedServer",0).invoke(minecraft);if(server==null)throw new IllegalStateException("Integrated native fixture not yet ready");
        var resource=classes.get("net.minecraft.world.level.storage.LevelResource");Object root=null;
        for(var f:resource.getFields())if(f.getType()==resource){Object value=f.get(null);boolean isRoot=value.toString().equals(".");
            for(var m:resource.getMethods())if(m.getParameterCount()==0&&m.getReturnType()==String.class&&m.invoke(value).equals("."))isRoot=true;
            if(isRoot){root=value;break;}}
        if(root==null)throw new IllegalStateException("Native world root key unavailable");
        Path world=(Path)returns(server.getClass(),"java.nio.file.Path",1).invoke(server,root);
        Path allowed=Path.of(System.getProperty("projectseele.poseCaptureWorldR52")).toAbsolutePath().normalize();
        if(!world.toAbsolutePath().normalize().equals(allowed)||!allowed.getFileName().toString().equals("SEELE_FIRST_BATTLE_REVIEW_R10"))throw new IllegalStateException("Refused nonfixture world: "+world);
        Path out=Path.of(System.getProperty("projectseele.poseCaptureOutputR52")).toAbsolutePath();
        Runnable operation=()->{try{if(arg.equals("setup"))setup();else if(arg.equals("sample"))sample(out);else if(arg.equals("cleanup"))cleanup();else throw new IllegalArgumentException(arg);}catch(Throwable failure){try{Files.writeString(out.resolve("failure.txt"),arg+": "+failure);json(out.resolve("failure.json"),Map.of("operation",arg,"error",failure.toString()));}catch(Exception ignored){}throw new RuntimeException(failure);}};
        method(server.getClass(),new String[]{"execute","m_18701_"},Runnable.class).invoke(server,operation);
    }
    private static void setup()throws Exception
    {
        var level=returns(server.getClass(),"net.minecraft.server.level.ServerLevel",0).invoke(server);
        Object list=returns(server.getClass(),"net.minecraft.server.players.PlayerList",0).invoke(server);
        @SuppressWarnings("unchecked") List<Object> players=(List<Object>)call(list,new String[]{"getPlayers","m_11314_"},new Class<?>[0]);
        if(players.size()!=1)throw new IllegalStateException("One real native fixture player required");player=players.get(0);
        before=xyz(call(player,new String[]{"position","m_20182_"},new Class<?>[0]));
        var gameType=classes.get("net.minecraft.world.level.GameType");Object creative=Enum.valueOf((Class)gameType,"CREATIVE");
        for(var f:player.getClass().getFields())if(f.getType().getName().equals("net.minecraft.server.level.ServerPlayerGameMode"))
        {Object controller=f.get(player);try{mode=method(controller.getClass(),new String[]{"getGameModeForPlayer","m_9290_"}).invoke(controller);}catch(Exception ignored){}break;}
        method(player.getClass(),new String[]{"setGameMode","m_143403_"},gameType).invoke(player,creative);
        call(player,new String[]{"stopRiding","m_8127_"},new Class<?>[0]);
        for(int x=10;x<=14;x++)for(int z=10;z<=14;z++)call(level,new String[]{"getChunk","m_6325_"},new Class<?>[]{int.class,int.class},x,z);
        Class<?> entities=classes.get("com.projectseele.registry.ModEntities");Object registry=entities.getField("EVA_UNIT01").get(null);Object type=registry.getClass().getMethod("get").invoke(registry);
        var levelClass=classes.get("net.minecraft.world.level.Level");eva=method(type.getClass(),new String[]{"create","m_20615_"},levelClass).invoke(type,level);
        eva.getClass().getMethod("prepareForMotionLab").invoke(eva);eva.getClass().getMethod("selectMotionLabWeapon",int.class).invoke(eva,2);
        call(eva,new String[]{"addTag","m_20049_"},new Class<?>[]{String.class},TAG);
        call(eva,new String[]{"moveTo","m_7678_"},new Class<?>[]{double.class,double.class,double.class,float.class,float.class},200D,-60D,200D,0F,0F);
        call(eva,new String[]{"setOnGround","m_6853_"},new Class<?>[]{boolean.class},true);
        var entityClass=classes.get("net.minecraft.world.entity.Entity");
        if(!(Boolean)method(level.getClass(),new String[]{"addFreshEntity","m_7967_"},entityClass).invoke(level,eva))throw new IllegalStateException("Actual native entity admission failed");
        call(player,new String[]{"teleportTo","m_6021_"},new Class<?>[]{double.class,double.class,double.class},200D,-45D,195D);
        if(!(Boolean)method(player.getClass(),new String[]{"startRiding","m_7998_"},entityClass,boolean.class).invoke(player,eva,true))throw new IllegalStateException("Actual native player boarding failed");
        eva.getClass().getMethod("toggleProne",classes.get("net.minecraft.server.level.ServerPlayer")).invoke(eva,player);
        // This disposable fixture now uses the ordinary closed pilot circuit
        // and one full normal battery; lab power bypass cannot qualify it.
        setData("DATA_MOTION_LAB_ACTIVE",false);setData("DATA_POWER_TICKS",eva.getClass().getMethod("getPowerCapacityTicks").invoke(eva));
        serverStable=clientStable=-1;captured=false;requested=false;installRenderHook();
        monitor=Executors.newSingleThreadScheduledExecutor(r->{var t=new Thread(r,"yashima-powered-native-monitor");t.setDaemon(true);return t;});
        monitor.scheduleAtFixedRate(()->{try{method(server.getClass(),new String[]{"execute","m_18701_"},Runnable.class).invoke(server,(Runnable)()->{try{probeServer();}catch(Exception failure){throw new RuntimeException(failure);}});}catch(Exception failure){throw new RuntimeException(failure);}},0,100,TimeUnit.MILLISECONDS);
        method(minecraft.getClass(),new String[]{"execute","m_18701_"},Runnable.class).invoke(minecraft,(Runnable)()->{try{
            for(var f:minecraft.getClass().getFields())if(f.getType().getName().equals("net.minecraft.client.Options")){var options=f.get(minecraft);var cameraType=classes.get("net.minecraft.client.CameraType");method(options.getClass(),new String[]{"setCameraType","m_92180_"},cameraType).invoke(options,Enum.valueOf((Class)cameraType,"THIRD_PERSON_BACK"));break;}
        }catch(Exception failure){throw new RuntimeException(failure);}});
    }
    private static void setData(String name,Object value)throws Exception
    {var field=classes.get("com.projectseele.entity.EvaUnit01Entity").getDeclaredField(name);field.setAccessible(true);var data=call(eva,new String[]{"getEntityData","m_20088_"},new Class<?>[0]);method(data.getClass(),new String[]{"set","m_135381_"},classes.get("net.minecraft.network.syncher.EntityDataAccessor"),Object.class).invoke(data,field.get(null),value);}
    private static long tick(Object actor)throws Exception
    {var level=call(actor,new String[]{"level","m_9236_"},new Class<?>[0]);return (Long)call(level,new String[]{"getGameTime","m_46467_"},new Class<?>[0]);}
    private static boolean good(Object actor)throws Exception
    {var ec=classes.get("com.projectseele.entity.EvaUnit01Entity");return (Boolean)ec.getMethod("isPoweredOn").invoke(actor)
        &&(Integer)ec.getMethod("getPowerTicks").invoke(actor)>0&&!(Boolean)classes.get("com.projectseele.entity.EvaShutdownR30").getMethod("disabled",ec).invoke(null,actor)
        &&(Float)ec.getMethod("rifleStanceLevel",float.class).invoke(actor,0F)>2.99F&&(Boolean)ec.getMethod("isPilotProne").invoke(actor);}
    private static void probeServer()throws Exception
    {if(eva==null)return;long now=tick(eva);if(!good(eva))serverStable=-1;else if(serverStable<0)serverStable=now;
        var out=Path.of(System.getProperty("projectseele.poseCaptureOutputR52"));json(out.resolve("powered_probe.json"),Map.of("tick",now,"stable_ticks",serverStable<0?0:now-serverStable,"powered",eva.getClass().getMethod("isPoweredOn").invoke(eva),"power_ticks",eva.getClass().getMethod("getPowerTicks").invoke(eva),"shutdown",classes.get("com.projectseele.entity.EvaShutdownR30").getMethod("disabled",classes.get("com.projectseele.entity.EvaUnit01Entity")).invoke(null,eva)));
    }
    private static void installRenderHook()throws Exception
    {
        System.getProperties().put(HOOK,(Consumer<Object[]>)values->{try{renderFinal(values);}catch(Exception error){try{Files.writeString(Path.of(System.getProperty("projectseele.poseCaptureOutputR52")).resolve("render_failure.txt"),error.toString());}catch(Exception ignored){}}});
        var transformer=new java.lang.instrument.ClassFileTransformer(){@Override public byte[] transform(Module module,ClassLoader loader,String name,Class<?> redef,java.security.ProtectionDomain protection,byte[] bytes)
        {if(!name.equals("com/projectseele/client/render/EvaPoseGraph"))return null;var writer=new ClassWriter(ClassWriter.COMPUTE_MAXS);new ClassReader(bytes).accept(new ClassVisitor(Opcodes.ASM9,writer){@Override public MethodVisitor visitMethod(int access,String method,String descriptor,String signature,String[] exceptions)
        {var parent=super.visitMethod(access,method,descriptor,signature,exceptions);if(!method.equals("finish"))return parent;return new MethodVisitor(Opcodes.ASM9,parent){@Override public void visitInsn(int opcode)
        {if(opcode==Opcodes.ARETURN){super.visitMethodInsn(Opcodes.INVOKESTATIC,"java/lang/System","getProperties","()Ljava/util/Properties;",false);super.visitLdcInsn(HOOK);super.visitMethodInsn(Opcodes.INVOKEVIRTUAL,"java/util/Properties","get","(Ljava/lang/Object;)Ljava/lang/Object;",false);super.visitTypeInsn(Opcodes.CHECKCAST,"java/util/function/Consumer");super.visitInsn(Opcodes.ICONST_4);super.visitTypeInsn(Opcodes.ANEWARRAY,"java/lang/Object");
        for(int i=0;i<4;i++){super.visitInsn(Opcodes.DUP);super.visitLdcInsn(i);if(i==2){super.visitVarInsn(Opcodes.FLOAD,2);super.visitMethodInsn(Opcodes.INVOKESTATIC,"java/lang/Float","valueOf","(F)Ljava/lang/Float;",false);}else super.visitVarInsn(Opcodes.ALOAD,i);super.visitInsn(Opcodes.AASTORE);}super.visitMethodInsn(Opcodes.INVOKEINTERFACE,"java/util/function/Consumer","accept","(Ljava/lang/Object;)V",true);}super.visitInsn(opcode);}};}},0);return writer.toByteArray();}};
        instrumentation.addTransformer(transformer,true);instrumentation.retransformClasses(classes.get("com.projectseele.client.render.EvaPoseGraph"));instrumentation.removeTransformer(transformer);
    }
    private static void renderFinal(Object[] values)throws Exception
    {
        var actor=values[0];if(eva==null||!call(actor,new String[]{"getUUID","m_20148_"},new Class<?>[0]).equals(call(eva,new String[]{"getUUID","m_20148_"},new Class<?>[0])))return;
        long now=tick(actor);if(!good(actor)){clientStable=-1;return;}if(clientStable<0)clientStable=now;
        if(!requested||captured||now-clientStable<20||serverStable<0||tick(eva)-serverStable<20)return;
        captured=true;var out=Path.of(System.getProperty("projectseele.poseCaptureOutputR52"));var result=new LinkedHashMap<String,Object>();var ec=classes.get("com.projectseele.entity.EvaUnit01Entity");
        result.put("uuid",call(actor,new String[]{"getUUID","m_20148_"},new Class<?>[0]).toString());result.put("tick",now);result.put("partial",values[2]);result.put("server_stable_ticks",tick(eva)-serverStable);result.put("client_stable_ticks",now-clientStable);result.put("powered",true);result.put("shutdown",false);result.put("power_ticks",ec.getMethod("getPowerTicks").invoke(actor));result.put("stance",ec.getMethod("rifleStanceLevel",float.class).invoke(actor,values[2]));result.put("scope","Actual EvaPoseGraph.finish final writer same frame; ordinary battery and real player; no station/campaign pass");
        Object pose=classes.get("com.projectseele.entity.EvaBodyPose").getMethod("sample",ec,float.class).invoke(null,actor,values[2]);
        @SuppressWarnings("unchecked") Map<String,Object> rig=(Map<String,Object>)pose.getClass().getField("rig").get(pose);var bones=new LinkedHashMap<String,Object>();
        var transforms=classes.get("com.projectseele.client.render.EvaRigTransforms");var geoBone=classes.get("software.bernie.geckolib.cache.object.GeoBone");var modelMethod=transforms.getDeclaredMethod("model",geoBone);modelMethod.setAccessible(true);
        for(var entry:rig.entrySet())
        {Object optional=values[1].getClass().getMethod("getBone",String.class).invoke(values[1],entry.getKey());Object bone=((Optional<?>)optional).orElse(null);if(bone==null)throw new IllegalStateException("Final rendered source bone absent: "+entry.getKey());var matrix=modelMethod.invoke(null,bone);var row=new LinkedHashMap<String,Object>();row.put("matrix",matrix.getClass().getMethod("get",float[].class).invoke(matrix,(Object)new float[16]));row.put("pivot",xyz(entry.getValue().getClass().getMethod("pivot").invoke(entry.getValue())));bones.put(entry.getKey(),row);}
        result.put("bones",bones);json(out.resolve("native_prone_cannon_final_render.json"),result);
        method(server.getClass(),new String[]{"execute","m_18701_"},Runnable.class).invoke(server,(Runnable)()->{try{sample(out);}catch(Exception failure){throw new RuntimeException(failure);}});
    }
    private static void sample(Path out)throws Exception
    {
        if(eva==null||player==null)throw new IllegalStateException("Explicit current fixture actor unavailable");
        if(!captured){requested=true;return;}
        if(!good(eva)||serverStable<0||tick(eva)-serverStable<20)throw new IllegalStateException("Powered production prone stability guard rejected");
        Class<?> ec=classes.get("com.projectseele.entity.EvaUnit01Entity");
        float stance=(Float)ec.getMethod("rifleStanceLevel",float.class).invoke(eva,0F);
        if(stance<2.99||(Integer)ec.getMethod("getWeapon").invoke(eva)!=2||!(Boolean)ec.getMethod("isPilotProne").invoke(eva))throw new IllegalStateException("Native full prone cannon posture not settled: "+stance);
        Object pose=classes.get("com.projectseele.entity.EvaBodyPose").getMethod("sample",ec,float.class).invoke(null,eva,0F);
        Object world=classes.get("com.projectseele.entity.EvaRifleKinematics").getMethod("world",ec,float.class).invoke(null,eva,0F);
        var result=new LinkedHashMap<String,Object>();result.put("scope","Production BodyPose and real hand FK in one existing isolated native client; not R52 station/campaign acceptance");
        result.put("uuid",call(eva,new String[]{"getUUID","m_20148_"},new Class<?>[0]).toString());result.put("stance",stance);result.put("position",xyz(call(eva,new String[]{"position","m_20182_"},new Class<?>[0])));
        result.put("yaw",call(eva,new String[]{"getYRot","m_146908_"},new Class<?>[0]));result.put("weapon",2);result.put("world_matrix",world.getClass().getMethod("get",float[].class).invoke(world,(Object)new float[16]));
        result.put("powered",true);result.put("shutdown",false);result.put("server_stable_ticks",tick(eva)-serverStable);result.put("power_ticks",ec.getMethod("getPowerTicks").invoke(eva));result.put("tick",tick(eva));
        @SuppressWarnings("unchecked") Map<String,Object> rig=(Map<String,Object>)pose.getClass().getField("rig").get(pose);var bones=new LinkedHashMap<String,Object>();
        for(var bone:rig.entrySet())
        {
            var row=new LinkedHashMap<String,Object>();Object matrix=pose.getClass().getMethod("matrix",String.class).invoke(pose,bone.getKey());
            row.put("matrix",matrix.getClass().getMethod("get",float[].class).invoke(matrix,(Object)new float[16]));row.put("pivot",xyz(bone.getValue().getClass().getMethod("pivot").invoke(bone.getValue())));bones.put(bone.getKey(),row);
        }
        result.put("bones",bones);Class<?> motion=classes.get("com.projectseele.entity.EvaGameplayMotionR32");var hand=motion.getMethod("hand",ec,String.class,float.class);
        result.put("left_hand_world",xyz(hand.invoke(null,eva,"l",0F)));result.put("right_hand_world",xyz(hand.invoke(null,eva,"r",0F)));
        Object handPose=classes.get("com.projectseele.entity.EvaAnatomicalHandsR45").getMethod("sample",ec,float.class).invoke(null,eva,0F);
        @SuppressWarnings("unchecked") Map<String,Object> joints=(Map<String,Object>)handPose.getClass().getMethod("rotations").invoke(handPose);var fingerRotations=new LinkedHashMap<String,Object>();
        for(var joint:joints.entrySet()){var q=joint.getValue();fingerRotations.put(joint.getKey(),new float[]{q.getClass().getField("x").getFloat(q),q.getClass().getField("y").getFloat(q),q.getClass().getField("z").getFloat(q),q.getClass().getField("w").getFloat(q)});}result.put("actual_finger_quaternions",fingerRotations);
        float pilotPitch=(Float)call(player,new String[]{"getXRot","m_146909_"},new Class<?>[0]),pilotYaw=(Float)call(player,new String[]{"getYRot","m_146908_"},new Class<?>[0]);
        float pitch=(Float)ec.getMethod("clampPilotWeaponPitch",float.class,float.class).invoke(eva,pilotPitch,0F),yaw=(Float)ec.getMethod("clampPilotWeaponYaw",float.class,float.class).invoke(eva,pilotYaw,0F);
        double p=Math.toRadians(pitch),y=Math.toRadians(yaw);Object direction=classes.get("net.minecraft.world.phys.Vec3").getConstructor(double.class,double.class,double.class).newInstance(-Math.sin(y)*Math.cos(p),-Math.sin(p),Math.cos(y)*Math.cos(p));
        Object cannon=classes.get("com.projectseele.entity.EvaCannonFrameR45").getMethod("sample",ec,float.class,classes.get("net.minecraft.world.phys.Vec3")).invoke(null,eva,0F,direction);
        Object gunMatrix=cannon.getClass().getMethod("weaponToWorld").invoke(cannon);result.put("production_held_gun_matrix",gunMatrix.getClass().getMethod("get",float[].class).invoke(gunMatrix,(Object)new float[16]));result.put("actual_aim_pitch",pitch);result.put("actual_aim_yaw",yaw);
        json(out.resolve("native_prone_cannon.json"),result);
    }
    private static void cleanup()throws Exception
    {if(monitor!=null)monitor.shutdownNow();System.getProperties().put(HOOK,(Consumer<Object[]>)values->{});if(player!=null){call(player,new String[]{"stopRiding","m_8127_"},new Class<?>[0]);if(before!=null)call(player,new String[]{"teleportTo","m_6021_"},new Class<?>[]{double.class,double.class,double.class},before[0],before[1],before[2]);if(mode!=null)method(player.getClass(),new String[]{"setGameMode","m_143403_"},classes.get("net.minecraft.world.level.GameType")).invoke(player,mode);}if(eva!=null){call(eva,new String[]{"discard","m_146870_"},new Class<?>[0]);eva=null;}}
}

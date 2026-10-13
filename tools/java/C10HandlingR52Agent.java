import java.lang.instrument.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.Consumer;
import org.objectweb.asm.*;

/** Opt-in actual native input/capture in one existing flat QA save. No production class replacement. */
public final class C10HandlingR52Agent {
    private static final String PREFIX="seele.ordinary.motion.r52.c10.";
    private static final boolean AFTER_FIRST_BATTLE=Boolean.getBoolean("projectseele.firstBattleThenOrdinaryR52");
    private static final boolean HANDLING_ONLY=Boolean.getBoolean("projectseele.ordinaryHandlingOnlyR52");
    private static final Map<String,Class<?>> CLASSES=new ConcurrentHashMap<>();
    private static Object mc,server,level,player,camera,options,active;
    private static final Object[] actors=new Object[3];
    private static final int[] variants={0,1,2},lengths={540,HANDLING_ONLY?210:1040,740};
    private static final Map<String,Object> keys=new HashMap<>();
    private static volatile boolean ready,done,failed,switching;
    private static int segment=-1,age,previous=-1,lastPoseAge=-1,lastWrittenSegment=-1,lastWrittenAge=-1,frame,dropped;
    private static long start,lastCapture,lastWrittenWallNanos=Long.MIN_VALUE; private static Path out; private static Object gson;
    private static Path checkedWorld;private static volatile boolean reviewHandedOff;private static int completedReviewHeroId=-1;
    private static Map<String,Object> pending;
    private static String cameraView="whole_body";
    private static final ExecutorService WRITER=Executors.newSingleThreadExecutor(r->{var t=new Thread(r,"ordinary-r52-image-writer");t.setDaemon(true);return t;});
    private static final Semaphore IMAGE_SLOTS=new Semaphore(3);
    private static java.io.BufferedWriter poses,inputs,frames,firstBattleDraws;
    private static long firstBattleDrawFrame=Long.MIN_VALUE;
    private static int firstBattleDrawCount;
    private static boolean rawBeginDrawRecorded,rawBerserkDrawRecorded;

    private static Class<?> c(String name)throws Exception {Class<?> found=CLASSES.get(name);if(found==null){found=Class.forName(name,true,CLASSES.get("com.projectseele.entity.EvaUnit01Entity").getClassLoader());CLASSES.put(name,found);}return found;}
    private static Method m(Class<?> type,String[] names,Class<?>... parameters)throws Exception {for(String name:names)try{return type.getMethod(name,parameters);}catch(NoSuchMethodException ignored){}throw new NoSuchMethodException(type+" "+Arrays.toString(names));}
    private static Object call(Object target,String[] names,Class<?>[] parameters,Object... args)throws Exception{return m(target.getClass(),names,parameters).invoke(target,args);}
    private static Object call(Object target,String name)throws Exception{return call(target,new String[]{name},new Class<?>[0]);}
    private static Object field(Object object,String... names)throws Exception {for(String name:names)try{return object.getClass().getField(name).get(object);}catch(NoSuchFieldException ignored){}throw new NoSuchFieldException(Arrays.toString(names));}
    private static void assign(Object object,Object value,String... names)throws Exception {for(String name:names)try{object.getClass().getField(name).set(object,value);return;}catch(NoSuchFieldException ignored){}throw new NoSuchFieldException(Arrays.toString(names));}
    private static Method returns(Class<?> type,String result,int argc)throws Exception {for(var method:type.getMethods())if(method.getParameterCount()==argc&&method.getReturnType().getName().equals(result))return method;throw new NoSuchMethodException(type+" returns "+result);}
    private static void execute(Object target,Runnable action)throws Exception {call(target,new String[]{"execute","m_18701_"},new Class<?>[]{Runnable.class},action);}
    private static long tick()throws Exception{return (Long)call(level,new String[]{"getGameTime","m_46467_"},new Class<?>[0]);}
    private static String json(Object object)throws Exception{return (String)gson.getClass().getMethod("toJson",Object.class).invoke(gson,object);}
    private static synchronized void append(java.io.BufferedWriter writer,Object value)throws Exception {writer.write(json(value));writer.newLine();writer.flush();}
    private static void write(String name,Object value)throws Exception {Files.writeString(out.resolve(name),json(value));}
    private static double[] xyz(Object object)throws Exception {if(object.getClass().getName().equals("org.joml.Vector3f"))return new double[]{object.getClass().getField("x").getFloat(object),object.getClass().getField("y").getFloat(object),object.getClass().getField("z").getFloat(object)};return new double[]{((Number)call(object,new String[]{"x","m_7096_"},new Class<?>[0])).doubleValue(),((Number)call(object,new String[]{"y","m_7098_"},new Class<?>[0])).doubleValue(),((Number)call(object,new String[]{"z","m_7094_"},new Class<?>[0])).doubleValue()};}
    private static double[] position(Object actor)throws Exception {return xyz(call(actor,new String[]{"position","m_20182_"},new Class<?>[0]));}
    private static void data(Object actor,String name,Object value)throws Exception {var f=c("com.projectseele.entity.EvaUnit01Entity").getDeclaredField(name);f.setAccessible(true);var d=call(actor,new String[]{"getEntityData","m_20088_"},new Class<?>[0]);call(d,new String[]{"set","m_135381_"},new Class<?>[]{c("net.minecraft.network.syncher.EntityDataAccessor"),Object.class},f.get(null),value);}
    private static Object data(Object actor,String name)throws Exception {var f=c("com.projectseele.entity.EvaUnit01Entity").getDeclaredField(name);f.setAccessible(true);var d=call(actor,new String[]{"getEntityData","m_20088_"},new Class<?>[0]);return call(d,new String[]{"get","m_135370_"},new Class<?>[]{c("net.minecraft.network.syncher.EntityDataAccessor")},f.get(null));}
    private static Object localPlayer()throws Exception{return field(mc,"player","f_91074_");}
    private static Object clientActor()throws Exception {var lp=localPlayer();if(lp==null)return null;var resolver=c("com.projectseele.world.EvaPilotResolver");return resolver.getMethod("controlTarget",c("net.minecraft.world.entity.Entity")).invoke(null,lp);}
    private static void fail(Throwable problem) {if(failed)return;failed=true;try{write("FAILURE.json",Map.of("error",problem.toString(),"segment",segment,"age",age,"native_acceptance",false));}catch(Exception ignored){}System.err.println("R52 ORDINARY QA FAILURE "+problem);problem.printStackTrace();}
    public static void agentmain(String argument,Instrumentation instrumentation)throws Exception {
        String mode=System.getProperty("projectseele.regionalBuild");
        if(!HANDLING_ONLY||AFTER_FIRST_BATTLE||!Boolean.getBoolean("projectseele.ordinaryHandlingC10R52"))throw new IllegalStateException("Explicit standalone C10 handling only");
        boolean firstThenHandling=Boolean.getBoolean("projectseele.firstBattleThenHandlingR52");
        if(HANDLING_ONLY&&AFTER_FIRST_BATTLE&&!firstThenHandling)throw new IllegalStateException("Combined handling QA requires explicit firstBattleThenHandlingR52");
        if(firstThenHandling&&(!HANDLING_ONLY||!AFTER_FIRST_BATTLE||!"r10-firstbattle".equals(mode)))throw new IllegalStateException("Incomplete explicit first-battle/handling QA mode");
        if(!"ordinary-motion-r52".equals(mode)&&!(AFTER_FIRST_BATTLE&&"r10-firstbattle".equals(mode)))throw new IllegalStateException("Wrong explicit QA JVM");
        if(!"start".equals(argument))throw new IllegalArgumentException(argument);
        if(ready||poses!=null)throw new IllegalStateException("Already attempted; retain evidence");
        for(var type:instrumentation.getAllLoadedClasses())CLASSES.put(type.getName(),type);
        mc=returns(c("net.minecraft.client.Minecraft"),"net.minecraft.client.Minecraft",0).invoke(null);
        server=returns(mc.getClass(),"net.minecraft.client.server.IntegratedServer",0).invoke(mc);
        if(server==null)throw new IllegalStateException("Integrated fixture not ready");
        var resource=c("net.minecraft.world.level.storage.LevelResource");Object root=null;
        for(var f:resource.getFields())if(f.getType()==resource){Object value=f.get(null);for(var method:resource.getMethods())if(method.getParameterCount()==0&&method.getReturnType()==String.class&&".".equals(method.invoke(value)))root=value;}
        if(root==null)throw new IllegalStateException("Native root resource unavailable");
        Path world=(Path)returns(server.getClass(),"java.nio.file.Path",1).invoke(server,root);
        Path allowed=Path.of(System.getProperty("projectseele.ordinaryMotionWorldR52")).toAbsolutePath().normalize();
        if(!allowed.equals(world.toAbsolutePath().normalize())||!allowed.getFileName().toString().equals("SEELE_FIRST_BATTLE_REVIEW_R10"))throw new IllegalStateException("Nonfixture world refused: "+world);
        checkedWorld=world.toAbsolutePath().normalize();
        out=Path.of(System.getProperty("projectseele.ordinaryMotionOutputR52")).toAbsolutePath().normalize();Files.createDirectories(out.resolve("frames"));
        gson=c("com.google.gson.Gson").getConstructor().newInstance();
        poses=Files.newBufferedWriter(out.resolve("poses.jsonl"),StandardOpenOption.CREATE_NEW);
        inputs=Files.newBufferedWriter(out.resolve("inputs.jsonl"),StandardOpenOption.CREATE_NEW);
        frames=Files.newBufferedWriter(out.resolve("frames.jsonl"),StandardOpenOption.CREATE_NEW);
        write("ATTACHED.json",Map.of("world",world.toString(),"native_only",true,"production_code_changed",false,"sequence_lengths_ticks",HANDLING_ONLY?new int[]{210}:lengths,"ordinary_variants",HANDLING_ONLY?new int[]{1}:variants));
        System.getProperties().put(PREFIX+"tick",(Consumer<Object[]>)values->{try{clientTick();}catch(Throwable error){fail(error);}});
        System.getProperties().put(PREFIX+"pose",(Consumer<Object[]>)values->{try{finalPose(values);}catch(Throwable error){fail(error);}});
        System.getProperties().put(PREFIX+"render",(Consumer<Object[]>)values->{try{renderEnd();}catch(Throwable error){fail(error);}});
        if(AFTER_FIRST_BATTLE)System.getProperties().put(PREFIX+"reviewComplete",(Consumer<Object[]>)values->{try{firstBattleComplete();}catch(Throwable error){fail(error);try{call(mc,new String[]{"stop","m_91395_"},new Class<?>[0]);}catch(Exception ignored){}}});
        install(instrumentation);
        if(!AFTER_FIRST_BATTLE)execute(server,()->{try{setup();}catch(Throwable error){fail(error);}});
    }
    /** The existing native R10 movie owns the fresh begin/age1 capture first.
     * Replace only its final QA exit with a verified handoff to real input QA. */
    private static void firstBattleComplete()throws Exception {
        if(reviewHandedOff)return;
        var review=c("com.projectseele.visual.FirstBattleR10Review");
        if(!review.getField("finished").getBoolean(null)){call(mc,new String[]{"stop","m_91395_"},new Class<?>[0]);return;}
        String evidence=Files.readString(checkedWorld.resolve("r10_first_battle_review.json"));
        @SuppressWarnings("unchecked") Map<String,Object> result=(Map<String,Object>)gson.getClass().getMethod("fromJson",String.class,Class.class).invoke(gson,evidence,Map.class);
        if(!Boolean.TRUE.equals(result.get("passed")))throw new IllegalStateException("Native first-battle review did not pass; ordinary handoff refused");
        String declared=System.getProperty("projectseele.firstBattleReviewClip","");
        if(declared.isBlank()||!HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(Path.of(declared)))).equals(result.get("clip_sha256")))throw new IllegalStateException("Completed native clip fingerprint differs from the declared immutable review clip");
        completedReviewHeroId=review.getField("heroId").getInt(null);reviewHandedOff=true;
        Files.writeString(out.resolve("FIRST_BATTLE_COMPLETED_BEFORE_ORDINARY.json"),evidence,StandardOpenOption.CREATE_NEW);
        if(firstBattleDraws!=null){firstBattleDraws.close();firstBattleDraws=null;write("RAW_FIRST_BATTLE_DRAW_CAPTURE_COMPLETE.json",Map.of("actual_main_draw_rows",firstBattleDrawCount,"raw_begin_draw_recorded",rawBeginDrawRecorded,"first_actual_berserk_draw_recorded",rawBerserkDrawRecorded,"pixel_eye_visibility_verified",false));}
        append(inputs,Map.of("kind","first_battle_completed_before_ordinary","hero_id",completedReviewHeroId,"clip_sha256",result.get("clip_sha256"),"raw_first_battle_was_not_replaced_by_ordinary_warmup",true));
        execute(server,()->{try{setup();}catch(Throwable error){fail(error);}});
    }
    private static void install(Instrumentation instrumentation)throws Exception {
        var transformer=new ClassFileTransformer(){@Override public byte[] transform(Module module,ClassLoader loader,String name,Class<?> redef,java.security.ProtectionDomain domain,byte[] bytes){
            if(!Set.of("net/minecraft/client/Minecraft","net/minecraft/client/renderer/GameRenderer","com/projectseele/client/render/EvaPoseGraph").contains(name)&&!(AFTER_FIRST_BATTLE&&name.equals("com/projectseele/client/visual/FirstBattleR10Client")))return null;
            var writer=new ClassWriter(ClassWriter.COMPUTE_MAXS);new ClassReader(bytes).accept(new ClassVisitor(Opcodes.ASM9,writer){@Override public MethodVisitor visitMethod(int access,String method,String descriptor,String signature,String[] exceptions){
                var parent=super.visitMethod(access,method,descriptor,signature,exceptions);String hook=null;int count=0;
                if(AFTER_FIRST_BATTLE&&name.equals("com/projectseele/client/visual/FirstBattleR10Client"))return new MethodVisitor(Opcodes.ASM9,parent){@Override public void visitMethodInsn(int opcode,String owner,String target,String desc,boolean face){
                    if(opcode==Opcodes.INVOKEVIRTUAL&&owner.equals("net/minecraft/client/Minecraft")&&Set.of("stop","m_91395_").contains(target)&&desc.equals("()V")){
                        super.visitInsn(Opcodes.POP);super.visitMethodInsn(Opcodes.INVOKESTATIC,"java/lang/System","getProperties","()Ljava/util/Properties;",false);super.visitLdcInsn(PREFIX+"reviewComplete");super.visitMethodInsn(Opcodes.INVOKEVIRTUAL,"java/util/Properties","get","(Ljava/lang/Object;)Ljava/lang/Object;",false);super.visitTypeInsn(Opcodes.CHECKCAST,"java/util/function/Consumer");super.visitInsn(Opcodes.ICONST_0);super.visitTypeInsn(Opcodes.ANEWARRAY,"java/lang/Object");super.visitMethodInsn(Opcodes.INVOKEINTERFACE,"java/util/function/Consumer","accept","(Ljava/lang/Object;)V",true);
                    }else super.visitMethodInsn(opcode,owner,target,desc,face);
                }};
                if(name.equals("net/minecraft/client/Minecraft")&&Set.of("tick","m_91398_").contains(method)&&descriptor.equals("()V"))hook="tick";
                if(name.equals("net/minecraft/client/renderer/GameRenderer")&&Set.of("render","m_109093_").contains(method)&&descriptor.equals("(FJZ)V"))hook="render";
                if(name.equals("com/projectseele/client/render/EvaPoseGraph")&&method.equals("finish")){hook="pose";count=4;}
                if(hook==null)return parent;final String selected=hook;final int arguments=count;
                return new MethodVisitor(Opcodes.ASM9,parent){@Override public void visitInsn(int opcode){if(opcode==Opcodes.RETURN||opcode==Opcodes.ARETURN){
                    super.visitMethodInsn(Opcodes.INVOKESTATIC,"java/lang/System","getProperties","()Ljava/util/Properties;",false);super.visitLdcInsn(PREFIX+selected);super.visitMethodInsn(Opcodes.INVOKEVIRTUAL,"java/util/Properties","get","(Ljava/lang/Object;)Ljava/lang/Object;",false);super.visitTypeInsn(Opcodes.CHECKCAST,"java/util/function/Consumer");super.visitLdcInsn(arguments);super.visitTypeInsn(Opcodes.ANEWARRAY,"java/lang/Object");
                    for(int index=0;index<arguments;index++){super.visitInsn(Opcodes.DUP);super.visitLdcInsn(index);if(index==2){super.visitVarInsn(Opcodes.FLOAD,index);super.visitMethodInsn(Opcodes.INVOKESTATIC,"java/lang/Float","valueOf","(F)Ljava/lang/Float;",false);}else super.visitVarInsn(Opcodes.ALOAD,index);super.visitInsn(Opcodes.AASTORE);}super.visitMethodInsn(Opcodes.INVOKEINTERFACE,"java/util/function/Consumer","accept","(Ljava/lang/Object;)V",true);
                }super.visitInsn(opcode);}};
            }},0);return writer.toByteArray();}};
        instrumentation.addTransformer(transformer,true);
        var targets=new ArrayList<Class<?>>(List.of(c("net.minecraft.client.Minecraft"),c("net.minecraft.client.renderer.GameRenderer"),c("com.projectseele.client.render.EvaPoseGraph")));
        if(AFTER_FIRST_BATTLE)targets.add(c("com.projectseele.client.visual.FirstBattleR10Client"));
        instrumentation.retransformClasses(targets.toArray(Class<?>[]::new));instrumentation.removeTransformer(transformer);
    }
    private static void setup()throws Exception {
        level=returns(server.getClass(),"net.minecraft.server.level.ServerLevel",0).invoke(server);
        var list=returns(server.getClass(),"net.minecraft.server.players.PlayerList",0).invoke(server);
        @SuppressWarnings("unchecked") var players=(List<Object>)call(list,new String[]{"getPlayers","m_11314_"},new Class<?>[0]);if(players.size()!=1)throw new IllegalStateException("One native player required");player=players.get(0);
        call(player,new String[]{"setGameMode","m_143403_"},new Class<?>[]{c("net.minecraft.world.level.GameType")},Enum.valueOf((Class)c("net.minecraft.world.level.GameType"),"SURVIVAL"));
        exportNativeShapes();
        call(player,new String[]{"stopRiding","m_8127_"},new Class<?>[0]);
        var previousActors=new ArrayList<Object>();
        for(Object actor:(Iterable<?>)call(level,new String[]{"getAllEntities","m_8583_"},new Class<?>[0]))
            if(((Set<?>)call(actor,new String[]{"getTags","m_19880_"},new Class<?>[0])).contains("seele_ordinary_motion_r52")
                    ||(reviewHandedOff&&c("com.projectseele.entity.EvaUnit01Entity").isInstance(actor)&&((Number)call(actor,new String[]{"getId","m_19879_"},new Class<?>[0])).intValue()==completedReviewHeroId))previousActors.add(actor);
        for(Object actor:previousActors)call(actor,new String[]{"discard","m_146870_"},new Class<?>[0]);
        append(inputs,Map.of("kind","discard_previous_explicit_tool_actors","count",previousActors.size(),"completed_lab_review_hero_only",reviewHandedOff,"production_actors_touched",false));
        for(int index=0;index<3;index++){
            if(HANDLING_ONLY&&index!=1)continue;
            Object registry=c("com.projectseele.registry.ModEntities").getField("EVA_UNIT0"+variants[index]).get(null);Object type=call(registry,"get");
            Object actor=call(type,new String[]{"create","m_20615_"},new Class<?>[]{c("net.minecraft.world.level.Level")},level);actors[index]=actor;
            call(actor,"prepareForMotionLab");data(actor,"DATA_MOTION_LAB_ACTIVE",false);data(actor,"DATA_POWER_TICKS",call(actor,"getPowerCapacityTicks"));
            data(actor,"DATA_ARMAMENT_MASK",index==1?(1<<0)|(1<<1)|(1<<4):index==2?(1<<0)|(1<<6):1);
            if(index==2&&!((Boolean)call(actor,new String[]{"selectMotionLabWeapon"},new Class<?>[]{int.class},6)))throw new IllegalStateException("Original sword resources unavailable");
            call(actor,new String[]{"addTag","m_20049_"},new Class<?>[]{String.class},"seele_ordinary_motion_r52");call(actor,new String[]{"setNoAi","m_21557_"},new Class<?>[]{boolean.class},true);call(actor,new String[]{"setNoGravity","m_20242_"},new Class<?>[]{boolean.class},false);
            call(actor,new String[]{"moveTo","m_7678_"},new Class<?>[]{double.class,double.class,double.class,float.class,float.class},(index-1)*80D,-60D,-20D,0F,0F);
            call(actor,new String[]{"setOnGround","m_6853_"},new Class<?>[]{boolean.class},true);
            if(!((Boolean)call(level,new String[]{"addFreshEntity","m_7967_"},new Class<?>[]{c("net.minecraft.world.entity.Entity")},actor)))throw new IllegalStateException("Actor admission failed");
        }
        switchActor(HANDLING_ONLY?1:0);ready=true;
    }
    @SuppressWarnings("unchecked")
    private static void exportNativeShapes()throws Exception {
        String input=System.getProperty("projectseele.nativeCollisionStatesR52","");if(input.isBlank())return;
        Path statesPath=Path.of(input).toAbsolutePath().normalize();
        byte[] bytes=Files.readAllBytes(statesPath);
        var states=(List<String>)gson.getClass().getMethod("fromJson",String.class,Class.class).invoke(gson,new String(bytes,java.nio.charset.StandardCharsets.UTF_8),List.class);
        var keys=new TreeSet<String>(states);if(keys.size()!=states.size()||keys.isEmpty())throw new IllegalArgumentException("Native shape inputs must be unique real state keys");
        var parse=c("com.projectseele.visual.RegionalSpatialAuditDriver").getDeclaredMethod("parse",String.class);parse.setAccessible(true);
        Object getter=((Object[])c("net.minecraft.world.level.EmptyBlockGetter").getMethod("values").invoke(null))[0];
        Object zero=c("net.minecraft.core.BlockPos").getConstructor(int.class,int.class,int.class).newInstance(0,0,0);
        Object context=m(c("net.minecraft.world.phys.shapes.CollisionContext"),new String[]{"of","m_82750_"},c("net.minecraft.world.entity.Entity")).invoke(null,player);
        var shapes=new LinkedHashMap<String,Object>();
        for(String key:keys){
            Object state=parse.invoke(null,key);
            Object shape=call(state,new String[]{"getCollisionShape","m_60742_"},new Class<?>[]{c("net.minecraft.world.level.BlockGetter"),c("net.minecraft.core.BlockPos"),c("net.minecraft.world.phys.shapes.CollisionContext")},getter,zero,context);
            var boxes=new ArrayList<double[]>();
            for(Object box:(List<?>)call(shape,new String[]{"toAabbs","m_83299_"},new Class<?>[0]))boxes.add(new double[]{
                    ((Number)field(box,"minX","f_82288_")).doubleValue(),((Number)field(box,"minY","f_82289_")).doubleValue(),((Number)field(box,"minZ","f_82290_")).doubleValue(),
                    ((Number)field(box,"maxX","f_82291_")).doubleValue(),((Number)field(box,"maxY","f_82292_")).doubleValue(),((Number)field(box,"maxZ","f_82293_")).doubleValue()});
            shapes.put(key,boxes);
        }
        Files.writeString(out.resolve("native_collision_shapes_r52.json"),json(shapes),StandardOpenOption.CREATE_NEW);
        write("NATIVE_COLLISION_EXPORT_RECEIPT.json",Map.of("server_tick",tick(),"input",statesPath.toString(),"input_sha256",HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes)),"state_count",shapes.size(),"world_written",false,"old_box_values_copied",false,"driver_enabled",false,"actual_native_collision_shapes",true));
    }
    private static void switchActor(int next)throws Exception {
        segment=next;active=actors[next];call(player,new String[]{"stopRiding","m_8127_"},new Class<?>[0]);
        if(!((Boolean)call(active,new String[]{"boardFromExternalPlug"},new Class<?>[]{c("net.minecraft.world.entity.Entity"),int.class},player,100)))throw new IllegalStateException("Real boarding rejected");
        start=tick()+35;age=-35;previous=-1;lastPoseAge=-1;pending=null;switching=false;
        append(inputs,Map.of("kind","native_boarding","variant",variants[next],"server_tick",tick(),"uuid",call(active,new String[]{"getUUID","m_20148_"},new Class<?>[0]).toString(),"ordinary_battery",true,"motionlab_bypass",false));
    }
    private static boolean at(int target){return previous<target&&age>=target;}
    private static void key(String name,boolean down)throws Exception {Object key=keys.get(name);if(key==null)throw new IllegalStateException("Missing native key "+name);call(key,new String[]{"setDown","m_7249_"},new Class<?>[]{boolean.class},down);}
    private static void packet(int action,String purpose)throws Exception {
        var packet=c("com.projectseele.network.ServerboundEvaControlPacket").getConstructor(int.class).newInstance(action);Object channel=c("com.projectseele.network.SeeleNetwork").getField("CHANNEL").get(null);channel.getClass().getMethod("sendToServer",Object.class).invoke(channel,packet);
        append(inputs,Map.of("kind","actual_client_packet","variant",variants[segment],"age",age,"server_tick",tick(),"action",action,"purpose",purpose));
    }
    private static void clientTick()throws Exception {
        if(!ready||done||failed||switching)return;if(localPlayer()==null)return;
        options=field(mc,"options","f_91066_");if(keys.isEmpty())for(var f:options.getClass().getFields())if(f.getType().getName().equals("net.minecraft.client.KeyMapping")){var value=f.get(options);if(value!=null)keys.put((String)call(value,new String[]{"getName","m_90860_"},new Class<?>[0]),value);}
        for(String name:new String[]{"pauseOnLostFocus","f_92126_"})try{options.getClass().getField(name).setBoolean(options,false);break;}catch(NoSuchFieldException ignored){}
        Object client=clientActor();if(client==null)return;
        if(!call(client,new String[]{"getUUID","m_20148_"},new Class<?>[0]).equals(call(active,new String[]{"getUUID","m_20148_"},new Class<?>[0])))return;
        age=(int)(tick()-start);boolean move=age>=30&&age<150||age>=185&&age<235;boolean run=age>=75&&age<120;
        if(segment==0)move|=age>=420&&age<450;
        if(segment==1)move|=age>=790&&age<835||age>=910&&age<935;
        if(segment==2)move|=age>=560&&age<590;
        if(HANDLING_ONLY){move=age>=15&&age<30;run=false;}
        key("key.forward",move);key("key.back",false);key("key.left",false);key("key.right",false);key("key.sprint",run);key("key.jump",false);key("key.sneak",false);
        if(!HANDLING_ONLY){if(at(75))packet(8,"walk_to_run");if(at(120))packet(9,"run_to_walk");}
        var lp=localPlayer();var input=field(lp,"input","f_108618_");
        // The detached camera suppresses vanilla player movement updates.
        assign(input,move,"up","f_108568_");assign(input,false,"down","f_108569_");
        assign(input,move?1F:0F,"forwardImpulse","f_108567_");assign(input,0F,"leftImpulse","f_108566_");
        assign(lp,move?1F:0F,"zza","f_20902_");assign(lp,0F,"xxa","f_20900_");
        // Send the ordinary vanilla mounted-player input packet as well, so
        // the server receives the same fields independently of camera policy.
        Object movement=c("net.minecraft.network.protocol.game.ServerboundPlayerInputPacket")
                .getConstructor(float.class,float.class,boolean.class,boolean.class).newInstance(0F,move?1F:0F,false,false);
        call(field(lp,"connection","f_108617_"),new String[]{"send","m_104955_"},
                new Class<?>[]{c("net.minecraft.network.protocol.Packet")},movement);
        if(age!=previous)append(inputs,Map.of("kind","actual_vanilla_player_input_packet","variant",variants[segment],"age",age,
                "server_tick",tick(),"forward",move?1F:0F,"sideways",0F,"jump",false,"crouch",false));
        call(lp,new String[]{"setYRot","m_146922_"},new Class<?>[]{float.class},!HANDLING_ONLY&&age>=185&&age<235?35F:0F);call(lp,new String[]{"setXRot","m_146926_"},new Class<?>[]{float.class},0F);
        if(segment==0){if(at(260))packet(6,"crouch_entry");if(at(330))packet(7,"crouch_exit");if(at(350))packet(13,"ordinary_unarmed_prone_entry");if(at(480))packet(13,"ordinary_unarmed_prone_exit");}
        if(HANDLING_ONLY){if(at(60))packet(0,"C10_targeted_normal_knife_draw");if(at(120))packet(0,"C10_targeted_normal_knife_stow_to_rifle");}
        if(segment==1&&!HANDLING_ONLY){
            if(at(250))packet(0,"normal_knife_draw");if(at(330))packet(2,"knife_forward");if(at(405))packet(5,"knife_reverse");
            if(at(480))packet(2,"knife_first_tick_cancel_source");if(at(481))packet(6,"knife_cancel_by_normal_stance");if(at(482))packet(7,"knife_cancel_stance_release");if(at(483))packet(2,"knife_immediate_reinput");
            if(at(560))packet(2,"knife_forward_after_cancel");if(at(650))packet(5,"knife_reverse_after_cancel");if(at(730))packet(0,"normal_knife_stow_to_rifle");
            if(at(850))packet(13,"ordinary_rifle_prone_entry");if(at(960))packet(13,"ordinary_rifle_prone_exit");
        }
        if(segment==2){if(at(260))packet(2,"02_sword_light_strike");if(at(365))packet(5,"02_sword_heavy_strike");if(at(490))packet(13,"ordinary_sword_prone_entry");if(at(640))packet(13,"ordinary_sword_prone_exit");}
        positionCamera(client);
        if(age!=previous)append(inputs,Map.of("kind","actual_client_key_state","variant",variants[segment],"age",age,"server_tick",tick(),"W",move,"sprint",run,"yaw",!HANDLING_ONLY&&age>=185&&age<235?35:0));
        previous=age;
        if(age>=lengths[segment]){key("key.forward",false);key("key.sprint",false);switching=true;if(segment<2&&!HANDLING_ONLY)execute(server,()->{try{switchActor(segment+1);}catch(Throwable error){fail(error);}});else finish();}
    }
    private static void positionCamera(Object actor)throws Exception {
        if(camera==null){Object type=null;for(var f:c("net.minecraft.world.entity.EntityType").getFields())if(Modifier.isStatic(f.getModifiers())&&f.getType()==c("net.minecraft.world.entity.EntityType")){Object value=f.get(null);if(value!=null&&value.toString().contains("armor_stand")){type=value;break;}}if(type==null)throw new IllegalStateException("Original armor stand camera type missing");Object clientLevel=field(mc,"level","f_91073_");camera=call(type,new String[]{"create","m_20615_"},new Class<?>[]{c("net.minecraft.world.level.Level")},clientLevel);call(camera,new String[]{"setInvisible","m_6842_"},new Class<?>[]{boolean.class},true);}
        var p=position(actor);double stance=((Number)call(actor,new String[]{"rifleStanceLevel"},new Class<?>[]{float.class},1F)).doubleValue()/3;
        double cx=p[0]+(segment==0?-66:66),cy=p[1]+33-18*stance,cz=p[2]+48,tx=p[0],ty=p[1]+28-19*stance,tz=p[2]+8*stance;
        cameraView="whole_body";
        boolean rear=segment==0&&age>=395&&age<418||segment==1&&age>=888&&age<907||segment==2&&age>=530&&age<552;
        boolean ankle=segment==0&&age>=455&&age<476||segment==1&&age>=940&&age<958||segment==2&&age>=610&&age<635;
        if(stance>.85&&pending!=null&&pending.get("actual_world_bone_pivots") instanceof Map<?,?> pivots){
            if(rear&&pivots.get("head") instanceof double[] focus){tx=focus[0];ty=focus[1];tz=focus[2];cx=tx+21;cy=ty+9;cz=tz-23;cameraView="prone_rear_head";}
            if(ankle&&pivots.get("foot_l") instanceof double[] left&&pivots.get("foot_r") instanceof double[] right){
                tx=(left[0]+right[0])*.5;ty=(left[1]+right[1])*.5;tz=(left[2]+right[2])*.5;
                cx=tx+17;cy=ty+10;cz=tz-22;cameraView="prone_ankles";
            }
        }
        float yaw=(float)Math.toDegrees(Math.atan2(tz-cz,tx-cx))-90F,pitch=(float)-Math.toDegrees(Math.atan2(ty-cy,Math.hypot(tx-cx,tz-cz)));
        float height=((Number)call(camera,new String[]{"getEyeHeight","m_20192_"},new Class<?>[0])).floatValue();call(camera,new String[]{"moveTo","m_7678_"},new Class<?>[]{double.class,double.class,double.class,float.class,float.class},cx,cy-height,cz,yaw,pitch);
        call(camera,new String[]{"setYHeadRot","m_5616_"},new Class<?>[]{float.class},yaw);
        for(String name:new String[]{"yHeadRotO","f_20886_"})try{camera.getClass().getField(name).setFloat(camera,yaw);break;}catch(NoSuchFieldException ignored){}
        for(String[] aliases:List.of(new String[]{"xo","f_19854_"},new String[]{"xOld","f_19790_"}))for(String name:aliases)try{camera.getClass().getField(name).setDouble(camera,cx);break;}catch(NoSuchFieldException ignored){}
        for(String[] aliases:List.of(new String[]{"yo","f_19855_"},new String[]{"yOld","f_19791_"}))for(String name:aliases)try{camera.getClass().getField(name).setDouble(camera,cy-height);break;}catch(NoSuchFieldException ignored){}
        for(String[] aliases:List.of(new String[]{"zo","f_19856_"},new String[]{"zOld","f_19792_"}))for(String name:aliases)try{camera.getClass().getField(name).setDouble(camera,cz);break;}catch(NoSuchFieldException ignored){}
        for(String name:new String[]{"yRotO","f_19859_"})try{camera.getClass().getField(name).setFloat(camera,yaw);break;}catch(NoSuchFieldException ignored){}
        for(String name:new String[]{"xRotO","f_19860_"})try{camera.getClass().getField(name).setFloat(camera,pitch);break;}catch(NoSuchFieldException ignored){}
        for(String name:new String[]{"hideGui","f_92062_"})try{options.getClass().getField(name).setBoolean(options,true);break;}catch(NoSuchFieldException ignored){}
        call(options,new String[]{"setCameraType","m_92157_"},new Class<?>[]{c("net.minecraft.client.CameraType")},Enum.valueOf((Class)c("net.minecraft.client.CameraType"),"FIRST_PERSON"));call(mc,new String[]{"setCameraEntity","m_91118_"},new Class<?>[]{c("net.minecraft.world.entity.Entity")},camera);
    }
    private static void firstBattleRawDraw(Object[] values)throws Exception {
        if(!AFTER_FIRST_BATTLE||ready||done||failed)return;
        var actor=values[0];var ec=c("com.projectseele.entity.EvaUnit01Entity");if(!ec.isInstance(actor)||!(Boolean)call(actor,"isFirstBattleActive"))return;
        int hero=c("com.projectseele.visual.FirstBattleR10Review").getField("heroId").getInt(null);
        if(((Number)call(actor,new String[]{"getId","m_19879_"},new Class<?>[0])).intValue()!=hero)return;
        if((Boolean)c("com.projectseele.client.render.ShaderShadowPassR44").getMethod("active").invoke(null))return;
        if((Boolean)c("com.projectseele.client.EvaCommandFeedClient").getMethod("isOpticalRenderPass").invoke(null))return;
        long frame=((Number)c("com.projectseele.entity.FirstBattleSignals").getMethod("clientFrameTime").invoke(null)).longValue();if(frame==firstBattleDrawFrame)return;firstBattleDrawFrame=frame;
        Object signals=call(actor,"firstBattleSignals");int age=((Number)signals.getClass().getMethod("age",c("net.minecraft.world.entity.Entity")).invoke(signals,actor)).intValue();float partial=(Float)values[2];boolean berserk=(Boolean)call(actor,"isBerserk");
        if(firstBattleDraws==null){Path root=out.getParent().resolve("firstbattle");Files.createDirectories(root);firstBattleDraws=Files.newBufferedWriter(root.resolve("raw_draws.jsonl"),StandardOpenOption.CREATE_NEW);}
        var row=new LinkedHashMap<String,Object>();row.put("synced_age_ticks",age);row.put("actual_frame_nanos",frame);row.put("partial",partial);row.put("entity_id",hero);row.put("uuid",call(actor,new String[]{"getUUID","m_20148_"},new Class<?>[0]).toString());row.put("first_actual_main_draw",!rawBeginDrawRecorded);row.put("first_actual_berserk_main_draw",berserk&&!rawBerserkDrawRecorded);row.put("isPoweredOn",call(actor,"isPoweredOn"));row.put("isBerserk",berserk);
        var dorsal=c("com.projectseele.entity.EvaDorsalMechanism");row.put("eyes_enabled",dorsal.getMethod("eyesEnabled",ec).invoke(null,actor));row.put("eye_surface",dorsal.getMethod("eyeSurface",ec).invoke(null,actor));
        row.put("scene_seconds",signals.getClass().getMethod("time",c("net.minecraft.world.entity.Entity"),float.class).invoke(signals,actor,partial));
        var transforms=c("com.projectseele.client.render.EvaRigTransforms");var boneType=c("software.bernie.geckolib.cache.object.GeoBone");var pivot=transforms.getDeclaredMethod("pivot",boneType);pivot.setAccessible(true);var point=transforms.getDeclaredMethod("point",boneType,c("org.joml.Vector3f"),c("org.joml.Matrix4f"));point.setAccessible(true);var pivots=new LinkedHashMap<String,double[]>();
        for(String name:List.of("head","foot_l","foot_r")){Object bone=((Optional<?>)values[1].getClass().getMethod("getBone",String.class).invoke(values[1],name)).orElse(null);if(bone!=null)pivots.put(name,xyz(point.invoke(null,bone,pivot.invoke(null,bone),values[3])));}
        row.put("actual_world_bone_pivots",pivots);row.put("model_to_world",values[3].getClass().getMethod("get",float[].class).invoke(values[3],(Object)new float[16]));row.put("pose_entry_blend_window_seconds",.4);row.put("production_camera_entry_window_seconds",1.2);row.put("pixel_visibility_verified",false);
        append(firstBattleDraws,row);firstBattleDrawCount++;rawBeginDrawRecorded=true;if(berserk)rawBerserkDrawRecorded=true;
    }
    private static void collectRenderedBones(Object bone,Map<String,Object> result)throws Exception {
        result.put((String)call(bone,"getName"),bone);
        for(Object child:(List<?>)call(bone,"getChildBones"))collectRenderedBones(child,result);
    }
    private static void finalPose(Object[] values)throws Exception {
        if(AFTER_FIRST_BATTLE&&!ready){firstBattleRawDraw(values);return;}
        if(!ready||done||failed||age<0||active==null)return;Object actor=values[0];
        if(!call(actor,new String[]{"getUUID","m_20148_"},new Class<?>[0]).equals(call(active,new String[]{"getUUID","m_20148_"},new Class<?>[0])))return;
        if((Boolean)c("com.projectseele.client.render.ShaderShadowPassR44").getMethod("active").invoke(null))return;
        if((Boolean)c("com.projectseele.client.EvaCommandFeedClient").getMethod("isOpticalRenderPass").invoke(null))return;
        if(lastPoseAge==age&&!(HANDLING_ONLY&&((age>=78&&age<=105)||(age>=150&&age<=195))))return;lastPoseAge=age;float partial=(Float)values[2];var ec=c("com.projectseele.entity.EvaUnit01Entity");
        var row=new LinkedHashMap<String,Object>();row.put("variant",variants[segment]);row.put("age",age);row.put("server_tick",tick());row.put("wall_ns",System.nanoTime());row.put("partial",partial);row.put("uuid",call(actor,new String[]{"getUUID","m_20148_"},new Class<?>[0]).toString());row.put("position",position(actor));
        row.put("onGround",call(actor,new String[]{"onGround","m_20096_"},new Class<?>[0]));row.put("isVisuallyAirborneForRender",call(actor,"isVisuallyAirborneForRender"));
        int entityTicks=((Number)field(actor,"tickCount","f_19797_")).intValue();row.put("actual_client_entity_tick_count",entityTicks);
        row.put("actual_support_raw_entity_clock",entityTicks+(double)Math.max(0,Math.min(1,partial)));
        row.put("actual_client_game_time",call(field(mc,"level","f_91073_"),new String[]{"getGameTime","m_46467_"},new Class<?>[0]));
        double[] actualOrigin=position(actor);int oi=0;
        for(String[] aliases:List.of(new String[]{"xOld","f_19790_"},new String[]{"yOld","f_19791_"},new String[]{"zOld","f_19792_"})){double before=((Number)field(actor,aliases)).doubleValue();actualOrigin[oi]=before+(actualOrigin[oi]-before)*partial;oi++;}
        row.put("actual_client_render_origin",actualOrigin);
        for(String name:List.of("getWeapon","getPowerTicks","isPoweredOn","isBerserk","isPilotProne","isPilotCrouching","getOrdinaryAttackStage","pilotControlLockedForReviewR52","isVisuallyMovingForRender"))row.put(name,call(actor,name));
        var runIntent=ec.getDeclaredMethod("isVisualRunRequested");runIntent.setAccessible(true);row.put("isVisualRunRequested",runIntent.invoke(actor));
        for(String name:List.of("rifleMoveBlend","rifleRunBlend","rifleGaitPhase"))row.put(name,call(actor,new String[]{name},new Class<?>[]{float.class},partial));
        row.put("key",call(actor,new String[]{"poseTransitionKey"},new Class<?>[]{float.class},partial));row.put("stance",call(actor,new String[]{"rifleStanceLevel"},new Class<?>[]{float.class},partial));row.put("phase",call(actor,new String[]{"combatPhaseR31"},new Class<?>[0]));row.put("melee_sequence",data(actor,"DATA_MELEE_SEQUENCE"));row.put("smash_sequence",data(actor,"DATA_SMASH_SEQUENCE"));row.put("knife_type",call(actor,new String[]{"getKnifeMotionType"},new Class<?>[]{float.class},partial));
        row.put("handling_active",c("com.projectseele.entity.EvaWeaponHandlingR45").getMethod("active",ec).invoke(null,actor));row.put("handling_phase",c("com.projectseele.entity.EvaWeaponHandlingR45").getMethod("phase",ec,float.class).invoke(null,actor,partial));
        row.put("sword_active",c("com.projectseele.entity.EvaSwordActionsR45").getMethod("active",ec).invoke(null,actor));row.put("sword_phase",c("com.projectseele.entity.EvaSwordActionsR45").getMethod("progress",ec,float.class).invoke(null,actor,partial));
        // Capture the already committed model directly; do not resample the production body/support state.
        var renderedBones=new LinkedHashMap<String,Object>();
        for(Object top:(List<?>)call(values[1],"topLevelBones"))collectRenderedBones(top,renderedBones);
        if(HANDLING_ONLY){
            row.put("ordinaryStandingSupportLockedR52",call(actor,"ordinaryStandingSupportLockedR52"));
            row.put("actual_airAge",c("com.projectseele.entity.EvaGameplayMotionR32").getMethod("airAge",ec,float.class).invoke(null,actor,partial));
            var memoryField=c("com.projectseele.entity.EvaOrdinaryStandingSupportR52").getDeclaredField("MEMORY");memoryField.setAccessible(true);var memoryMap=memoryField.get(null);
            var memory=memoryMap.getClass().getMethod("get",Object.class).invoke(memoryMap,actor);var facts=new LinkedHashMap<String,Object>();facts.put("present",memory!=null);
            if(memory!=null){for(String name:List.of("changed","last","from","target","action","actionFrom","correction","lastPoseClock","groundTime","groundY","leftGround","rightGround","groundFloor")){var f=memory.getClass().getDeclaredField(name);f.setAccessible(true);Object value=f.get(memory);facts.put(name,name.equals("correction")?value!=null:value);}}
            row.put("actual_ordinary_support_memory",facts);
            var historyField=c("com.projectseele.client.render.EvaPoseTransition").getDeclaredField("STATES");historyField.setAccessible(true);
            Object history=((Map<?,?>)historyField.get(null)).get(actor);var exit=new LinkedHashMap<String,Object>();exit.put("present",history!=null);
            if(history!=null)for(String name:List.of("time","start","duration","liveAction","weapon","weaponGuardExit","entryCorrection","entryStart","entryEnd","actionPhase","recordedFrame")){
                var f=history.getClass().getDeclaredField(name);f.setAccessible(true);exit.put(name,f.get(history));
            }
            row.put("actual_pose_transition_history",exit);
        }
        var names=renderedBones.keySet();var bones=new LinkedHashMap<String,Object>();var transforms=c("com.projectseele.client.render.EvaRigTransforms");var modelMethod=transforms.getDeclaredMethod("model",c("software.bernie.geckolib.cache.object.GeoBone"));modelMethod.setAccessible(true);
        for(String name:names){Object bone=((Optional<?>)values[1].getClass().getMethod("getBone",String.class).invoke(values[1],name)).orElse(null);if(bone==null)continue;var matrix=modelMethod.invoke(null,bone);bones.put(name,matrix.getClass().getMethod("get",float[].class).invoke(matrix,(Object)new float[16]));}row.put("final_rendered_model_bones",bones);row.put("finger_joint_count",names.stream().filter(n->n.startsWith("r45_hand_")).count());row.put("production_pose_resampled_by_tool",false);
        var pivotMethod=transforms.getDeclaredMethod("pivot",c("software.bernie.geckolib.cache.object.GeoBone"));pivotMethod.setAccessible(true);
        var pointMethod=transforms.getDeclaredMethod("point",c("software.bernie.geckolib.cache.object.GeoBone"),c("org.joml.Vector3f"),c("org.joml.Matrix4f"));pointMethod.setAccessible(true);
        var pivots=new LinkedHashMap<String,double[]>();
        for(String name:List.of("head","foot_l","foot_r")){Object bone=((Optional<?>)values[1].getClass().getMethod("getBone",String.class).invoke(values[1],name)).orElse(null);if(bone!=null)pivots.put(name,xyz(pointMethod.invoke(null,bone,pivotMethod.invoke(null,bone),values[3])));}
        row.put("actual_world_bone_pivots",pivots);row.put("camera_view",cameraView);
        row.put("model_to_world",values[3].getClass().getMethod("get",float[].class).invoke(values[3],(Object)new float[16]));
        Object foot=c("com.projectseele.client.render.EvaFootWitnessR44").getMethod("capture",ec,c("software.bernie.geckolib.cache.object.BakedGeoModel"),float.class,c("org.joml.Matrix4f")).invoke(null,actor,values[1],partial,values[3]);row.put("actual_foot_witness",foot);
        row.put("pilot_server_position",position(player));row.put("entry_socket",xyz(call(actor,"getEntryPlugSocketPosition")));pending=row;
        row.put("pilot_server_forward_input",field(player,"zza","f_20902_"));row.put("pilot_server_sideways_input",field(player,"xxa","f_20900_"));
    }
    private static void renderEnd()throws Exception {
        if(!ready||done||failed||switching||age<0||pending==null)return;
        long poseWall=((Number)pending.get("wall_ns")).longValue();
        if(poseWall!=lastWrittenWallNanos&&(lastWrittenSegment!=segment||lastWrittenAge!=((Number)pending.get("age")).intValue()||HANDLING_ONLY&&((age>=78&&age<=105)||(age>=150&&age<=195)))){
            append(poses,pending);lastWrittenSegment=segment;lastWrittenAge=((Number)pending.get("age")).intValue();lastWrittenWallNanos=poseWall;
        }
        long now=System.nanoTime();long interval=segment==1&&age>=466&&age<=510?33_333_333L:100_000_000L;
        if(now-lastCapture<interval)return;if(!IMAGE_SLOTS.tryAcquire()){dropped++;return;}lastCapture=now;
        var row=new LinkedHashMap<>(pending);String name=String.format(Locale.ROOT,"rig%d_%05d_%05d.jpg",variants[segment],age,frame++);row.put("file",name);row.put("capture_ns",now);row.put("frame",frame-1);row.put("fps",call(mc,new String[]{"getFps","m_260875_"},new Class<?>[0]));
        Object target=call(mc,new String[]{"getMainRenderTarget","m_91385_"},new Class<?>[0]);Object image=m(c("net.minecraft.client.Screenshot"),new String[]{"takeScreenshot","m_92279_"},c("com.mojang.blaze3d.pipeline.RenderTarget")).invoke(null,target);append(frames,row);
        WRITER.execute(()->{try{c("com.projectseele.client.visual.NativeReviewFrames").getMethod("writeJpeg",c("com.mojang.blaze3d.platform.NativeImage"),Path.class).invoke(null,image,out.resolve("frames").resolve(name));}catch(Throwable error){fail(error);}finally{try{call(image,"close");}catch(Exception ignored){}IMAGE_SLOTS.release();}});
    }
    private static void finish()throws Exception {
        done=true;append(inputs,Map.of("kind","inputs_complete","ticks",HANDLING_ONLY?210:Arrays.stream(lengths).sum(),"frames",frame,"dropped",dropped));
        execute(server,()->{try{call(player,new String[]{"stopRiding","m_8127_"},new Class<?>[0]);for(Object actor:actors)if(actor!=null)call(actor,new String[]{"discard","m_146870_"},new Class<?>[0]);}catch(Throwable error){fail(error);}});
        WRITER.execute(()->{try{poses.close();inputs.close();frames.close();write("CAPTURE_COMPLETE.json",Map.of("input_sequence_complete",true,"native_frames",frame,"dropped",dropped,"native_visual_acceptance",false,"production_code_changed",false));}catch(Throwable error){fail(error);}try{execute(mc,()->{try{call(mc,new String[]{"stop","m_91395_"},new Class<?>[0]);}catch(Exception ignored){}});}catch(Exception ignored){}});
    }
}

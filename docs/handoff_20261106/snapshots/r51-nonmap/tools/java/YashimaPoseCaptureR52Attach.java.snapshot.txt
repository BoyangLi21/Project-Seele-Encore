import com.sun.tools.attach.VirtualMachine;
public final class YashimaPoseCaptureR52Attach
{
    public static void main(String[] args)throws Exception
    {var vm=VirtualMachine.attach(args[0]);try{if(!"yashima-pose-r52".equals(vm.getSystemProperties().getProperty("projectseele.regionalBuild")))throw new IllegalStateException("Wrong explicit fixture JVM");vm.loadAgent(args[1],args[2]);}finally{vm.detach();}}
}

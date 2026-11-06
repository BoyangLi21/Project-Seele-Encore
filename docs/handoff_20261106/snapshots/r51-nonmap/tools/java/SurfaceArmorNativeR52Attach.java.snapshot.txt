import com.sun.tools.attach.VirtualMachine;
public final class SurfaceArmorNativeR52Attach {
    public static void main(String[] args)throws Exception {
        var vm=VirtualMachine.attach(args[0]);try{
            var p=vm.getSystemProperties();if(!"surface-armor-r52".equals(p.getProperty("projectseele.regionalBuild"))||!"candidate6".equals(p.getProperty("projectseele.surfaceArmorCandidateR52")))throw new IllegalStateException("Exact candidate6 surface fixture JVM required");
            vm.loadAgent(args[1],"start");
        }finally{vm.detach();}
    }
}

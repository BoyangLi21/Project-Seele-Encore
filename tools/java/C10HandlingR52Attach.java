import com.sun.tools.attach.VirtualMachine;
public final class C10HandlingR52Attach {
    public static void verifyTarget(java.util.Properties properties) {
        String mode=properties.getProperty("projectseele.regionalBuild");
        if(!"true".equals(properties.getProperty("projectseele.ordinaryHandlingC10R52"))||!"true".equals(properties.getProperty("projectseele.ordinaryHandlingOnlyR52"))||"true".equals(properties.getProperty("projectseele.firstBattleThenOrdinaryR52"))||"true".equals(properties.getProperty("projectseele.firstBattleThenHandlingR52")))throw new IllegalStateException("Explicit standalone C10 fixture only");
        boolean first="true".equals(properties.getProperty("projectseele.firstBattleThenOrdinaryR52"));
        boolean handling="true".equals(properties.getProperty("projectseele.ordinaryHandlingOnlyR52"));
        boolean combined="true".equals(properties.getProperty("projectseele.firstBattleThenHandlingR52"));
        if(!"ordinary-motion-r52".equals(mode)&&!("r10-firstbattle".equals(mode)&&first))throw new IllegalStateException("Wrong fixture JVM");
        if(handling&&first&&!combined)throw new IllegalStateException("Combined handling mode not explicit");
        if(combined&&(!handling||!first||!"r10-firstbattle".equals(mode)))throw new IllegalStateException("Incomplete combined handling mode");
    }
    public static void main(String[] arguments)throws Exception {
        if(arguments.length!=2)throw new IllegalArgumentException("Expected PID and agent JAR");
        var vm=VirtualMachine.attach(arguments[0]);try{
            verifyTarget(vm.getSystemProperties());
            vm.loadAgent(arguments[1],"start");
        }finally{vm.detach();}
    }
}

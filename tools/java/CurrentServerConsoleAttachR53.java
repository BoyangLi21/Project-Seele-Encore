import com.sun.tools.attach.VirtualMachine;

/** Root-executed client for the pinned ordinary stop agent. */
public final class CurrentServerConsoleAttachR53
{
    public static void main(String[] args) throws Exception
    {
        if(args.length!=4)throw new IllegalArgumentException("pid fresh_agent_jar exact_world fresh_receipt required");
        VirtualMachine vm=VirtualMachine.attach(args[0]);
        try{vm.loadAgent(args[1],args[2]+"|"+args[3]);}finally{vm.detach();}
    }
}

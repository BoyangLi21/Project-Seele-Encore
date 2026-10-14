import com.sun.tools.attach.VirtualMachine;
public final class CurrentGameplayReadOnlyAttachR53
{
    public static void main(String[] args) throws Exception
    {
        if(args.length!=4)throw new IllegalArgumentException("pid agent output seconds required");
        var vm=VirtualMachine.attach(args[0]);
        try{vm.loadAgent(args[1],args[2]+"|"+args[3]);}finally{vm.detach();}
    }
}

import com.sun.tools.attach.VirtualMachine;
public final class CurrentClientInputAttachV5R53
{
    public static void main(String[] args) throws Exception
    {
        if(args.length<5)throw new IllegalArgumentException("pid agent action output values required");
        var vm=VirtualMachine.attach(args[0]);
        try{vm.loadAgent(args[1],String.join("|",java.util.Arrays.copyOfRange(args,2,args.length)));}finally{vm.detach();}
    }
}

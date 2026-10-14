import com.sun.tools.attach.VirtualMachine;

public final class NamedPersonnelReadOnlyAttachR53
{
    public static void main(String[] args) throws Exception
    {
        if (args.length != 6)
        {
            throw new IllegalArgumentException("pid agent.jar plan.json freshOutputDirectory actualLiveWorldPath groupPrefix required; '-' selects all named groups");
        }
        var vm = VirtualMachine.attach(args[0]);
        try
        {
            vm.loadAgent(args[1], String.join("|", args[2], args[3], args[4], args[5]));
        }
        finally
        {
            vm.detach();
        }
    }
}

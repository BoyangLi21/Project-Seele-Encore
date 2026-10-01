import com.sun.tools.attach.VirtualMachine;
import java.nio.file.Path;

/** Explicit PID only; never scans or attaches unrelated JVMs. */
public final class R44TokyoInspectAttach
{
    public static void main(String[] args) throws Exception
    {
        if(args.length!=6)throw new IllegalArgumentException("pid agent.jar inspect|inspect-and-halt expectedJob expectedWorld output.json");
        if(!args[2].equals("inspect")&&!args[2].equals("inspect-and-halt"))throw new IllegalArgumentException(args[2]);
        String job=Path.of(args[3]).toAbsolutePath().normalize().toString();
        String world=Path.of(args[4]).toAbsolutePath().normalize().toString();
        if(!Path.of(world).getFileName().toString().equals("SEELE_FIELD_R44_REVIEW"))throw new IllegalArgumentException("Wrong expected world");
        var vm=VirtualMachine.attach(args[0]);
        try
        {
            String actual=vm.getSystemProperties().getProperty("projectseele.r44TokyoQualityJob","");
            if(!Path.of(actual).toAbsolutePath().normalize().toString().equals(job))throw new IllegalStateException("Explicit PID does not run expected quality job: "+actual);
            vm.loadAgent(Path.of(args[1]).toAbsolutePath().toString(),String.join("|",args[2],job,world,Path.of(args[5]).toAbsolutePath().normalize().toString()));
        }
        finally{vm.detach();}
    }
}

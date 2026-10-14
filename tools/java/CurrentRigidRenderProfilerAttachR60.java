import com.sun.tools.attach.VirtualMachine;
public final class CurrentRigidRenderProfilerAttachR60
{
    public static void main(String[] a)throws Exception
    {if(a.length!=5)throw new IllegalArgumentException("pid agentjar fresh_external_jsonl frame_count seconds required");var vm=VirtualMachine.attach(a[0]);try{vm.loadAgent(a[1],a[2]+"|"+a[3]+"|"+a[4]);}finally{vm.detach();}}
}

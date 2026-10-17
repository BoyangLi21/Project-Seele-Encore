package com.projectseele.world;

public final class NervPreparationRecoveryR53Test
{
    public static void main(String[] args)
    {
        int checked=0;
        // These are persisted phases from saves produced before the front seal
        // was moved ahead of guide deployment, not a reset to initial setup.
        String[][] saved={{"READY","FRONT_RECOVER_CLAMPS"},{"RELEASE_CLAMPS","FRONT_RECOVER_CLAMPS"},
                {"RAISE","FRONT_RECOVER_LOWER"},{"SERVICE_BRIDGE_OPEN","FRONT_RECOVER_BRIDGE"}};
        for(var row:saved)
        {
            var old=NervAssemblyOwnerR52.Prepare.valueOf(row[0]);
            var next=NervAssemblyOwnerR52.frontSealRecoveryR53(old,true,false);
            if(!next.name().equals(row[1]))throw new AssertionError("Unsafe persisted-phase recovery: "+row[0]);
            if(NervAssemblyOwnerR52.frontSealRecoveryR53(next,true,false)!=next)throw new AssertionError("Restart would restart an in-progress physical recovery");
            checked+=2;
        }
        for(var phase:NervAssemblyOwnerR52.Prepare.values())
        {
            if(NervAssemblyOwnerR52.frontSealRecoveryR53(phase,true,true)!=phase)throw new AssertionError("Open front must retain preparation progress");
            if(NervAssemblyOwnerR52.frontSealRecoveryR53(phase,false,false)!=phase)throw new AssertionError("Legacy assembly without a floor seal must retain preparation progress");
            checked+=2;
        }
        if(NervAssemblyOwnerR52.frontSealRecoveryR53(NervAssemblyOwnerR52.Prepare.INSERT,true,false)!=NervAssemblyOwnerR52.Prepare.INSERT)throw new AssertionError("Do not interrupt an unfinished original insertion");
        System.out.println("Persisted preparation recovery: "+(++checked)+" checks passed");
    }
}

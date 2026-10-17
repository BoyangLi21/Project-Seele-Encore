package com.projectseele.world;

/** Explicit UI intent; an underground destination never becomes a surface launch. */
public final class StaffUndergroundChoiceR52
{
    public static final String PREFIX="UNDERGROUND_DEPLOY:";
    public static final String PREPARE_AND_DEPLOY="underground_deploy";
    public record Choice(int unit,boolean prepareFirst) {}
    private StaffUndergroundChoiceR52() {}
    public static String request(int unit,boolean prepareFirst)
    {
        if(unit<0||unit>2)throw new IllegalArgumentException("Original unit required");
        return PREFIX+unit+":"+(prepareFirst?"prepare":"ready");
    }
    public static Choice parse(String request)
    {
        String[] fields=request.split(":",-1);
        if(fields.length!=3||!fields[0].equals("UNDERGROUND_DEPLOY"))throw new IllegalArgumentException("Invalid underground deployment request");
        int unit=Integer.parseInt(fields[1]);
        if(unit<0||unit>2||!java.util.Set.of("prepare","ready").contains(fields[2]))throw new IllegalArgumentException("Invalid underground deployment choice");
        return new Choice(unit,fields[2].equals("prepare"));
    }
    public static String initialOperation(String requested)
    {return requested.equals("deploy")||requested.startsWith("deploy_")||requested.equals(PREPARE_AND_DEPLOY)?"prepare":requested;}
    public static String readyContinuation(String requested,String phase)
    {
        if(!deploymentReady(phase))return "";
        return requested.equals(PREPARE_AND_DEPLOY)?"underground":requested.equals("deploy")||requested.startsWith("deploy_")?"launch":"";
    }
    public static boolean deploymentReady(String phase){return "SILO_READY".equals(phase);}
    public static boolean deployedDoorReady(String phase){return "DEPLOYED".equals(phase);}
}

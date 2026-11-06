package com.projectseele.compat;

import java.util.Set;
import java.util.TreeSet;
import java.util.concurrent.ConcurrentHashMap;

/** JDK-only transformation witness; safe for the optional-mod mixin bootstrap. */
public final class CityUnionActivationR45
{
    private static final Set<String> APPLIED=ConcurrentHashMap.newKeySet();
    private static volatile String backendReason="Not evaluated", actualCreateResource="";
    private static volatile boolean backendEligible;
    private CityUnionActivationR45() {}
    public static boolean required(){return Boolean.getBoolean("projectseele.r45CityBalancedUnionRequired");}
    public static void backendAbi(String resource,boolean eligible,String reason)
    {actualCreateResource=resource;backendEligible=eligible;backendReason=reason;}
    public static void applied(String mixin)
    {
        if(mixin.endsWith("CityExactUnionCreateMixinR45"))APPLIED.add("CityExactUnionCreateMixinR45");
        if(mixin.endsWith("CitySavedOwnerUnionMixinR45"))APPLIED.add("CitySavedOwnerUnionMixinR45");
    }
    public static String requiredFailure(boolean proofValid)
    {
        if(!required())return null;
        if(!Boolean.getBoolean("projectseele.r45CityBalancedUnion"))return "Required exact union was not requested";
        if(!backendEligible)return "Create producer was not accepted: "+backendReason;
        if(!proofValid)return "Current runtime native input/union contract is not ready";
        if(!APPLIED.contains("CityExactUnionCreateMixinR45")||!APPLIED.contains("CitySavedOwnerUnionMixinR45"))return "Actual required city mixin postApply witnesses are missing";
        return null;
    }
    public static String actualCreateResource(){return actualCreateResource;}
    public static String backendReason(){return backendReason;}
    public static boolean backendEligible(){return backendEligible;}
    public static Set<String> appliedMixins(){return Set.copyOf(new TreeSet<>(APPLIED));}
}

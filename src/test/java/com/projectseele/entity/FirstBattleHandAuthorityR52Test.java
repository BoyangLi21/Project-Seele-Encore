package com.projectseele.entity;

import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Map;

/** Real admitted hand contract and parsed old/new performances, without entities or a world. */
public final class FirstBattleHandAuthorityR52Test
{
    private static String[] parsedEvaBones(Path clip) throws Exception
    {
        Method read=FirstBattleClip.class.getDeclaredMethod("read",java.io.InputStream.class,String.class);
        read.setAccessible(true);
        Object data;
        try(var stream=Files.newInputStream(clip)){data=read.invoke(null,stream,"R52 hand ownership regression");}
        Method roles=data.getClass().getDeclaredMethod("roles");roles.setAccessible(true);
        Object role=((Map<?,?>)roles.invoke(data)).get("eva");
        Method bones=role.getClass().getDeclaredMethod("bones");bones.setAccessible(true);
        return (String[])bones.invoke(role);
    }
    public static void main(String[] args) throws Exception
    {
        System.setProperty("projectseele.firstBattleReviewClip",args[0]);
        System.setProperty("projectseele.dorsalPoseReview",Path.of(args[0]).getParent().resolve("eva_dorsal_r30.json").toString());
        System.setProperty("projectseele.handRigDirectoryR45",args[2]);
        var rig=EvaAnatomicalHandsR45.rig(1);
        if(rig==null||rig.joints().size()!=34)throw new AssertionError("Actual admitted 34-joint hand contract not loaded");
        var expected=rig.joints().stream().map(EvaAnatomicalHandsR45.Joint::name).toList();
        if(FirstBattleClip.ownsAnatomicalHandsR52(1))throw new AssertionError("Old R51 clip stole its unkeyed anatomical hands");
        String[] candidate=parsedEvaBones(Path.of(args[1]));
        if(!FirstBattleClip.ownsCompleteHandBoneSetR52(candidate,expected))throw new AssertionError("Complete candidate hands still lost to late gameplay writer");
        var missing=new ArrayList<>(Arrays.asList(candidate));missing.remove(expected.get(0));
        if(FirstBattleClip.ownsCompleteHandBoneSetR52(missing.toArray(String[]::new),expected))throw new AssertionError("Incomplete candidate disabled fallback hand writer");
        if(FirstBattleClip.ownsCompleteHandBoneSetR52(candidate,expected.subList(0,30)))throw new AssertionError("Legacy 30-joint rig admitted as a complete 34-joint performance");
        var duplicated=new ArrayList<>(expected);duplicated.set(0,duplicated.get(1));
        if(FirstBattleClip.ownsCompleteHandBoneSetR52(candidate,duplicated))throw new AssertionError("Duplicate hand key bypassed exact complete-set gate");
        System.out.println("PASS: parsed old R51=false; parsed candidate with all actual34=true; missing1=false; legacy30=false; duplicate=false; jaw owner unchanged");
    }
}

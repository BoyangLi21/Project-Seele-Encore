import java.lang.instrument.Instrumentation;
import java.nio.file.*;
import java.sql.*;
import java.util.*;

/** Clear stale derived columns for unfinished source chunks in the isolated cache only. */
public final class ClearIncompleteLodR55 {
    record Key(int detail,int x,int z) {}
    static Object call(Object target,String name,Object... args)throws Exception {
        Class<?> type=target instanceof Class<?> c?c:target.getClass();
        for(var method:type.getMethods())if(method.getName().equals(name)&&method.getParameterCount()==args.length)
            try{return method.invoke(target instanceof Class<?>?null:target,args);}catch(IllegalArgumentException ignored){}
        throw new NoSuchMethodException(name);
    }
    public static void agentmain(String argument,Instrumentation instrumentation) {
        new Thread(()->{
            Path input=Path.of(argument),receipt=input.resolveSibling("incomplete-invalidation.json");
            try {
                ClassLoader loader=null;
                for(Class<?> type:instrumentation.getAllLoadedClasses())
                    if(type.getName().equals("com.projectseele.ProjectSeele"))loader=type.getClassLoader();
                if(loader==null)throw new IllegalStateException("Project loader unavailable");
                Object gson=Class.forName("com.google.gson.Gson",true,loader).getConstructor().newInstance();
                Map<?,?> plan=(Map<?,?>)call(gson,"fromJson",Files.readString(input),Map.class);
                Path expected=Path.of((String)plan.get("cache_world"),"dimensions","projectseele","geofront","data","DistantHorizons.sqlite").toRealPath();
                if(!expected.toString().replace('\\','/').contains("/cache-server/SEELE_R53_WORLD/"))
                    throw new IllegalStateException("Only the isolated cache world is permitted");
                Object world=call(Class.forName("com.seibel.distanthorizons.core.api.internal.SharedApi",true,loader),"getAbstractDhWorld");
                Object provider=null;
                for(Object level:(Iterable<?>)call(world,"getAllLoadedLevels"))
                    if(call(level,"getLevelWrapper").toString().contains("projectseele:geofront"))provider=call(level,"getFullDataProvider");
                if(provider==null)throw new IllegalStateException("GeoFront provider unavailable");
                Object repo=provider.getClass().getField("repo").get(provider);
                Path actual=((java.io.File)repo.getClass().getField("databaseFile").get(repo)).toPath().toRealPath();
                if(!actual.equals(expected))throw new IllegalStateException("Unexpected database "+actual);
                if(!((Map<?,?>)provider.getClass().getField("queuedUpdateCountsByPos").get(provider)).isEmpty()
                   ||!((Set<?>)provider.getClass().getField("updatingPosSet").get(provider)).isEmpty())
                    throw new IllegalStateException("Wait for native imports and parent updates to finish");
                Connection nativeConnection=(Connection)call(repo,"getConnection");
                Driver driver=(Driver)Class.forName("dh_sqlite.JDBC",true,loader).getConstructor().newInstance();
                try(Connection sql=driver.connect(nativeConnection.getMetaData().getURL(),new Properties())) {
                    try(Statement statement=sql.createStatement();ResultSet rows=statement.executeQuery("select count(*) from FullData where ApplyToParent=1 or ApplyToChildren=1")) {
                        rows.next();
                        if(rows.getInt(1)!=0)throw new IllegalStateException("Pending native hierarchy updates");
                    }
                    int maximum;
                    try(Statement statement=sql.createStatement();ResultSet rows=statement.executeQuery("select max(DetailLevel) from FullData")) {rows.next();maximum=rows.getInt(1);}
                    if(maximum>30)throw new IllegalStateException("Unexpected hierarchy depth");
                    Set<Key> removed=new LinkedHashSet<>(),frontier=new LinkedHashSet<>();
                    for(Object item:(List<?>)plan.get("tiles")) {
                        List<?> tile=(List<?>)item;
                        int x=((Number)tile.get(0)).intValue(),z=((Number)tile.get(1)).intValue();
                        for(int detail=0;detail<=maximum;detail++)removed.add(new Key(detail,x>>detail,z>>detail));
                    }
                    for(Key parent:removed)if(parent.detail>0)
                        for(int dx=0;dx<2;dx++)for(int dz=0;dz<2;dz++)
                            frontier.add(new Key(parent.detail-1,parent.x*2+dx,parent.z*2+dz));
                    frontier.removeAll(removed);
                    int deleted=0,queued=0;
                    sql.setAutoCommit(false);
                    try(PreparedStatement delete=sql.prepareStatement("delete from FullData where DetailLevel=? and PosX=? and PosZ=?");
                        PreparedStatement mark=sql.prepareStatement("update FullData set ApplyToParent=1 where DetailLevel=? and PosX=? and PosZ=?")) {
                        for(Key key:removed){delete.setInt(1,key.detail);delete.setInt(2,key.x);delete.setInt(3,key.z);deleted+=delete.executeUpdate();}
                        for(Key key:frontier){mark.setInt(1,key.detail);mark.setInt(2,key.x);mark.setInt(3,key.z);queued+=mark.executeUpdate();}
                        sql.commit();
                    }catch(Throwable failure){sql.rollback();throw failure;}
                    Files.writeString(receipt,(String)call(gson,"toJson",Map.of("done",true,"database",actual.toString(),
                        "invalidated_base_tiles",((List<?>)plan.get("tiles")).size(),"deleted_rows_including_parents",deleted,
                        "retained_children_queued",queued,"world_blocks_written",false)));
                }
            }catch(Throwable failure) {
                try{Files.writeString(receipt,"{\"done\":false,\"error\":\""+failure.toString().replace("\\","/").replace("\"","'")+"\"}");}catch(Exception ignored){}
            }
        },"SEELE incomplete-source LOD invalidation").start();
    }
}

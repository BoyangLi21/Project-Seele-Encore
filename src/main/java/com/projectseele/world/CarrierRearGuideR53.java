package com.projectseele.world;

import com.google.gson.*;
import com.google.gson.stream.JsonReader;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.*;
import org.joml.*;
import java.lang.Math;

/** Source-facet rear attachments for the supplied carrier. No world construction. */
public final class CarrierRearGuideR53
{
    public static final String SELECTION="eva/carrier_rear_guides_r53_sources.json";
    public static final String HARDWARE="mesh/carrier_rear_guides_r53.json";
    public static final String RAILS="facility/r52_upright_guideway_paths.json";
    public static final double STOW_LIFT=7;
    public record Mount(String name,Vec3 ball){}
    public record Template(String name,String frame,String role,NervRigidMeshSweepR52 mesh,double[] rgb){}
    public record Fixed(String name,String leg,String mount,String component,NervLegacyCarrierRideR52.Piece steel)
    {
        public AABB bounds(){return steel.mesh().envelope(steel.frame(),steel.frame());}
    }
    public record Anchor(String leg,String mount,BlockPos at,String state,Vec3 point,Vec3 normal,boolean importedUpright)
    {
        public Anchor(String leg,String mount,BlockPos at,String state,Vec3 point,Vec3 normal)
        {this(leg,mount,at,state,point,normal,false);}
    }
    public record FixedGeometry(String directory,String legacySource,List<Fixed> pieces,List<Anchor> anchors,
                                NervStaticSpatialIndexR52<Fixed> index,NervStaticSpatialIndexR52<Anchor> anchorIndex){}
    public record Hardware(List<Mount> mounts,List<Template> parts,String fingerprint)
    {
        public RigidTransform headFrame(RigidTransform root,String mount,Vec3 direction)
        {
            require(root.transformVector(new Vec3(0,1,0)).distanceTo(new Vec3(0,1,0))<1e-5,
                "Rear guide carrier must retain its upright root");
            require(direction!=null&&Double.isFinite(direction.lengthSqr())&&direction.lengthSqr()>1e-12,
                "Actual route tangent required");
            var z=direction.normalize();var fixedX=root.transformVector(new Vec3(1,0,0));
            var x=fixedX.subtract(z.scale(fixedX.dot(z)));
            require(x.lengthSqr()>.01,"Rear guide tangent frame degenerates");
            x=x.normalize();var y=z.cross(x).normalize();
            var basis=new Matrix3f().setColumn(0,x.toVector3f()).setColumn(1,y.toVector3f()).setColumn(2,z.toVector3f());
            var ball=mounts.stream().filter(m->m.name().equals(mount)).findFirst().orElseThrow().ball();
            return RigidTransform.of(root.transformPoint(ball).subtract(y.scale(.35)),new Quaternionf().setFromNormalized(basis).normalize());
        }

        public List<NervLegacyCarrierRideR52.Piece> partsAt(RigidTransform root,float rise,Vec3 direction,double slide)
        {return partsAt(root,rise,direction,slide,0);}

        public List<NervLegacyCarrierRideR52.Piece> partsAt(RigidTransform root,float rise,Vec3 direction,double slide,double lift)
        {return partsAt(root,rise,direction,slide,lift,CarrierMountProfileR53.LEGACY);}

        public List<NervLegacyCarrierRideR52.Piece> partsAt(RigidTransform root,float rise,Vec3 direction,double slide,double lift,CarrierMountProfileR53.State mounting)
        {
            require(Double.isFinite(lift)&&lift>=0&&lift<=STOW_LIFT,"Bounded measured transfer lift required");
            require(Float.isFinite(rise)&&rise>=0&&rise<=1&&Double.isFinite(slide)&&slide<=0&&slide>=-.65,
                "Bounded rear guide actuators required");
            require(mounting.transverse()==0||parts.stream().anyMatch(p->p.role().equals("lateral_rod")),"Transverse motion requires the actual telescoping source");
            var body=mounting.bodyFrame(root,rise);
            var lifted=mounting.headLiftFrame(root,rise,lift);
            var frames=new HashMap<String,RigidTransform>();frames.put("ROOT",mounting.guideRootFrame(root,rise));frames.put("LIFT",lifted);
            for(var mount:mounts)frames.put(mount.name(),headFrame(lifted,mount.name(),direction));
            var result=new ArrayList<NervLegacyCarrierRideR52.Piece>();
            for(var part:CarrierMountProfileR53.rearTemplates(this,mounting))
            {
                var frame=mounting.shallowBay()&&(part.role().equals("source_weld")||part.name().contains("/mount/0"))
                        ?body:Objects.requireNonNull(frames.get(part.frame()));
                if(NervBankHeadTransferR53.slides(part.role()))frame=frame.compose(new RigidTransform(new Vec3(0,0,slide),0,0,0,1));
                frame=CarrierMountProfileR53.transverseFrame(root,frame,part,mounting);
                result.add(new NervLegacyCarrierRideR52.Piece(part.name(),part.mesh(),part.rgb(),frame,part.role()));
            }
            return List.copyOf(result);
        }

        public List<AABB> verticalPorts()
        {
            var result=new ArrayList<AABB>();
            // Same vertical tangent frame as the actual rear rail sections.
            for(var mount:mounts)
            {
                double x=-mount.ball().x,z=-mount.ball().z-.35;
                result.add(new AABB(x-.305,0,z-.555,x+.305,0,z-.075));
            }
            return List.copyOf(result);
        }
    }

    private static boolean checked;
    private static Hardware selected;
    private static JsonObject manifest;
    private static FixedGeometry fixed;
    private record ContactCell(List<Vec3> vertices,List<Vec3> normals){}
    private static final Map<NervRigidMeshSweepR52,List<ContactCell>> CONTACT_CELLS=new IdentityHashMap<>();

    public static synchronized FixedGeometry fixed()
    {
        if(selected()==null)return null;
        if(fixed!=null)return fixed;
        try
        {
            String legacy=manifest.get("legacy_upright_sha256").getAsString(),directory=manifest.get("directory_sha256").getAsString();
            String resource=manifest.getAsJsonObject("resources").get(RAILS).getAsString();
            require(directory.matches("[0-9a-f]{64}"),"Declared original route directory required");
            FixedGeometry original;
            // Root has already parsed and validated this exact source before
            // world simulation. Share those immutable meshes instead of parsing
            // the same giant decimal document on the first actuator tick.
            if(legacy.equals(resource)&&legacy.equals(NervUprightGuidewayR52.sourceSha256()))
            {
                var pieces=new ArrayList<Fixed>();var anchors=new ArrayList<Anchor>();
                for(var p:NervUprightGuidewayR52.pieces())
                {
                    var steel=p.steel();pieces.add(new Fixed(p.name(),p.leg(),p.side()<0?"rear_l":"rear_r",
                            Set.of("head","web").contains(p.component())?p.component():"support",
                            new NervLegacyCarrierRideR52.Piece(p.name(),steel.mesh(),steel.rgb(),steel.frame(),p.component())));
                }
                for(var a:NervUprightGuidewayR52.anchors())anchors.add(new Anchor(a.leg(),"shared",a.at(),a.state(),a.bearing(),a.normal(),true));
                original=new FixedGeometry(directory,legacy,List.copyOf(pieces),List.copyOf(anchors),
                        new NervStaticSpatialIndexR52<>(pieces,Fixed::bounds),
                        new NervStaticSpatialIndexR52<>(anchors,a->new AABB(a.point(),a.point()).inflate(.0001)));
            }
            else
            {
                byte[] bytes=EvaOriginalMeshGeometryR52.classpathBytes(RAILS);
                require(sha(bytes).equals(resource),"Rear fixed geometry bytes changed");
                original=readExistingFixed(bytes,legacy,directory);
            }
            var transfer=CarrierTransferRailsR53.selected();if(transfer==null)return fixed=original;
            require(transfer.directory().equals(original.directory()),"Transfer rails require the same actual directory");
            var pieces=new ArrayList<>(original.pieces());pieces.addAll(transfer.fixed());
            var anchors=new ArrayList<>(original.anchors());anchors.addAll(transfer.anchors());
            return fixed=new FixedGeometry(original.directory(),original.legacySource(),List.copyOf(pieces),List.copyOf(anchors),
                new NervStaticSpatialIndexR52<>(pieces,Fixed::bounds),
                new NervStaticSpatialIndexR52<>(anchors,a->new AABB(a.point(),a.point()).inflate(.0001)));
        }
        catch(IOException failure){throw new IllegalStateException("Selected fixed rear rail source unavailable",failure);}
    }

    static String actualHardwareSourceR53()
    { return selected()==null?"":manifest.getAsJsonObject("resources").get(HARDWARE).getAsString(); }

    /** The uninstalled diagnostic path cannot publish runtime geometry. */
    public static FixedGeometry readFixedForAudit(byte[] bytes,byte[] hardware)throws IOException
    {return readFixed(bytes,"uninstalled-diagnostic",sha(hardware),false);}

    public static FixedGeometry readExistingFixed(byte[] bytes,String expectedSha,String directory)throws IOException
    {
        require(directory.matches("[0-9a-f]{64}"),"Declared original route directory required");
        var pieces=new ArrayList<Fixed>();var anchors=new ArrayList<Anchor>();
        NervUprightGuidewayR52.readVisualR52(new ByteArrayInputStream(bytes),expectedSha,p->{
            var steel=p.steel();
            pieces.add(new Fixed(p.name(),p.leg(),p.side()<0?"rear_l":"rear_r",
                Set.of("head","web").contains(p.component())?p.component():"support",
                new NervLegacyCarrierRideR52.Piece(p.name(),steel.mesh(),steel.rgb(),steel.frame(),p.component())));
        },a->anchors.add(new Anchor(a.leg(),"shared",a.at(),a.state(),a.bearing(),a.normal(),true)));
        return new FixedGeometry(directory,expectedSha,List.copyOf(pieces),List.copyOf(anchors),
            new NervStaticSpatialIndexR52<>(pieces,Fixed::bounds),
            new NervStaticSpatialIndexR52<>(anchors,a->new AABB(a.point(),a.point()).inflate(.0001)));
    }

    private static FixedGeometry readFixed(byte[] bytes,String legacy,String expectedHardware,boolean requireSupports)throws IOException
    {
            var pieces=new ArrayList<Fixed>();var anchors=new ArrayList<Anchor>();var names=new HashSet<String>();
            String schema=null,hardware=null,directory=null;boolean complete=false,missing=false;
            // Do not materialize the 146 MB decimal document as a Gson tree.
            // Each measured primitive is validated before joining the index.
            try(var reader=new JsonReader(new InputStreamReader(new ByteArrayInputStream(bytes),StandardCharsets.UTF_8)))
            {
                reader.beginObject();
                while(reader.hasNext())switch(reader.nextName())
                {
                case "schema" -> schema=reader.nextString();
                case "hardware_sha256" -> hardware=reader.nextString();
                case "directory" -> directory=reader.nextString();
                case "supports_complete" -> complete=reader.nextBoolean();
                case "support_missing" -> missing=!JsonParser.parseReader(reader).getAsJsonArray().isEmpty();
                case "pieces" -> {
                reader.beginArray();while(reader.hasNext())
                {
                var p=JsonParser.parseReader(reader).getAsJsonObject();String name=p.get("name").getAsString(),component=p.get("component").getAsString();
                require(names.add(name)&&Set.of("head","web","support").contains(component),"Unique declared fixed rail part required");
                var a=p.getAsJsonArray("triangles_rgb");require(!a.isEmpty()&&a.size()%18==0,"Complete fixed rail triangles required");
                double[] rgb=new double[a.size()],xyz=new double[a.size()/2];
                for(int i=0,k=0;i<a.size();i+=6)
                {
                    for(int j=0;j<6;j++){rgb[i+j]=a.get(i+j).getAsDouble();require(Double.isFinite(rgb[i+j]),"Finite fixed rail vertices required");}
                    xyz[k++]=rgb[i];xyz[k++]=rgb[i+1];xyz[k++]=rgb[i+2];
                }
                var frame=new RigidTransform(point(p.getAsJsonArray("origin")),0,0,0,1);
                pieces.add(new Fixed(name,p.get("leg").getAsString(),p.get("mount").getAsString(),component,
                    new NervLegacyCarrierRideR52.Piece(name,new NervRigidMeshSweepR52(xyz),rgb,frame,component)));
                }reader.endArray();}
                case "sockets" -> {
                reader.beginArray();while(reader.hasNext())
                {
                var p=JsonParser.parseReader(reader).getAsJsonObject();
                if(!p.has("anchor")){require(!requireSupports,"Actual support seat required");continue;}
                var a=p.getAsJsonObject("anchor");var normal=point(a.getAsJsonArray("normal"));
                require(normal.lengthSqr()==1&&(Math.abs(normal.x)==1||Math.abs(normal.y)==1||Math.abs(normal.z)==1),"Native axis-aligned support face required");
                anchors.add(new Anchor(p.get("leg").getAsString(),p.get("mount").getAsString(),BlockPos.containing(point(a.getAsJsonArray("at"))),
                    a.get("state").getAsString(),point(a.getAsJsonArray("bearing")),normal));
                }reader.endArray();}
                default -> reader.skipValue();
                }
                reader.endObject();
            }
            require("projectseele.r53.rear-guide-rails.v1".equals(schema)&&(!requireSupports||complete&&!missing),"Complete measured rear rail supports required");
            require(expectedHardware.equals(hardware),"Fixed rails belong to another carrier hardware source");
            require(!pieces.isEmpty()&&(!requireSupports||!anchors.isEmpty()),"Fixed rails and actual native anchors required");
            require(directory.matches("[0-9a-f]{64}")&&(!requireSupports||legacy.matches("[0-9a-f]{64}")),"Declared route and world source required");
            return new FixedGeometry(directory,legacy,List.copyOf(pieces),List.copyOf(anchors),new NervStaticSpatialIndexR52<>(pieces,Fixed::bounds),
                new NervStaticSpatialIndexR52<>(anchors,a->new AABB(a.point(),a.point()).inflate(.0001)));
    }

    public static boolean anchorBears(Level level,Anchor anchor)
    {
        if(!level.hasChunkAt(anchor.at()))return false;
        // Imported upright seats retain their original finite-face contract;
        // a decorative repaint does not change that bearing. New transfer
        // sockets retain their authored block-state requirement as well.
        boolean originalUpright=anchor.importedUpright()&&anchor.mount().equals("shared")
            &&anchor.leg().equals(NervUprightGuidewayR52.canonicalPathR52(anchor.leg()));
        if(!originalUpright&&!BlockStateParser.serialize(level.getBlockState(anchor.at())).equals(anchor.state()))return false;
        var normal=anchor.normal();var u=Math.abs(normal.x)>.5?new Vec3(0,1,0):new Vec3(1,0,0);var v=normal.cross(u);
        for(var local:level.getBlockState(anchor.at()).getCollisionShape(level,anchor.at()).toAabbs())
        {
            var box=local.move(anchor.at());boolean matches=true;
            for(double x:new double[]{-.05,0,.05})for(double y:new double[]{-.05,0,.05})
            {
                var p=anchor.point().add(u.scale(x)).add(v.scale(y));
                double plane=normal.x>0?box.maxX:normal.x<0?box.minX:normal.y>0?box.maxY:normal.y<0?box.minY:normal.z>0?box.maxZ:box.minZ;
                double coordinate=normal.x!=0?p.x:normal.y!=0?p.y:p.z;
                if(Math.abs(coordinate-plane)>.0002||p.x<box.minX-.0002||p.x>box.maxX+.0002||p.y<box.minY-.0002||p.y>box.maxY+.0002||p.z<box.minZ-.0002||p.z>box.maxZ+.0002)matches=false;
            }
            if(matches)return true;
        }
        return false;
    }

    static String canonicalPath(DirectoryTrajectoryR52 path)
    {
        String outer=NervUprightGuidewayR52.canonicalPathR52(path.leg().id());
        return outer!=null?outer:CarrierTransferRailsR53.canonicalPath(path);
    }

    public static boolean finiteBankCapture(RigidTransform root,Vec3 direction,String leg)
    {
        var hardware=selected();var rails=fixed();if(hardware==null||rails==null)return false;
        int faces=0;
        for(var part:hardware.partsAt(root,1,direction,0))
        {
            if(!Set.of("upper_bearing","lower_bearing","side_bearing").contains(part.role()))continue;
            String mount=part.name().split("/")[1];var bounds=part.mesh().bounds();
            boolean side=part.role().equals("side_bearing");
            double plane=side?(part.name().endsWith("/-1")?bounds.maxX:bounds.minX):part.role().equals("upper_bearing")?bounds.minY:bounds.maxY;
            var nearby=rails.index().query(part.mesh().envelope(part.frame(),part.frame()).inflate(.001)).stream()
                .filter(p->p.leg().equals(leg)&&p.mount().equals(mount)&&p.component().equals("head")).toList();
            if(nearby.isEmpty())return false;
            // The entry end captures the leading finite half of each pad.
            // Its remaining half engages during the first four millimetres.
            for(double t:new double[]{.25,.5,.75})for(double z:new double[]{.001,.002,.003})
            {
                var local=side?new Vec3(plane,bounds.minY+(bounds.maxY-bounds.minY)*t,z):new Vec3(bounds.minX+(bounds.maxX-bounds.minX)*t,plane,z);
                if(distance(local,part.mesh().triangles(),RigidTransform.identity())>.00001)return false;
                var point=part.frame().transformPoint(local);double nearest=Double.POSITIVE_INFINITY;
                for(var rail:nearby)nearest=Math.min(nearest,distance(point,rail.steel().mesh().triangles(),rail.steel().frame()));
                if(nearest>.0002)return false;
            }
            faces++;
        }
        return faces==hardware.mounts().size()*5;
    }

    static boolean finiteTransferCapture(Level level,RigidTransform root,Vec3 direction,String leg,
                                         double lift,CarrierMountProfileR53.State mounting)
    {
        var hardware=selected();if(hardware==null||CarrierTransferRailsR53.selected()==null)return false;
        int faces=0;
        for(var part:hardware.partsAt(root,1,direction,0,lift,mounting))
        {
            if(!Set.of("upper_bearing","lower_bearing","side_bearing").contains(part.role()))continue;
            var bounds=part.mesh().bounds();boolean side=part.role().equals("side_bearing");
            double plane=side?(part.name().endsWith("/-1")?bounds.maxX:bounds.minX):part.role().equals("upper_bearing")?bounds.minY:bounds.maxY;
            String mount=part.name().split("/")[1];
            var nearby=CarrierTransferRailsR53.nearby(level,part.mesh().envelope(part.frame(),part.frame()).inflate(.001)).stream()
                .filter(p->p.leg().equals(leg)&&p.mount().equals(mount)&&p.component().equals("head")).toList();
            if(nearby.isEmpty())return false;
            for(double t:new double[]{.25,.5,.75})for(double z:new double[]{-.002,0,.002})
            {
                var local=side?new Vec3(plane,bounds.minY+(bounds.maxY-bounds.minY)*t,z):new Vec3(bounds.minX+(bounds.maxX-bounds.minX)*t,plane,z);
                if(distance(local,part.mesh().triangles(),RigidTransform.identity())>.00001)return false;
                var point=part.frame().transformPoint(local);double nearest=Double.POSITIVE_INFINITY;
                for(var rail:nearby)nearest=Math.min(nearest,distance(point,rail.steel().mesh().triangles(),rail.steel().frame()));
                if(nearest>.0002)return false;
            }
            faces++;
        }
        return faces==hardware.mounts().size()*5;
    }

    public static boolean namedContact(NervLegacyCarrierRideR52.Piece from,
                                      NervLegacyCarrierRideR52.Piece to,Fixed fixed,String leg)
    {return namedContact(from,to,fixed,leg,0);}

    public static boolean namedContact(NervLegacyCarrierRideR52.Piece from,
                                      NervLegacyCarrierRideR52.Piece to,Fixed fixed,String leg,double deviation)
    {
        if(!Double.isFinite(deviation)||deviation<0||deviation>=.0002)return false;
        if(!from.name().equals(to.name())||from.mesh()!=to.mesh()||!fixed.leg().equals(leg)
            ||!fixed.component().equals("head")||!fixed.mount().equals(from.name().split("/")[1])
            ||!Set.of("upper_bearing","lower_bearing","side_bearing").contains(from.role()))return false;
        var local=from.role().equals("upper_bearing")?new Vec3(0,1,0):
            from.role().equals("lower_bearing")?new Vec3(0,-1,0):new Vec3(from.name().endsWith("/-1")?-1:1,0,0);
        var source=fixed.steel().mesh().triangles();var frame=fixed.steel().frame();
        for(var part:List.of(from,to))
        {
            var direction=part.frame().transformVector(local);var xyz=part.mesh().triangles();
            for(int v=0;v<xyz.length;v+=3)
            {
                var point=part.frame().transformPoint(new Vec3(xyz[v],xyz[v+1],xyz[v+2]));
                double nearest=Double.POSITIVE_INFINITY,signed=Double.NEGATIVE_INFINITY;
                for(int i=0;i<source.length;i+=9)
                {
                    var a=frame.transformPoint(new Vec3(source[i],source[i+1],source[i+2]));
                    var b=frame.transformPoint(new Vec3(source[i+3],source[i+4],source[i+5]));
                    var c=frame.transformPoint(new Vec3(source[i+6],source[i+7],source[i+8]));
                    var normal=b.subtract(a).cross(c.subtract(a));if(normal.lengthSqr()<1e-20)continue;
                    normal=normal.normalize();if(Math.abs(normal.dot(direction))<.95)continue;
                    if(normal.dot(direction)<0)normal=normal.scale(-1);
                    double d=NervShoulderBearingR52.triangleDistanceR52(point,a,b,c);
                    if(d<nearest){nearest=d;signed=point.subtract(a).dot(normal);}
                }
                if(signed<-.0002+deviation)return finiteRailHeadContact(from,to,fixed,deviation);
            }
        }
        return true;
    }

    /** A finite rail end is not the infinite extension of its bearing plane.
     * Prove separation of the complete swept pad from every closed head cell,
     * with the same inward allowance after subtracting the curve error. */
    private static boolean finiteRailHeadContact(NervLegacyCarrierRideR52.Piece from,
            NervLegacyCarrierRideR52.Piece to,Fixed fixed,double deviation)
    {
        // Both authored rail families have finite closed ends. The caller has
        // already matched the exact leg, mount and bearing role; the complete
        // swept pad still needs a separating certificate for every head cell.
        if(!fixed.name().startsWith("transfer/")&&!fixed.name().startsWith("upright_rail/"))return false;
        var pads=contactCells(from.mesh());var heads=contactCells(fixed.steel().mesh());
        if(pads.size()!=1||heads.isEmpty())return false;
        var moving=new ArrayList<Vec3>();var axes=new ArrayList<Vec3>();
        for(var pose:List.of(from.frame(),to.frame()))
        {
            for(var point:pads.get(0).vertices())moving.add(pose.transformPoint(point));
            for(var normal:pads.get(0).normals())axes.add(pose.transformVector(normal).normalize());
        }
        var frame=fixed.steel().frame();double allowance=.0002-deviation;
        for(var cell:heads)
        {
            var steel=cell.vertices().stream().map(frame::transformPoint).toList();
            boolean separated=false;
            for(var axis:axes)if(separatedContact(moving,steel,axis,allowance)){separated=true;break;}
            if(!separated)for(var normal:cell.normals())
                if(separatedContact(moving,steel,frame.transformVector(normal).normalize(),allowance))
                {separated=true;break;}
            // Each tested axis is a sufficient separating certificate. Missing
            // cross-edge axes can only reject a contact, never admit intrusion.
            if(!separated)return false;
        }
        return true;
    }

    private static boolean separatedContact(List<Vec3> moving,List<Vec3> steel,Vec3 axis,double allowance)
    {
        var origin=steel.get(0);double low=Double.POSITIVE_INFINITY,high=Double.NEGATIVE_INFINITY;
        double railLow=low,railHigh=high;
        for(var point:moving){double value=point.subtract(origin).dot(axis);low=Math.min(low,value);high=Math.max(high,value);}
        for(var point:steel){double value=point.subtract(origin).dot(axis);railLow=Math.min(railLow,value);railHigh=Math.max(railHigh,value);}
        return Math.min(high-railLow,railHigh-low)<=allowance;
    }

    private static synchronized List<ContactCell> contactCells(NervRigidMeshSweepR52 mesh)
    {
        var cached=CONTACT_CELLS.get(mesh);if(cached!=null)return cached;
        var cells=new ArrayList<ContactCell>();var xyz=mesh.triangles();
        if(xyz.length%108!=0){CONTACT_CELLS.put(mesh,List.of());return List.of();}
        for(int start=0;start<xyz.length;start+=108)
        {
            var points=new ArrayList<Vec3>();var unique=new LinkedHashSet<Vec3>();
            for(int i=start;i<start+108;i+=3){var p=new Vec3(xyz[i],xyz[i+1],xyz[i+2]);points.add(p);unique.add(p);}
            if(unique.size()!=8){CONTACT_CELLS.put(mesh,List.of());return List.of();}
            var centre=Vec3.ZERO;for(var point:unique)centre=centre.add(point.scale(1D/8));
            var normals=new ArrayList<Vec3>();var edges=new HashMap<Set<Vec3>,Integer>();boolean valid=true;
            for(int i=0;i<points.size();i+=3)
            {
                var a=points.get(i);var b=points.get(i+1);var c=points.get(i+2);
                var normal=b.subtract(a).cross(c.subtract(a));if(normal.lengthSqr()<1e-20){valid=false;break;}
                normal=normal.normalize();if(normal.dot(a.subtract(centre))<0)normal=normal.scale(-1);
                for(var point:unique)if(point.subtract(a).dot(normal)>1e-8){valid=false;break;}
                if(!valid)break;
                normals.add(normal);
                edges.merge(Set.of(a,b),1,Integer::sum);edges.merge(Set.of(b,c),1,Integer::sum);edges.merge(Set.of(c,a),1,Integer::sum);
            }
            if(!valid||edges.values().stream().anyMatch(count->count!=2))
            {CONTACT_CELLS.put(mesh,List.of());return List.of();}
            cells.add(new ContactCell(List.copyOf(unique),List.copyOf(normals)));
        }
        var result=List.copyOf(cells);CONTACT_CELLS.put(mesh,result);return result;
    }

    private static double distance(Vec3 point,double[] values,RigidTransform frame)
    {
        double nearest=Double.POSITIVE_INFINITY;
        for(int i=0;i<values.length;i+=9)
        {
            var a=frame.transformPoint(new Vec3(values[i],values[i+1],values[i+2]));
            var b=frame.transformPoint(new Vec3(values[i+3],values[i+4],values[i+5]));
            var c=frame.transformPoint(new Vec3(values[i+6],values[i+7],values[i+8]));
            nearest=Math.min(nearest,NervShoulderBearingR52.triangleDistanceR52(point,a,b,c));
        }
        return nearest;
    }

    public static synchronized Hardware selected()
    {
        if(checked)return selected;
        try(var stream=CarrierRearGuideR53.class.getResourceAsStream("/assets/projectseele/"+SELECTION))
        {
            if(stream!=null)
            {
                byte[] bytes=stream.readAllBytes();var document=json(bytes);
                require(document.get("schema").getAsString().equals("projectseele.r53.rear-guide-selection.v1"),"Rear guide selection schema");
                var hashes=document.getAsJsonObject("resources");
                byte[] hardware=EvaOriginalMeshGeometryR52.classpathBytes(HARDWARE);
                require(sha(hardware).equals(hashes.get(HARDWARE).getAsString()),"Rear hardware bytes changed");
                selected=readHardware(hardware,sha(bytes));manifest=document;
                require(CarrierAssemblyR53.selected()!=null,"Rear guide requires its measured supplied carrier");
                require(CarrierAssemblyR53.retainsSourceSurface(json(hardware).get("carrier_sha256").getAsString()),"Rear guide source carrier changed");
                for(var source:json(hardware).getAsJsonObject("source_hardware_sha256").entrySet())
                    require(sha(EvaOriginalMeshGeometryR52.classpathBytes(source.getKey())).equals(source.getValue().getAsString()),"Rear guide bearing source changed: "+source.getKey());
                require(json(hardware).get("transfer_stow_lift_m").getAsDouble()==STOW_LIFT&&liftBearings(selected),
                    "Rear transfer lift lacks its four finite sliding bearings");
            }
            checked=true;return selected;
        }
        catch(IOException failure){throw new IllegalStateException("Selected rear guide source unavailable",failure);}
    }

    public static Hardware readHardware(byte[] bytes,String fingerprint)
    {
        var source=json(bytes);
        require(source.get("schema").getAsString().equals("projectseele.r53.rear-guide-hardware.v1"),"Rear guide hardware schema");
        require(source.get("head_slide").getAsDouble()==NervBankHeadTransferR53.RETRACT,"Original bounded head slide required");
        var mounts=new ArrayList<Mount>();var names=new HashSet<String>();
        for(var raw:source.getAsJsonArray("mounts"))
        {
            var m=raw.getAsJsonObject();String name=m.get("id").getAsString();require(names.add(name),"Unique rear mounts required");
            mounts.add(new Mount(name,point(m.getAsJsonArray("ball"))));
        }
        require(mounts.size()==2||mounts.size()==4,"Measured paired rear attachment facets required");
        names.add("ROOT");names.add("LIFT");var parts=new ArrayList<Template>();var partNames=new HashSet<String>();
        for(var raw:source.getAsJsonArray("parts"))
        {
            var p=raw.getAsJsonObject();String name="rear/"+p.get("name").getAsString(),frame=p.get("frame").getAsString();
            require(names.contains(frame)&&partNames.add(name),"Unique declared rear part frame required");
            var a=p.getAsJsonArray("triangles_rgb");require(!a.isEmpty()&&a.size()%18==0,"Complete rear triangles required");
            double[] rgb=new double[a.size()],xyz=new double[a.size()/2];
            for(int i=0,k=0;i<a.size();i+=6)
            {
                for(int j=0;j<6;j++){rgb[i+j]=a.get(i+j).getAsDouble();require(Double.isFinite(rgb[i+j]),"Finite rear vertices required");}
                xyz[k++]=rgb[i];xyz[k++]=rgb[i+1];xyz[k++]=rgb[i+2];
            }
            parts.add(new Template(name,frame,p.get("role").getAsString(),new NervRigidMeshSweepR52(xyz),rgb));
        }
        return new Hardware(List.copyOf(mounts),List.copyOf(parts),fingerprint);
    }

    private static Vec3 point(JsonArray a)
    {require(a.size()==3,"Three coordinates required");var p=new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());require(Double.isFinite(p.lengthSqr()),"Finite point required");return p;}
    private static JsonObject json(byte[] bytes)
    {return JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject();}
    private static String sha(byte[] bytes)
    {try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}catch(NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}}
    private static void require(boolean condition,String message)
    {if(!condition)throw new IllegalArgumentException(message);}
    public static double bankLift(net.minecraft.nbt.CompoundTag state,double clock)
    {
        boolean toTransfer=state.getBoolean("RearToTransferR53");
        double t=Math.max(0,Math.min(1,toTransfer?(clock-90)/30:clock/30));
        double eased=t*t*t*(10+t*(-15+6*t));return STOW_LIFT*(toTransfer?eased:1-eased);
    }
    public static double actualLift(com.projectseele.entity.NervCarrierPlatformEntity carrier,float partial)
    {
        var state=carrier.originalCarrierReadStateR53();var head=state.getCompound(NervBankHeadTransferR53.KEY);
        if(!head.contains("RearLegR53"))return STOW_LIFT;
        double clock=head.getInt("Clock");
        if(carrier.level().isClientSide&&head.getLong("At")==state.getLong("At"))
        {
            double blend=carrier.mechanicalVisualFractionR54("carrier",head.getLong("At"),partial);
            int previous=head.contains("PreviousClock")?head.getInt("PreviousClock"):Math.max(0,(int)clock-1);
            clock=previous+blend*(clock-previous);
        }
        return bankLift(head,clock);
    }
    public static boolean liftBearings(Hardware hardware)
    {
        for(var mount:hardware.mounts())
        {
            String prefix="rear/"+mount.name()+"/";
            var rod=hardware.parts().stream().filter(p->p.name().equals(prefix+"lift_rod")&&p.frame().equals("LIFT")).findFirst().orElse(null);
            if(rod==null)return false;var r=rod.mesh().bounds();
            var sleeves=hardware.parts().stream().filter(p->p.name().startsWith(prefix+"lift_sleeve/")&&p.frame().equals("ROOT")).toList();
            if(sleeves.size()!=4)return false;
            for(int side=0;side<4;side++)
            {
                final int index=side;var s=sleeves.stream().filter(p->p.name().endsWith("/"+index)).findFirst().orElseThrow().mesh().bounds();
                double plane=switch(side){case 0->Math.abs(s.minX-r.maxX);case 1->Math.abs(s.maxX-r.minX);case 2->Math.abs(s.minZ-r.maxZ);default->Math.abs(s.maxZ-r.minZ);};
                double width=side<2?Math.min(s.maxZ,r.maxZ)-Math.max(s.minZ,r.minZ):Math.min(s.maxX,r.maxX)-Math.max(s.minX,r.minX);
                if(plane>1e-7||width<=.02)return false;
                // Overlap of two intervals under translation is concave: its
                // minimum on the entire stroke occurs at an endpoint.
                for(double lift:new double[]{0,STOW_LIFT})
                    if((Math.min(s.maxY,r.maxY+lift)-Math.max(s.minY,r.minY+lift))*width<.01)return false;
            }
        }
        return true;
    }
    private CarrierRearGuideR53(){}
}

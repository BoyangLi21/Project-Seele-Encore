from pathlib import Path
import hashlib,difflib,json
R=Path('D:/eva');O=R/'artifacts/rebuild_r45/lifts_doors_lifecycle_sol_v2/command17_first_contact_material_capture_v1';O.mkdir(exist_ok=False)
p=R/'src/main/java/com/projectseele/client/visual/CommandDoorInteractionReviewR45.java';s=p.read_text('utf8');t=s
needle='    private static void captureOriginal(ServerPlayer p)throws Exception'
method='''    private static void captureRegisteredCabinMaterials() throws Exception
    {
        var proof=new JsonObject();proof.addProperty("schema","projectseele.tv-cabin-registered-state-capture.r45.v1");
        proof.addProperty("captured_at_utc",java.time.Instant.now().toString());proof.addProperty("world_written",false);proof.addProperty("world_chunks_read_or_loaded",false);
        proof.addProperty("native_registry_and_geometry_executed",true);proof.addProperty("visual_or_user_approved",false);
        proof.addProperty("candidate_binding_sha256",job.get("candidate_binding_sha256").getAsString());proof.addProperty("world_id",job.get("world_id").getAsString());
        var states=new JsonArray();
        for(String name:List.of("tv_staff_lift_panel_r45","tv_staff_lift_band_r45","tv_utility_lift_ceiling_r45"))
        {
            var id=new net.minecraft.resources.ResourceLocation("projectseele",name);require(BuiltInRegistries.BLOCK.containsKey(id),"Actual cabin material not registered: "+id);
            var state=BuiltInRegistries.BLOCK.get(id).defaultBlockState();var row=new JsonObject();row.addProperty("state",BlockStateParser.serialize(state));
            row.addProperty("registered",true);row.addProperty("java_class",state.getBlock().getClass().getName());row.addProperty("state_count",state.getBlock().getStateDefinition().getPossibleStates().size());
            row.addProperty("has_block_entity",state.hasBlockEntity());row.addProperty("entity_block_factory",state.getBlock() instanceof net.minecraft.world.level.block.EntityBlock);
            var collision=state.getCollisionShape(EmptyBlockGetter.INSTANCE,BlockPos.ZERO,CollisionContext.empty());var outline=state.getShape(EmptyBlockGetter.INSTANCE,BlockPos.ZERO,CollisionContext.empty());
            row.add("native_collision_aabbs",GSON.toJsonTree(collision.toAabbs().stream().map(b->List.of(b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ)).toList()));
            row.add("native_outline_aabbs",GSON.toJsonTree(outline.toAabbs().stream().map(b->List.of(b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ)).toList()));
            row.addProperty("native_context","EmptyBlockGetter.INSTANCE / BlockPos.ZERO / CollisionContext.empty");states.add(row);
        }
        proof.add("states",states);var classes=new JsonObject();
        for(String resource:List.of("/com/projectseele/registry/ModBlocks.class","/com/projectseele/registry/ModItems.class","/com/projectseele/world/TvLiftFinishR45.class","/com/projectseele/world/S20MovingElevatorsAdapter.class","/com/projectseele/client/visual/CommandDoorInteractionReviewR45.class"))
        {
            try(var input=CommandDoorInteractionReviewR45.class.getResourceAsStream(resource))
            {require(input!=null,"Actual cabin source resource missing: "+resource);classes.addProperty(resource,HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(input.readAllBytes())));}
        }
        proof.add("actual_loaded_class_SHA256",classes);Files.writeString(output.getParent().resolve("cabin_registered_materials.native.json"),GSON.toJson(proof),StandardOpenOption.CREATE_NEW);
    }

'''
assert t.count(needle)==1;t=t.replace(needle,method+needle)
a='Files.createDirectories(output.getParent());\n    }\n    private static void captureRegisteredCabinMaterials()';b='Files.createDirectories(output.getParent());if(firstContact)captureRegisteredCabinMaterials();\n    }\n    private static void captureRegisteredCabinMaterials()';assert t.count(a)==1;t=t.replace(a,b)
(O/'CommandDoorInteractionReviewR45.before.txt').write_bytes(p.read_bytes());(O/'CommandDoorInteractionReviewR45.candidate.txt').write_text(t,encoding='utf8');rel=p.relative_to(R).as_posix();patch=''.join(difflib.unified_diff(s.splitlines(True),t.splitlines(True),fromfile='a/'+rel,tofile='b/'+rel));(O/'root_C17_capture_registered_materials.patch').write_text(patch,encoding='utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();(O/'FROZEN.json').write_text(json.dumps({'Root_558_sources_and17_resources_actual_compiled216':True,'world558_installed':False,'patch_SHA256':sha(O/'root_C17_capture_registered_materials.patch'),'before_source_SHA256':sha(p),'candidate_SHA256':sha(O/'CommandDoorInteractionReviewR45.candidate.txt'),'first_contact_only':True,'world_written_or_new_MC_by_child':False},indent=2)+'\n',encoding='utf8');print(O)

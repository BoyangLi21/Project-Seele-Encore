// Reuse the pinned MIT Mesh2Motion boundary and extremity solvers locally.
// Geometry, UVs and the supplied model silhouette are not modified.
import fs from 'node:fs';
import path from 'node:path';
import {Bone,BufferGeometry,Float32BufferAttribute} from '../artifacts/rebuild_r48/tooling/rig-runtime/node_modules/three/build/three.module.js';
import {WeightSmoother} from '../artifacts/rebuild_r48/tooling/rig-runtime/compiled/solvers/WeightSmoother.js';
import {WeightNormalizer} from '../artifacts/rebuild_r48/tooling/rig-runtime/compiled/solvers/WeightNormalizer.js';
import {ExtremityWeightCorrector} from '../artifacts/rebuild_r48/tooling/rig-runtime/compiled/solvers/ExtremityWeightCorrector.js';
import {ArmWeightCorrector} from '../artifacts/rebuild_r48/tooling/rig-runtime/compiled/solvers/ArmWeightCorrector.js';
const root=path.resolve(import.meta.dirname,'..');
for(const name of ['un00','un01']){
  const directory=path.join(root,'artifacts/rebuild_r48/tripo_pipeline',name,'rig_candidate');
  const d=JSON.parse(fs.readFileSync(path.join(directory,'initial_skin.json'),'utf8'));
  const map=new Map(d.bones.map(b=>[b.name,new Bone()]));
  const specs=new Map(d.bones.map(b=>[b.name,b]));
  for(const spec of d.bones){
    const bone=map.get(spec.name);bone.name=spec.name;
    const parent=spec.parent?specs.get(spec.parent):null;
    bone.position.set(...spec.pivot.map((x,i)=>x-(parent?.pivot[i]??0)));
    if(parent)map.get(parent.name).add(bone);
  }
  const bones=d.bones.map(s=>map.get(s.name));
  for(const segment of d.segments){
    const parent=map.get(segment.bone);if(parent.children.length)continue;
    const leaf=new Bone();leaf.name=segment.bone+'_End';
    leaf.position.set(...segment.end.map((x,i)=>x-segment.start[i]));parent.add(leaf);bones.push(leaf);
  }
  map.get('root').updateMatrixWorld(true);
  const geometry=new BufferGeometry();geometry.setAttribute('position',new Float32BufferAttribute(d.vertices.flat(),3));geometry.setIndex(d.triangles.flat());
  const indices=d.skin_indices,weights=d.skin_weights;
  new ExtremityWeightCorrector(geometry,bones).apply_extremity_weight_correction(indices,weights);
  new ArmWeightCorrector(geometry,bones,-.016).apply_arm_weight_correction(indices,weights);
  new WeightSmoother(geometry,bones).smooth_bone_weight_boundaries(indices,weights);
  new WeightNormalizer(geometry).normalize_weights(weights);
  let invalid=0;
  for(let i=0;i<weights.length;i+=4){
    const sum=weights.slice(i,i+4).reduce((a,b)=>a+b,0);
    if(!Number.isFinite(sum)||Math.abs(sum-1)>1e-5)invalid++;
  }
  if(invalid)throw Error(`${name}: ${invalid} invalid weight sums`);
  fs.writeFileSync(path.join(directory,'smoothed_skin.json'),JSON.stringify({
    upstream:'https://github.com/Mesh2Motion/mesh2motion-app',commit:'79f3f61a9852ef70234a5a4a7c13ed87f7a71833',license:'MIT',
    method:'Measured segment initial assignment; upstream extremity/arm correction, adjacency smoothing and normalization',
    bones:bones.map(b=>b.name),skin_indices:indices,skin_weights:weights,geometry_changed:false,game_integrated:false,visual_review_pending:true
  }));
  console.log(name,`${d.vertices.length} vertices skinned; visual review remains required.`);
}

"""Actual saved state/native AABB diagrams; no world edits, no model rendering."""
from pathlib import Path
import argparse,collections,gzip,hashlib,json,sys
sys.dont_write_bytecode=True
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rebuild_r45/pyramid_components_sol_v1/middle_lift_waiting_component_v1';OUT=BASE/'actual_blocks_isometric_v1'
WORLD=ROOT/'artifacts/rebuild_r45/composition_candidates/R45_source_candidate_20261003_v4_01/world'
def rows(p):
    with gzip.open(p,'rt',encoding='utf8')as f:return [json.loads(x)for x in f if x.strip()]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    global BASE,OUT
    p=argparse.ArgumentParser();p.add_argument('--enclosed',action='store_true');args=p.parse_args()
    if args.enclosed:BASE=ROOT/'artifacts/rebuild_r45/pyramid_components_sol_v1/middle_lift_waiting_enclosed_v2';OUT=BASE/'actual_blocks_isometric_v1'
    assert not OUT.exists();OUT.mkdir()
    original={tuple(r['pos']):r['state']for r in rows(BASE/'whole_component_before_state_NBT.jsonl.gz')};candidate=dict(original);delta=rows(BASE/'forward.jsonl.gz');changed={tuple(r['pos'])for r in delta}
    for r in delta:assert original[tuple(r['pos'])]==r['before'];candidate[tuple(r['pos'])]=r['after']
    shapes=json.loads((WORLD/'native_collision_shapes.json').read_text('utf8'))
    colors={'projectseele:nerv_floor_panel':'#718086','projectseele:nerv_structural_panel':'#424d54','projectseele:nerv_wall_panel':'#bbc3c6','projectseele:clear_glass':'#78bdd1','projectseele:nerv_edge_rail':'#f2b954','minecraft:polished_deepslate':'#536268'}
    index=[];unknown=set()
    for cut in (False,True):
        fig=plt.figure(figsize=(17,7.5),facecolor='#f5f6f8')
        for i,(label,image)in enumerate([('BEFORE: whole tall south end',original),('AFTER: enclosed industrial window'if args.enclosed else'AFTER: supported waiting overlook',candidate)],1):
            ax=fig.add_subplot(1,2,i,projection='3d',computed_zorder=False);ax.set_facecolor('#f5f6f8');faces=[];facecolors=[]
            for q,state in sorted(image.items(),key=lambda item:(item[0][1],item[0][2],item[0][0])):
                if cut and q[1]>=-389:continue
                name=state.split('[',1)[0]
                if name in {'minecraft:air','minecraft:cave_air','minecraft:light'}:continue
                boxes=shapes.get(state)
                if boxes is None:unknown.add(state);continue
                color=matplotlib.colors.to_rgba(colors.get(name,'#8f9a91'),.22 if name=='projectseele:clear_glass' else 1.)
                for b in boxes:
                    x,y,z=q;lo=(x+b[0],z+b[2],y+b[1]);hi=(x+b[3],z+b[5],y+b[4])
                    verts=[(X,Z,Y)for X in (lo[0],hi[0])for Z in (lo[1],hi[1])for Y in (lo[2],hi[2])]
                    # Six native collision faces, including shaped rails/stairs.
                    for face in [(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]:faces.append([verts[k]for k in face]);facecolors.append(color)
            collection=Poly3DCollection(faces,facecolors=facecolors,edgecolors=(.1,.16,.2,.1),linewidths=.12,zsort='average');ax.add_collection3d(collection)
            ax.set_xlim(88,115);ax.set_ylim(-51,-40);ax.set_zlim(-397,-386);ax.set_box_aspect((27,11,11));ax.set_proj_type('ortho');ax.view_init(elev=23 if cut else 14,azim=60)
            ax.set_title(label,fontsize=15,pad=12);ax.set_xlabel('World X');ax.set_ylabel('World Z');ax.set_zlabel('World Y')
            ax.set_xticks([90,95,105,113]);ax.set_yticks([-49,-45,-42]);ax.set_zticks([-396,-394,-391,-388]);ax.grid(False)
            ax.text(105.5,-41.85,-390.6,'105,-391,-42',fontsize=9,color='#aa3c32')
            if i==2:ax.text(102.5,-42.5,-393.6,'Retracted Z=-43 closed window'if args.enclosed else'23 supported rail cells',fontsize=9,color='#7f5313')
        suffix='roof_cutaway'if cut else'whole_component';fig.suptitle('Same saved coordinates and native collision shapes | '+str(len(delta))+'-cell candidate',fontsize=17,y=.98)
        footer='CUTAWAY: BOTH views omit Y >= -389; same clipping plane. 'if cut else'Whole sampled component, including its roof and bearing. '
        fig.text(.5,.035,footer+'Glass is translucent only for this diagram. Colors are schematic; not a game screenshot or visual acceptance.',ha='center',fontsize=10)
        fig.subplots_adjust(left=.025,right=.975,bottom=.10,top=.90,wspace=.015);p=OUT/(suffix+'_before_after.png');fig.savefig(p,dpi=150);plt.close(fig);index.append(dict(path=str(p),sha256=digest(p),cutaway_Y_ge=-389 if cut else None))
    assert not unknown,('Unknown actual shape cannot be rendered as cube',unknown)
    (OUT/'render_provenance.json').write_bytes((json.dumps(dict(source_preimage=str(BASE/'whole_component_before_state_NBT.jsonl.gz'),source_sha256=digest(BASE/'whole_component_before_state_NBT.jsonl.gz'),forward_sha256=digest(BASE/'forward.jsonl.gz'),native_shapes_sha256=digest(WORLD/'native_collision_shapes.json'),images=index,unknown_states=[],world_written=False,model_changed=False,game_screenshot=False,visual_acceptance=False),indent=2)+'\n').encode('utf8'))
    print('Rendered exact saved block/native AABB before-after diagrams; no world or model writes.',flush=True)
if __name__=='__main__':main()

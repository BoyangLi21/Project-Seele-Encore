"""Continuous adjacent-joint locality comparison; immutable source geometry and no installation."""
from pathlib import Path
import argparse,copy,hashlib,json
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
def smooth(x):
    x=np.clip(x,0,1);return x*x*(3-2*x)

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--source',type=Path,default=ROOT/'run/resourcepacks/eva_real_model/assets/projectseele/mesh/sachiel.mesh.json');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    source=a.source.resolve()
    mesh=json.loads(source.read_text());before=copy.deepcopy(mesh['skin']);bones=mesh['skin']['bones'];lookup={n:i for i,n in enumerate(bones)}
    geo=json.loads((ROOT/'run/resourcepacks/eva_real_model/assets/projectseele/geo/sachiel.geo.json').read_text())
    hierarchy={b['name']:b.get('parent') for b in geo['minecraft:geometry'][0]['bones']};edges=[]
    for name in bones:
        ancestor=hierarchy.get(name)
        while ancestor is not None and ancestor not in lookup:ancestor=hierarchy.get(ancestor)
        if ancestor is not None:edges.append((lookup[ancestor],lookup[name]))
    ids=np.array(before['indices']).reshape(-1,4);weights=np.array(before['weights']).reshape(-1,4);dense=np.zeros((len(ids),len(bones)))
    for slot in range(4):np.add.at(dense,(np.arange(len(ids)),ids[:,slot]),weights[:,slot])
    pair=np.column_stack([dense[:,i]+dense[:,j]for i,j in edges]);order=np.argsort(pair,axis=1);winner=order[:,-1];mass=pair[np.arange(len(ids)),winner];second=pair[np.arange(len(ids)),order[:,-2]]
    amount=smooth((mass-.60)/.20)*smooth((mass-second)/.25)
    changed=[]
    for vertex in range(len(ids)):
        group=edges[winner[vertex]];remote=1-mass[vertex]
        if amount[vertex]<1e-8 or remote<1e-8:continue
        result=dense[vertex]*(1-amount[vertex]);result[list(group)]+=amount[vertex]*dense[vertex,list(group)]/mass[vertex]
        active=[(i,float(w))for i,w in enumerate(result)if w>1e-10];active.sort(key=lambda x:(-x[1],x[0]));assert len(active)<=4
        bi=[i for i,w in active];bw=[round(w,7)for i,w in active];bw[0]=round(bw[0]+1-sum(bw),7)
        while len(bi)<4:bi.append(bi[0]);bw.append(0.)
        if bi==ids[vertex].tolist() and bw==weights[vertex].tolist():continue
        changed.append(dict(vertex=vertex,adjacent_pair=[bones[i]for i in group],amount=float(amount[vertex]),old_ids=ids[vertex].tolist(),old_weights=weights[vertex].tolist(),new_ids=bi,new_weights=bw))
        ids[vertex]=bi;weights[vertex]=bw
    mesh['skin']['indices']=ids.ravel().tolist();mesh['skin']['weights']=weights.ravel().tolist()
    mesh['skin']['locality_candidate_r45']='PRIVATE_UNAPPROVED: continuous pair mass and pair dominance, immutable vertex geometry'
    target=a.out/'overlay/assets/projectseele/mesh/sachiel.mesh.json';target.parent.mkdir(parents=True);target.write_text(json.dumps(mesh,separators=(',',':')))
    report=dict(source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),candidate_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),geometry_unchanged=True,palette_unchanged=True,changes=changed,
                method='Retain local adjacent-joint ratio, smoothly suppress remote residual only for a dominant adjacent pair; influence vanishes continuously at a pair tie. Canonical positive order and same-owner zero padding. Not automatic anatomical approval.',promoted=False,native_executed=False)
    (a.out/'receipt.json').write_text(json.dumps(report,indent=2));print('Changed',len(changed),'expanded vertices; geometry preserved')

if __name__=='__main__':main()

"""Constrain future outer terrain with actual saved ground and water.

Core and commissioned repairs stay exact. Only unsaved exterior gaps gain a
native-noise blend. Both resources use the original bounded two-block grid.
"""
import argparse, gzip, json, struct
from pathlib import Path
import numpy as np
from scipy.ndimage import distance_transform_edt, gaussian_filter, binary_dilation
from map_pipeline.outer_water_banks import CORE


def smooth(value):
    t=np.clip(value,0,1)
    return t*t*(3-2*t)


def exterior(x,z,native):
    coast=np.maximum(np.maximum(0,x-4386.),np.maximum(0,z-3720.))
    inland=np.maximum(np.maximum(0,-1982.-x),np.maximum(0,-1548.-z))
    offset=np.where(coast==0,0,np.where(inland==0,1,smooth((coast/np.maximum(1,coast+inland)-.5)*4)))
    height=np.maximum(-120,native-144*offset)
    crest=74+np.maximum(0,native-70)*.2
    bank=np.where(offset<=.35,native+(crest-native)*smooth(offset/.35),
        crest+(np.maximum(-120,native-144)-crest)*smooth((offset-.35)/.65))
    height=np.where((offset>0)&(offset<1),np.maximum(height,bank),height)
    return np.floor(height+.5),np.where(offset<.35,62,-82)


def combine(x,z,fixed,water,weight,native):
    native_h,native_water=exterior(x,z,native)
    height=fixed*(1-weight)+native_h*weight
    crest=np.maximum(water,native_water)+2
    bank=np.where(weight<=.5,fixed+(crest-fixed)*smooth(weight*2),
        crest+(native_h-crest)*smooth(weight*2-1))
    height=np.where((water!=native_water)&(weight>0),np.maximum(height,bank),height)
    ground=np.floor(height+.5).astype(np.int16)
    level=np.where(weight<.5,water,native_water)
    return ground,np.where((weight==0)|(ground<level),level,-32768).astype(np.int16)


def read_field(path):
    raw=gzip.decompress(path.read_bytes())
    header=struct.unpack('>6i',raw[:24]);magic,x,z,step,w,d=header
    if magic!=0x484B3535 or len(raw)!=24+w*d*4:raise ValueError('Unexpected surface format')
    return header,np.frombuffer(raw[24:24+w*d*2],'>i2').reshape(d,w).copy(),np.frombuffer(raw[24+w*d*2:],'>i2').reshape(d,w).copy()


class Sampler:
    """Offline equivalent of the runtime consumer, used for saved protochunks."""
    def __init__(self,field,blend):
        self.header,h,self.water=read_field(field);self.height=h.astype(np.float64)/16
        raw=gzip.decompress(blend.read_bytes())
        if struct.unpack('>6i',raw[:24])!=(0x484B4231,*self.header[1:]):raise ValueError('Blend grid differs')
        self.blend=np.frombuffer(raw[24:],np.uint8).reshape(h.shape)

    def sample(self,x,z,native):
        _,fx,fz,step,w,d=self.header
        qx=np.clip((x-fx)/step,0,w-1);qz=np.clip((z-fz)/step,0,d-1)
        ix=qx.astype(int);iz=qz.astype(int);jx=np.minimum(ix+1,w-1);jz=np.minimum(iz+1,d-1)
        dx=qx-ix;dz=qz-iz
        def bilinear(a):return (a[iz,ix]*(1-dx)+a[iz,jx]*dx)*(1-dz)+(a[jz,ix]*(1-dx)+a[jz,jx]*dx)*dz
        fixed=bilinear(self.height);weight=bilinear(self.blend)/255
        water=self.water[np.floor(qz+.5).astype(int),np.floor(qx+.5).astype(int)]
        distance=np.maximum.reduce([fx-x,x-(fx+(w-1)*step),fz-z,z-(fz+(d-1)*step)])
        weight=1-(1-weight)*(1-smooth(distance/256))
        return combine(x,z,fixed,water,weight,native)


def bake(a):
    a.out.mkdir(parents=True,exist_ok=False)
    header,original,water=read_field(a.field)
    _,x,z,step,w,d=header
    if a.extend:
        if a.extend%step:raise ValueError('Field extension must align to its sample grid')
        margin=a.extend//step
        original=np.pad(original,margin,mode='edge');water=np.pad(water,margin,mode='edge')
        x-=a.extend;z-=a.extend;w+=2*margin;d+=2*margin
        header=(header[0],x,z,step,w,d)
    if w*d>16000000:raise ValueError('Field exceeds bounded runtime allocation')
    original_water=water.copy()
    xs=x+np.arange(w)*step;zs=z+np.arange(d)*step
    xx,zz=np.meshgrid(xs,zs)
    core=(xx>=CORE[0])&(xx<=CORE[2])&(zz>=CORE[1])&(zz<=CORE[3])
    known=core.copy();height=original.astype(np.float32)/16
    measured=0
    for path in sorted(a.survey.glob('r.*.npz')):
        rx,rz=map(int,path.stem.split('.')[1:])
        ix=np.flatnonzero((xs>=rx*512)&(xs<rx*512+512));iz=np.flatnonzero((zs>=rz*512)&(zs<rz*512+512))
        if not len(ix)or not len(iz):continue
        with np.load(path)as f:
            ground=f['ground'].copy();level=f['water'].copy();full=f['full']
        bank=a.banks/'earthworks'/path.name
        if bank.exists():
            with np.load(bank)as f:
                ground[f['active']]=f['target'][f['active']];level[f['wet']]=62
        src=np.ix_(zs[iz]-rz*512,xs[ix]-rx*512);dst=np.ix_(iz,ix)
        valid=full[src]&~core[dst]&(ground[src]>-129)
        patch=height[dst];patch[valid]=ground[src][valid];height[dst]=patch
        patch=water[dst];patch[valid]=level[src][valid];water[dst]=patch
        patch=known[dst];patch[valid]=True;known[dst]=patch;measured+=int(valid.sum())
    distance,nearest=distance_transform_edt(~known,sampling=step,return_indices=True)
    filled=height[tuple(nearest)]
    water[~known]=water[tuple(nearest)][~known]
    # Relax only unknown exterior values. Unlike row interpolation, the
    # bounded two-dimensional extension cannot create long horizontal flats.
    for _ in range(12):
        smoothed=gaussian_filter(filled,8,mode='nearest')
        filled[~known]=smoothed[~known];filled[known]=height[known]
    t=smooth(distance/256)
    # A dry saved hollow cannot become the edge of an unfinished high lake.
    # Reserve an unbuilt shore before extending any retained Y62 water into
    # that hollow, then place a graded dry divide at the water-mode boundary.
    dry=known&(water!=62)&(height<62)
    dry_distance=distance_transform_edt(~dry,sampling=step)
    water[(~known)&(dry_distance<24)&(water==62)]=-32768
    high=(water==62)&(filled<64)
    low=(water!=62)&(filled<64)
    shore=(binary_dilation(high)&low)|(binary_dilation(low)&high)
    shore&=~known
    if shore.any():
        shore_distance=distance_transform_edt(~shore,sampling=step)
        shore_height=64-shore_distance*.35
        in_bank=(~known)&(shore_height>filled)
        filled[in_bank]=shore_height[in_bank]
        t[~known]*=smooth(shore_distance[~known]/96)
    blend=np.rint(t*255).astype(np.uint8);blend[known]=0
    fixed=np.rint(filled*16).astype('>i2');fixed[core]=original[core]
    from map_pipeline.launch_protection import load
    launch=load(a.world);retained=np.zeros(known.shape,bool)
    for identity,(bx,by,bz,bX,bY,bZ) in launch.boxes:
        if bY < -128 or by > 319:continue
        ix=np.flatnonzero((xs>=bx-step)&(xs<=bX+step));iz=np.flatnonzero((zs>=bz-step)&(zs<=bZ+step))
        if not len(ix)or not len(iz):continue
        s=np.ix_(iz,ix)
        if np.any(blend[s]):raise ValueError('Unconstrained native terrain overlaps a retained launch projection')
        before=original[s]/16;after=fixed[s]/16
        if np.max(np.maximum(before,after))<by or np.min(np.minimum(before,after))-3>bY:continue
        different=(original[s]!=fixed[s])|(original_water[s]!=water[s])
        patch=retained[s];patch|=different;retained[s]=patch
        # Keep every contributing bilinear node for a finite surface/SPACE
        # intersection, including the one-node interpolation margin.
        fixed[s]=original[s];water[s]=original_water[s]
    if not np.array_equal(fixed[core],original[core]):raise ValueError('Core changed')
    payload=struct.pack('>6i',*header)+fixed.tobytes()+water.astype('>i2').tobytes()
    (a.out/'hakone_surface.bin.gz').write_bytes(gzip.compress(payload,compresslevel=6,mtime=0))
    (a.out/'hakone_surface_blend.bin.gz').write_bytes(gzip.compress(struct.pack('>6i',0x484B4231,*header[1:])+blend.tobytes(),compresslevel=6,mtime=0))
    np.savez_compressed(a.out/'boundary-field.npz',x=xs,z=zs,height=fixed.astype(np.float32)/16,water=water,
                        blend=blend,known=known,core=core)
    report=dict(core_samples_retained=int(core.sum()),measured_outer_samples=measured,
        bounds=[int(xs[0]),int(zs[0]),int(xs[-1]),int(zs[-1])],resident_field_bytes=w*d*5,
        native_blend_samples=int((blend>0).sum()),full_native_samples=int((blend==255).sum()),
        restored_outer_water_samples=int(((water==62)&~core).sum()),world_written=False,
        unbuilt_shore_samples=int(shore.sum()),
        retained_launch_surface_samples=int(retained.sum()),
        source_field=str(a.field),source_survey=str(a.survey),bank_candidate=str(a.banks))
    (a.out/'boundary-field.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in ('field','survey','banks','world','out'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--extend',type=int,default=0,help='Include more saved shore context around the old field, in blocks')
    bake(p.parse_args())

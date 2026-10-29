"""Draw saved-world block surfaces after a successful measured installation.

Reconstructs measured source chunks plus read-back installed cells. No planned
roads, buildings or terrain are drawn as if they already existed in the save.
"""
import argparse, json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb


def color(state):
    name = str(state).split(':')[-1].split('[')[0]
    exact = {'water':'#5795af','lcl':'#b99042','grass_block':'#809967','dirt':'#9b8260',
             'sand':'#cfc398','stone':'#9a9d94','smooth_stone':'#bdc0b7',
             'nerv_structural_panel':'#94a69c','iron_block':'#d7ded9','bricks':'#ac8170'}
    if name in exact: return to_rgb(exact[name])
    if 'leaves' in name: return to_rgb('#52794b')
    if 'log' in name or 'wood' in name: return to_rgb('#79664b')
    if 'glass' in name: return to_rgb('#aac4c5')
    if 'rail' in name or 'asphalt' in name: return to_rgb('#505c5a')
    dyes = {'light_gray':'#b7bcb6','light_blue':'#9cc4cd','white':'#dedfd4','gray':'#64716d',
            'black':'#303a38','orange':'#c28b54','red':'#a75e4f','yellow':'#c8b85a',
            'blue':'#657f9b','purple':'#9071a6','green':'#617e4e','lime':'#9caf63'}
    for dye,c in dyes.items():
        if name.startswith(dye+'_'): return to_rgb(c)
    if 'quartz' in name: return to_rgb('#dddcd0')
    if 'stone' in name or 'andesite' in name: return to_rgb('#939d95')
    return to_rgb('#9aa99c')


def render(gis, installation, out, view='city', source_snapshot=None):
    receipt = json.loads(installation.read_text('utf8'))
    if receipt.get('status') != 'installed' or not receipt.get('changed_section_readback'):
        raise ValueError('Map is only delivered after actual installation and changed-cell readback')
    candidates = [Path(c) for c in receipt['candidates']]
    terrain, city = candidates[0], candidates[-1]
    if source_snapshot:
        with np.load(source_snapshot/'blocks.npz')as a:volumes=a['blocks'].copy();palette=list(map(str,a['palette']))
        x0,z0=-352,-128;x1,z1=x0+volumes.shape[2]-1,z0+volumes.shape[1]-1
    else:x0,z0,x1,z1 = json.loads((terrain/'manifest.json').read_text('utf8'))['bounds_xz']
    shape = (z1-z0+1,x1-x0+1)
    rgb = np.zeros((*shape,3), np.float32); heights = np.full(shape,-129,np.int16)
    invisible = {'air','cave_air','void_air','barrier','structure_void','light'}
    if source_snapshot:
        lookup={s:i for i,s in enumerate(palette)}
        for candidate in candidates:
            for patch in sorted((candidate/'delta').glob('*.npz')):
                with np.load(patch)as a:
                    remap=[]
                    for s in map(str,a['palette']):
                        if s not in lookup:lookup[s]=len(palette);palette.append(s)
                        remap.append(lookup[s])
                    remap=np.asarray(remap,np.uint16);points,ranges,indices,after=(a[k]for k in ('coordinates','ranges','indices','after'))
                    for i,(cx,cz)in enumerate(points):
                        l,r=ranges[i:i+2];at=indices[l:r]
                        volumes[at//256,cz*16+(at//16)%16-z0,cx*16+at%16-x0]=remap[after[l:r]]
        visible=np.asarray([s.split(':')[-1].split('[')[0]not in invisible for s in palette]);colors=np.asarray([color(s)for s in palette],np.float32)
        top=volumes.shape[0]-1-np.argmax(visible[volumes[::-1]],axis=0)
        rgb=colors[np.take_along_axis(volumes,top[None,:,:],axis=0)[0]];heights=top-128
        del volumes
    for source in sorted((terrain/'source').glob('*.npz')):
        with np.load(source) as a:
            palette = list(map(str,a['palette'])); lookup = {s:i for i,s in enumerate(palette)}
            coordinates = a['coordinates']; volumes = a['blocks']; row = {tuple(p):i for i,p in enumerate(coordinates)}
        for candidate in candidates:
            patch = candidate/'delta'/source.name
            if not patch.exists(): continue
            with np.load(patch) as a:
                remap = []
                for s in map(str,a['palette']):
                    if s not in lookup: lookup[s]=len(palette); palette.append(s)
                    remap.append(lookup[s])
                remap = np.asarray(remap,np.uint16)
                points,ranges,indices,after = (a[k] for k in ('coordinates','ranges','indices','after'))
                for i,p in enumerate(points):
                    left,right = ranges[i:i+2]
                    volumes[row[tuple(p)]].reshape(-1)[indices[left:right]] = remap[after[left:right]]
        colors = np.asarray([color(s) for s in palette],np.float32)
        visible = np.asarray([s.split(':')[-1].split('[')[0] not in invisible for s in palette])
        for p,volume in zip(coordinates,volumes):
            top = volume.shape[0]-1-np.argmax(visible[volume[::-1]],axis=0)
            ids = np.take_along_axis(volume,top[None,:,:],axis=0)[0]
            x,z = int(p[0])*16-x0,int(p[1])*16-z0
            rgb[z:z+16,x:x+16] = colors[ids]; heights[z:z+16,x:x+16] = top-128
        print('Mapped',source.name,flush=True)
    shade = np.clip(1+.018*(heights-np.roll(heights,1,0))+.012*(heights-np.roll(heights,1,1)),.72,1.15)
    shaded = np.clip(rgb*shade[...,None],0,1)
    out.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(out/'installed-surface.npz',rgb=rgb,heights=heights,bounds=[x0,z0,x1,z1])
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'axes.unicode_minus':False})
    panels=[('main-map',(x0,z0,x1,z1),'已安装地图 · 主城区与山地'),
            ('city-detail',(-352,-128,415,719),'已安装地图 · 十字城区街道')]
    if view=='lake':panels=[('lake-map',(x0,z0,x1,z1),'已安装地图 · 完整芦之湖与周边地形')]
    if source_snapshot:panels=[('city-south-map',(x0,z0,x1,z1),'已安装地图 · 南移后的十字城区与街道')]
    for name,bounds,title in panels:
        fig,ax = plt.subplots(figsize=(14,11),facecolor='#f6f5ef')
        ax.imshow(shaded,extent=(x0,x1+1,z1+1,z0),interpolation='nearest')
        ax.set_xlim(bounds[0],bounds[2]); ax.set_ylim(bounds[3],bounds[1]); ax.set_aspect('equal')
        ax.set_xlabel('游戏 X · 向东'); ax.set_ylabel('游戏 Z · 向南')
        ax.set_title(title+'\nHOTFIX_20261025 · 原方块与已安装差量 · 北朝上',loc='left',fontsize=19,pad=18)
        ax.text(.97,.96,'北 ↑',transform=ax.transAxes,ha='right',fontsize=17,bbox=dict(fc='white',ec='none',alpha=.85))
        labels = [(30,-45,'EVA 发射区'),(30,220,'十字升降城区\n当前为收纳状态'),(322,300,'保留的高架换乘区')]
        if source_snapshot:labels=[(30,-45,'保留的 EVA 发射区'),(30,340,'十字布局中心南移\n机械原点与身份保持'),(-230,140,'迁入的住宅和店铺'),(260,140,'迁入的商住街区'),(322,300,'原高架换乘区'),(-150,390,'首批邻里建筑保留'),(30,686,'南侧街道接入')]
        elif view=='lake':labels=[(-476,880,'原街角商店保留\n已抬高并接回原街道'),(-870,1350,'旧缩尺湖已退役\n恢复真实山地'),(15,1760,'芦之湖\n岸线依据 GSI 水域'),(-150,805,'南部旧街区 · 后续重构')]
        elif name=='main-map': labels += [(-500,250,'西部旧街区 · 待重建'),(-200,-350,'北部旧街区 · 待重建'),(-200,720,'南部旧街区 · 待重建')]
        else: labels += [(-146,61,'重建诊所 / 公园'),(-148,395,'重建住宅 / 商店'),(201,48,'重建诊所 / 书店'),(201,397,'重建住宅 / 咖啡馆')]
        for x,z,text in labels:
            ax.annotate(text,(x,z),xytext=(8,-12),textcoords='offset points',fontsize=10,
                        bbox=dict(boxstyle='round,pad=.3',fc='#fffef5',ec='#9ea99c',alpha=.92))
        caption='实际已写入方块的俯视简化着色；桃源台站、码头和湖岸街景尚未建设。灰黑缺口为未记录区域。' if view=='lake' else '地表最高可见方块的简化着色；地下楼体不展开。外围旧街区、完整湖岸和新铁路仍在施工。'
        fig.text(.08,.025,caption,fontsize=11,color='#52645d')
        fig.subplots_adjust(bottom=.10,top=.89); fig.savefig(out/(name+'.png'),dpi=160); plt.close(fig)
    (out/'provenance.json').write_text(json.dumps(dict(installation=str(installation),world=receipt['world'],
        inputs='measured source + installed arrays with successful changed-section readback',planned_geometry_drawn=False),indent=2),'utf8')
    print(out,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('gis','installation','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--view',choices=('city','lake'),default='city')
    p.add_argument('--source-snapshot',type=Path,help='Measured dense city source captured before this installation')
    a=p.parse_args();render(a.gis,a.installation,a.out,a.view,a.source_snapshot)

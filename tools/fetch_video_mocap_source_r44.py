"""Fetch the creator's CC BY 4 video-derived sample arrays, using ZIP ranges."""
from pathlib import Path
import argparse,hashlib,io,json,urllib.request,zipfile

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r44/combat/tv_exchange/video_source'
ARTICLE='https://api.figshare.com/v2/articles/22680424'


class RemoteZip(io.RawIOBase):
    def __init__(self,url,length):self.url=url;self.length=length;self.position=0
    def seekable(self):return True
    def tell(self):return self.position
    def seek(self,value,whence=0):
        self.position=value if whence==0 else self.position+value if whence==1 else self.length+value;return self.position
    def read(self,count=-1):
        if count<0:count=self.length-self.position
        count=min(count,self.length-self.position)
        if count<=0:return b''
        if count>128*1024*1024:raise ValueError('Only explicit research arrays/scene metadata are fetched')
        request=urllib.request.Request(self.url,headers={'Range':f'bytes={self.position}-{self.position+count-1}'})
        with urllib.request.urlopen(request,timeout=60)as response:
            if response.status!=206:raise ValueError('Server did not honor the exact byte range')
            payload=response.read()
        if len(payload)!=count:raise ValueError('Incomplete archive range')
        self.position+=count;return payload


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--list-only',action='store_true');args=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    metadata=json.load(urllib.request.urlopen(ARTICLE));file=metadata['files'][0];(OUT/'creator_metadata.json').write_text(json.dumps(metadata,indent=2),'utf8')
    with zipfile.ZipFile(RemoteZip(file['download_url'],file['size']))as archive:
        rows=[dict(name=x.filename,bytes=x.file_size,compressed=x.compress_size)for x in archive.infolist()if not x.is_dir()]
        (OUT/'archive_inventory.json').write_text(json.dumps(rows,indent=2),'utf8');print(json.dumps([r for r in rows if r['name'].endswith(('.npy','.blend','.json','.toml','.csv','.bvh','.fbx'))],indent=2),flush=True)
        if args.list_only:return
        names={'mediapipe_body_3d_xyz.npy','mediapipe_left_hand_3d_xyz.npy','mediapipe_right_hand_3d_xyz.npy',
               'total_body_center_of_mass_xyz.npy','segmentCOM_frame_joint_xyz.npy','mediapipe_names_and_connections_dict.json',
               'mediapipe_skeleton_segment_lengths.json'}
        selected=[r for r in rows if Path(r['name']).name in names or r['name'].endswith('_camera_calibration.toml')]
        downloads=[]
        for row in selected:
            target=(OUT/'data'/row['name']).resolve()
            if not target.is_relative_to((OUT/'data').resolve()):raise ValueError('Archive entry escapes research directory')
            target.parent.mkdir(parents=True,exist_ok=True);payload=archive.read(row['name']);target.write_bytes(payload)
            downloads.append(dict(file=str(target),source=row['name'],bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest()));print('Read actual video-mocap array:',row['name'],flush=True)
        (OUT/'download_receipt.json').write_text(json.dumps(dict(article=ARTICLE,license=metadata['license'],authors=metadata['authors'],files=downloads,
            use='Private source comparison/import only. Not a DeepMotion/Move paid job, runtime asset, or quality claim.'),indent=2),'utf8')


if __name__=='__main__':main()

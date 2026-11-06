"""Pin the actual original identity roster and both unchanged base archives."""
import argparse,hashlib,json,uuid
from pathlib import Path
from verify_main_r20 import entities


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);a=p.parse_args()
    base=a.base.resolve();world=base/'WORLD';source=base/'survey/ORIGINAL_ALL_ACTORS.json'
    snapshot=json.loads(source.read_text('utf8'));assert snapshot['count']==len(snapshot['actors'])==678
    original={r['uuid']:dict(type=r['id'],dimension='dimensions/projectseele/geofront') for r in snapshot['actors']}
    assert len(original)==678
    actual={str(uuid.UUID(int=sum((int(v)&0xffffffff)<<(96-32*i) for i,v in enumerate(words)))):
            dict(type=str(tag['id']),dimension='dimensions/projectseele/geofront') for words,tag in entities(world).items()}
    assert all(actual.get(k)==v for k,v in original.items()),'Original full identity set changed'
    doc=dict(world=world.as_posix(),managed_geofront=original,source_roster=source.as_posix(),
             source_roster_sha256=sha(source),world_written=False,original_identity_count=len(original))
    out=base/'delivery_preparation';out.mkdir(exist_ok=True)
    identity_path=out/'ORIGINAL_WORLD_IDENTITIES.json';identity_path.write_text(json.dumps(doc,indent=2),'utf8')
    pins={}
    for key,stem,expected in (
        ('server','Project_SEELE_Encore_R52_NonMapUnified_20261013_Server.zip','52b9df85ffbaf675fbd2d548524bdda7154e523239b992747d229c6669651b33'),
        ('client','Project_SEELE_Encore_R52_NonMapUnified_20261013_Client_PCL.zip','dbe1670763cdc0a9aea3cbfdc8782af72ace887fe7c6e8e42021590b343507c4')):
        archive=base.parents[1]/'delivery'/stem;digest=sha(archive);assert digest==expected
        pins[key]=dict(path=archive.as_posix(),bytes=archive.stat().st_size,sha256=digest)
    pin_path=out/'BASELINE_INPUTS.json';pin_path.write_text(json.dumps(pins,indent=2),'utf8')
    print(json.dumps(dict(originals=len(original),current_entities=len(actual),
                         original_identity_file=str(identity_path),original_identity_sha256=sha(identity_path),
                         baseline_inputs=str(pin_path),baseline_inputs_sha256=sha(pin_path)),indent=2))


if __name__=='__main__':main()

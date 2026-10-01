"""Read the authors' boxing video-motion sample and export data-only arrays.

The joblib archive is not executed as a general pickle: only its numeric NumPy
wrapper/dtype classes are accepted, object arrays and arbitrary globals fail.
This stage is private DCC comparison, never a shipped asset or art acceptance.
"""
from pathlib import Path
import hashlib,io,json,zlib,urllib.request,pickle,struct
import numpy as np
from joblib.numpy_pickle import NumpyUnpickler,NumpyArrayWrapper

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r44/combat/tv_exchange/video_source/boxing'
REPO='https://raw.githubusercontent.com/SMPLOlympics/SMPLOlympics/master/'
URL='https://drive.usercontent.google.com/download?id=1lgzAup2qotweWDMxY9TygbRTea4jUZb0&export=download&confirm=t'


class NumericWrapper(NumpyArrayWrapper):
    def read_array(self,unpickler,ensure_native_byte_order):
        if self.dtype.hasobject:raise ValueError('Object arrays are not numerical motion')
        if int(np.prod(self.shape))>100_000_000:raise ValueError('Unexpected array extent')
        return super().read_array(unpickler,ensure_native_byte_order)


class NumericalUnpickler(NumpyUnpickler):
    def find_class(self,module,name):
        allowed={('joblib.numpy_pickle','NumpyArrayWrapper'):NumericWrapper,
                 ('numpy','ndarray'):np.ndarray,('numpy','dtype'):np.dtype,
                 ('torch.storage','_load_from_bytes'):read_legacy_storage,
                 ('torch._utils','_rebuild_tensor_v2'):rebuild_numeric_tensor,
                 ('collections','OrderedDict'):dict}
        if(module,name)not in allowed:raise ValueError('Non-data pickle global: '+module+'.'+name)
        return allowed[module,name]


def read_legacy_storage(payload):
    """Data-only subset of torch's legacy CPU storage serialization."""
    stream=io.BytesIO(payload);storage=[]
    class StorageUnpickler(pickle.Unpickler):
        def find_class(self,module,name):
            if module=='torch'and name in('FloatStorage','DoubleStorage','LongStorage'):
                return {'FloatStorage':np.dtype('<f4'),'DoubleStorage':np.dtype('<f8'),'LongStorage':np.dtype('<i8')}[name]
            raise ValueError('Unexpected storage global: '+module+'.'+name)
        def persistent_load(self,token):
            kind,dtype,key,device,count,view=token
            if kind!='storage'or device!='cpu'or view is not None:raise ValueError('Unexpected storage descriptor')
            result=dict(dtype=dtype,key=key,count=count);storage.append(result);return result
    for _ in range(3):StorageUnpickler(stream).load()
    value=StorageUnpickler(stream).load();keys=StorageUnpickler(stream).load()
    if len(storage)!=1 or keys!=[storage[0]['key']]:raise ValueError('Unexpected storage keys')
    count=struct.unpack('<q',stream.read(8))[0]
    if count!=storage[0]['count']or count>100_000_000:raise ValueError('Unexpected numeric storage size')
    raw=stream.read();dtype=storage[0]['dtype']
    if len(raw)!=count*dtype.itemsize:raise ValueError('Truncated storage')
    return np.frombuffer(raw,dtype=dtype).copy()


def rebuild_numeric_tensor(storage,offset,size,stride,requires_grad,hooks):
    if not isinstance(storage,np.ndarray)or storage.dtype.hasobject:raise ValueError('Not numeric storage')
    if requires_grad or hooks:raise ValueError('Unexpected tensor execution state')
    if len(size)!=len(stride)or any(x<0 for x in(size+stride)):raise ValueError('Invalid shape/stride')
    extent=offset+sum((n-1)*s for n,s in zip(size,stride))
    if offset<0 or extent>=len(storage):raise ValueError('Out-of-storage tensor')
    return np.lib.stride_tricks.as_strided(storage[offset:],shape=size,strides=tuple(x*storage.itemsize for x in stride),writeable=False).copy()


def main():
    OUT.mkdir(parents=True,exist_ok=True);source=OUT/'video_boxing_afterproc_upright.pkl'
    if not source.exists():source.write_bytes(urllib.request.urlopen(URL,timeout=45).read())
    raw=zlib.decompress(source.read_bytes())
    motion=NumericalUnpickler(str(source),io.BytesIO(raw),True).load()
    inventory=[]
    for name,row in motion.items():
        record=dict(name=name,fields={});arrays={}
        for key,value in row.items():
            if isinstance(value,np.ndarray):
                if value.dtype.hasobject:raise ValueError('Object array')
                record['fields'][key]=dict(shape=list(value.shape),dtype=str(value.dtype),finite=float(np.isfinite(value).mean()))
                arrays[key]=value
            else:
                if not isinstance(value,(str,float,int,list,tuple,type(None))):raise ValueError('Unexpected metadata type')
                record['fields'][key]=value;arrays[key]=np.asarray(value)
        np.savez_compressed(OUT/(name+'.npz'),**arrays);inventory.append(record)
    for filename in ('LICENSE','README.MD','download_data.sh','phc/data/assets/mjcf/smpl_humanoid_neutral_boxing.xml','poselib/poselib/skeleton/skeleton3d.py'):
        target=OUT/Path(filename).name
        if not target.exists():target.write_bytes(urllib.request.urlopen(REPO+filename,timeout=45).read())
    (OUT/'motion_inventory.json').write_text(json.dumps(inventory,indent=2),'utf8')
    (OUT/'source_receipt.json').write_text(json.dumps(dict(
        official_repository='https://github.com/SMPLOlympics/SMPLOlympics',
        official_selection=REPO+'download_data.sh',source_url=URL,bytes=source.stat().st_size,
        sha256=hashlib.sha256(source.read_bytes()).hexdigest(),motion_count=len(motion),
        method='Author-published Boxing video estimate after PHC physical refinement. Not CMU optical mocap or a Move/DeepMotion paid job.',
        scope='Private source comparison. Full hand/finger capture, physical force, and artistic quality are not inferred.'),indent=2),'utf8')
    print(json.dumps(inventory[:3],indent=2));print('Actual numeric video-combat motions:',len(motion))


if __name__=='__main__':main()

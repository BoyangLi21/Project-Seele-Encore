"""Lossless bounded reader/writer for installed Xaero World Map 1.47 cache.

Format 1.25 was checked against the installed MapSaveLoad, LeveledRegion,
RegionTexture and ConsistentBitArray implementations. No world/player data is
stored here; unmodified cache records remain byte-identical.
"""
import io,struct,zipfile
from dataclasses import dataclass
import numpy as np

class Reader:
    def __init__(self,data):self.data=data;self.at=0
    def take(self,n):
        v=self.data[self.at:self.at+n]
        if len(v)!=n:raise ValueError('Truncated Xaero cache')
        self.at+=n;return v
    def u8(self):return self.take(1)[0]
    def i32(self):return struct.unpack('>i',self.take(4))[0]
    def utf(self):return self.take(struct.unpack('>H',self.take(2))[0]).decode('utf8')

def unpack_heights(raw):
    words=np.frombuffer(raw,dtype='>u8');values=((words[:,None]>>np.arange(4,dtype=np.uint64)[None,:]*13)&8191).reshape(64,64)
    h=(values&4095).astype(np.int16);h[h>=2048]-=4096;h[(values&4096)==0]=-32768
    return h

def pack_heights(h):
    v=np.where(h==-32768,0,4096|(h.astype(np.int64)&4095)).astype(np.uint64).reshape(-1,4)
    words=np.bitwise_or.reduce(v<<(np.arange(4,dtype=np.uint64)*13)[None,:],axis=1)
    return words.astype('>u8').tobytes()

@dataclass
class Tile:
    key:int
    raw:bytes
    compressed:int
    format:int
    pixels:bytes
    light:int
    heights:bytes
    top_heights:bytes
    biomes:bytes
    def image(self):
        from PIL import Image
        if not self.compressed:
            if self.format in (6408,32856):
                # Xaero's big-endian packed colour is light,R,G,B. Alpha in
                # this returned image carries the native light byte, not opacity.
                a=np.frombuffer(self.pixels,np.uint8).reshape(64,64,4)
                return Image.fromarray(a[:,:,[1,2,3,0]],'RGBA')
            if self.format==32993:return Image.frombytes('RGBA',(64,64),self.pixels,'raw','BGRA')
            if self.format==6407:return Image.frombytes('RGB',(64,64),self.pixels).convert('RGBA')
            raise ValueError(('Unknown native colour format',self.format))
        fourcc={33776:b'DXT1',33777:b'DXT1',33778:b'DXT3',33779:b'DXT5'}.get(self.format)
        if fourcc is None:raise ValueError(('Unsupported native compressed texture',self.format))
        header=b'DDS '+struct.pack('<7I',124,0x81007,64,64,len(self.pixels),0,1)+bytes(44)+struct.pack('<II4sIIIII',32,4,fourcc,0,0,0,0,0)+struct.pack('<5I',0x1000,0,0,0,0)
        return Image.open(io.BytesIO(header+self.pixels)).convert('RGBA')
    def replaced(self,image,heights,top_heights):
        pixels=np.asarray(image.convert('RGBA'))[:,:,[3,0,1,2]].tobytes()
        return bytes([self.key,0])+struct.pack('>ii',32856,len(pixels))+pixels+bytes([self.light])+pack_heights(heights)+pack_heights(top_heights)+self.biomes

class Cache:
    @classmethod
    def empty(cls,leaf=True):
        # New surface regions use native default metadata and the current
        # surface layer bounds. Existing opaque region metadata is untouched.
        prefix=bytes(12)+struct.pack('>2i',2147483647,30)if leaf else b''
        return cls(struct.pack('>i',65561)+prefix+b'\xff'+struct.pack('>i',0)+b'\xff',leaf)
    def add_empty_tile(self,key):
        if key in self.tiles:raise ValueError('Cannot replace an existing native tile')
        h=pack_heights(np.full((64,64),-32768,np.int16))
        tail=struct.pack('>i',0)+(struct.pack('>4i',-1,-1,-1,-1)if not self.leaf else b'')
        pixels=bytes(16384)
        raw=bytes([key,0])+struct.pack('>ii',32856,len(pixels))+pixels+b'\x00'+h+h+tail
        self.versions[key]=0;self.tiles[key]=Tile(key,raw,0,32856,pixels,0,h,h,tail)
    def __init__(self,data,leaf=True):
        r=Reader(data);self.original=data;self.version=r.i32()
        if self.version!=65561:raise ValueError(('Unsupported Xaero cache version',self.version))
        self.leaf=leaf
        # Preserve the native region metadata as opaque bytes. No identity or
        # fingerprint field is recomputed, interpreted or compared separately.
        self.prefix=r.take(20)if leaf else b''
        self.versions={}
        while (key:=r.u8())!=255:
            if key in self.versions:raise ValueError('Duplicate cache metadata')
            self.versions[key]=r.i32()
        self.biome_start=r.at;n=r.i32()
        for i in range(n):
            flag=r.u8()
            if flag==0:r.utf()
            elif flag!=255:raise ValueError('Unexpected legacy biome ID')
        self.biome_header=data[self.biome_start:r.at];self.tiles={}
        while True:
            start=r.at;key=r.u8()
            if key==255:break
            if key not in self.versions or key in self.tiles:raise ValueError('Inconsistent cache metadata')
            compressed=r.u8();fmt=r.i32();length=r.i32()
            if length<0 or length>16384:raise ValueError('Invalid texture payload length')
            pixels=r.take(length);light=r.u8();heights=r.take(8192);top=r.take(8192);bstart=r.at
            count=r.i32()
            for _ in range(count):
                if r.i32()!=-1:r.take(2)
            if count and r.u8():r.take(8192)
            if not leaf:r.take(16)
            self.tiles[key]=Tile(key,data[start:r.at],compressed,fmt,pixels,light,heights,top,data[bstart:r.at])
        if r.at!=len(data)or self.tiles.keys()!=self.versions.keys():raise ValueError('Cache tail or metadata mismatch')
    @classmethod
    def open(cls,path,leaf=None):
        with zipfile.ZipFile(path)as z:
            if z.namelist()!=['cache.xaero']:raise ValueError('Unexpected Xaero cache members')
            return cls(z.read('cache.xaero'),leaf=not path.parent.name.isdigit()if leaf is None else leaf)
    def encode(self,updates=None):
        updates=updates or {};out=bytearray(struct.pack('>i',self.version)+self.prefix)
        for key,version in self.versions.items():out.extend(bytes([key])+struct.pack('>i',version+(1 if key in updates else 0)))
        out.extend(b'\xff'+self.biome_header)
        for key,tile in self.tiles.items():out.extend(updates.get(key,tile.raw))
        out.append(255);return bytes(out)
    def write(self,path,updates):
        data=self.encode(updates);check=Cache(data,self.leaf)
        for key,tile in self.tiles.items():
            if key not in updates and check.tiles[key].raw!=tile.raw:raise ValueError('Unchanged tile altered')
        with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED)as z:z.writestr('cache.xaero',data)
        if Cache.open(path,leaf=self.leaf).original!=data:raise ValueError('Xaero cache readback mismatch')

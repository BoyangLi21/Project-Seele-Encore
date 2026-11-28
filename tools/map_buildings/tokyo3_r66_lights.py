"""Update the authored R65 far-light survey for the rebuilt rigid cargo. Preserve streets and protected owners."""
import argparse,gzip,io,struct
from pathlib import Path
from tokyo3_r66_design import OWNERS
def read(stream,fmt):
    return struct.unpack(fmt,stream.read(struct.calcsize(fmt)))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('old',type=Path);ap.add_argument('shell',type=Path);ap.add_argument('out',type=Path);args=ap.parse_args()
    rebuild(args.old,args.shell,args.out,OWNERS)

def rebuild(old,shell,out,selected):
    with gzip.open(old,'rb') as f:
        magic,owners,n=read(f,'>IHI');assert (magic,owners)==(0x4c523635,100)
        bases=f.read(owners*4);orig=[read(f,'>hhhBBB') for _ in range(n)];assert f.read()==b''
    rows={r for r in orig if r[-1] not in selected}
    with gzip.open(shell,'rb')as f:
        assert read(f,'>IH')==(0x54333636,100)
        for i in range(100):
            x,y,z,low,*bounds=read(f,'>8h');nq,=read(f,'>I')
            for j in range(nq):
                face,plane,u,w,width,height,r,g,b,lit=read(f,'>BhhhBBBBBB')
                if i not in selected or not lit or face==4:continue
                for uu in range(u,u+width):
                    for ww in range(w,w+height):
                        if (uu*23+ww*11+i)%5:continue
                        if face<2:xx,zz=x+plane-int(face==0),z+uu
                        else:xx,zz=x+uu,z+plane-int(face==2)
                        rows.add((xx,y+ww,zz,1,(1,0,3,2)[face],i))
    assert len(rows)<=60000
    with out.open('wb') as file,gzip.GzipFile(filename='',fileobj=file,mode='wb',mtime=0) as f:
        f.write(struct.pack('>IHI',magic,owners,len(rows))+bases)
        for row in sorted(rows):f.write(struct.pack('>hhhBBB',*row))
    print('Light anchors:',len(orig),'->',len(rows))
if __name__=='__main__':main()

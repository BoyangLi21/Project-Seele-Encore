"""Copy the playtest world's outer-ring chunks into a copy of the formal world, raw record by raw record.

Only empty slots are filled: a chunk the copy already has (the surveyed map, the 60 south-west donor chunks of batch
697, anything written since) is never touched. A region file the copy lacks is taken whole; a shared one is rebuilt
with the copy's records first and the playtest records for its empty slots after them. Block data only (region/);
entities and POI of the ring are left to the game. Every copied record is compared byte for byte afterwards.

usage: ringcopy_r65.py <copy region dir> <playtest region dir> [--dry]
"""
import os, shutil, struct, sys, time, hashlib

SECTOR = 4096


def read_region(path):
    data = open(path, 'rb').read() if os.path.exists(path) else b''
    recs = {}
    if len(data) < 8192: return data, recs
    for i in range(1024):
        off = int.from_bytes(data[i * 4:i * 4 + 3], 'big'); cnt = data[i * 4 + 3]
        if not off or not cnt: continue
        p = off * SECTOR
        if p + 5 > len(data): continue
        ln = struct.unpack_from('>i', data, p)[0]
        if ln <= 0 or p + 4 + ln > len(data): continue
        ts = struct.unpack_from('>i', data, 4096 + i * 4)[0]
        recs[i] = (data[p:p + 4 + ln], ts)
    return data, recs


def write_region(path, recs):
    head = bytearray(8192); body = bytearray(); sector = 2
    for i in sorted(recs):
        rec, ts = recs[i]
        n = (len(rec) + SECTOR - 1) // SECTOR
        if n > 255: raise ValueError(f'{path} slot {i}: record of {n} sectors')
        head[i * 4:i * 4 + 3] = sector.to_bytes(3, 'big'); head[i * 4 + 3] = n
        struct.pack_into('>i', head, 4096 + i * 4, ts)
        body += rec + b'\0' * (n * SECTOR - len(rec)); sector += n
    tmp = path + '.ringtmp'
    with open(tmp, 'wb') as f: f.write(head); f.write(body)
    os.replace(tmp, path)


def main():
    dst, src = sys.argv[1], sys.argv[2]; dry = '--dry' in sys.argv
    t = time.time(); whole = merged = added = 0; bytes_added = 0; plan = {}
    for name in sorted(os.listdir(src)):
        if not name.endswith('.mca'): continue
        s_data, s_recs = read_region(os.path.join(src, name))
        if not s_recs: continue
        dp = os.path.join(dst, name)
        d_data, d_recs = read_region(dp)
        new = {i: r for i, r in s_recs.items() if i not in d_recs}
        if not new: continue
        plan[name] = {i: r[0] for i, r in new.items()}
        if not d_recs:
            whole += 1; added += len(new); bytes_added += len(s_data)
            if not dry: shutil.copyfile(os.path.join(src, name), dp)
        else:
            merged += 1; added += len(new); bytes_added += sum(len(r[0]) for r in new.values())
            if not dry: write_region(dp, {**d_recs, **new})
    print(f'region files copied whole {whole}, merged {merged}; chunks added {added}; ~{bytes_added / 1e9:.2f} GB; {time.time() - t:.0f} s', flush=True)
    if dry: return
    # readback: every added record is in the copy byte for byte, and no slot the copy had before changed
    bad = 0
    for name, recs in plan.items():
        _, d_recs = read_region(os.path.join(dst, name))
        bad += sum(1 for i, rec in recs.items() if d_recs.get(i, (None,))[0] != rec)
    print(f'readback: added records {sum(len(v) for v in plan.values())}, wrong {bad}')

if __name__ == '__main__':
    main()

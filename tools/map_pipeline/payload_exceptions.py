"""Keep the captured state when successive exterior passes touch one cell."""

def record_exception(rows,entry):
    previous=next((r for r in reversed(rows)if r['pos']==entry['pos']),None)
    if previous is None:
        rows.append(entry);return
    if previous['after']!=entry['before']:
        raise ValueError(('Exterior payload exception chain mismatch',entry['pos']))
    previous['after']=entry['after']
    if entry.get('kind'):previous.setdefault('subsequent_operations',[]).append(entry['kind'])

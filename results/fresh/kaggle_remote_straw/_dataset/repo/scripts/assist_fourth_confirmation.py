"""Resume pending confirmation cases from the far end of the queue."""
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from confirm_fourth_quadrant import run,R

if __name__=='__main__':
    jobs=json.loads((R.OUT/'confirmation_manifest.json').read_text(encoding='utf-8'))['jobs']
    pending=[tuple(j) for j in reversed(jobs) if not (R.OUT/'games'/('-'.join(map(str,j))+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=4,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in pending]):f.result()

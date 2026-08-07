import sys
import time
import csv
import numpy as np
from pathlib import Path
sys.path.insert(0, r'c:\Users\WINDOWS\Evacuaciones')
from experimento import barrido_propuesta1 as bp

bp.RHO_VALS = [0.75, 1.0]
bp.D_INV_VALS = list(np.logspace(-3, 0, 16))
bp.N_SIMS = 100

start = time.time()
output = bp.ejecutar_barrido()
end = time.time()
print(f'elapsed {end-start}')

ref = []
with open('tabla_escenario_base.csv', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rho = float(row['rho'])
        if rho in (0.75, 1.0):
            ref.append((rho, float(row['T_mean']), float(row['sigma_T'])))

print(f'ref rows {len(ref)}')
ok = True
for idx, entry in enumerate(output['resultados']):
    rho = entry['rho']
    T = entry['metricas']['T']
    sigma = entry['metricas']['sigma_T']
    ref_rho, ref_T, ref_sigma = ref[idx]
    if abs(T - ref_T) > 1e-9 or abs(sigma - ref_sigma) > 1e-9:
        print('mismatch', idx, rho, T, sigma, 'ref', ref_T, ref_sigma)
        ok = False
        break
print('all match' if ok else 'some mismatch')
print('sample0', output['resultados'][0])
print('sample15', output['resultados'][15])
print('sample16', output['resultados'][16])
print('sample31', output['resultados'][31])

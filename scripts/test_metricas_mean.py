"""Quick validation script for calcular_metricas() fix.

Constructs a fake ensemble and patches _calcular_t to return controlled T values,
then verifies that metricas['T'] equals the mean of those values.
"""
from unittest.mock import patch
from experimento import metricas

def main():
    desired_ts = [10, 12, 14, 16, 18]

    # Build dummy histories (content irrelevant because _calcular_t is patched)
    ensemble = [[{}] for _ in desired_ts]

    # Patch _calcular_t to return values from desired_ts in order
    def fake_calcular_t(historia_unica):
        # Pop the first value from list each call
        return fake_calcular_t.values.pop(0)

    fake_calcular_t.values = desired_ts.copy()

    with patch.object(metricas, '_calcular_t', side_effect=fake_calcular_t):
        res = metricas.calcular_metricas(ensemble)

    T_old = desired_ts[0]
    T_new = sum(desired_ts) / len(desired_ts)

    print("ts (expected):", desired_ts)
    print("T_old (first):", T_old)
    print("T_new (mean):", T_new)
    print("metricas['T']:", res.get('T'))

    assert abs(res.get('T') - T_new) < 1e-9, "calcular_metricas T is not the mean"
    print("TEST PASSED: metricas['T'] equals ensemble mean.")

if __name__ == '__main__':
    main()

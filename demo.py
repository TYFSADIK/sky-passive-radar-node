"""Run: python demo.py  -> FM-like scene with 2 aircraft, ECA, range-Doppler, CA-CFAR, ADS-B scoring."""
import numpy as np

from pradar.caf import caf
from pradar.cfar import ca_cfar, peaks
from pradar.eca import eca
from pradar.signals import scene
from pradar.truth import associate

FS = 250_000
targets = ((15_000, 80.0, -42), (32_000, -55.0, -45))
ref, surv = scene(fs=FS, seconds=1.0, targets=targets)

for label, s in (("raw", surv), ("ECA", eca(ref, surv, n_taps=40, batch=FS // 4))):
    p, rng, dop = caf(ref, s, FS, max_range_m=45_000)
    det, _ = ca_cfar(p)
    pk = peaks(p, det, rng, dop)
    m, miss, fa = associate(pk, {"C-GABC": targets[0][:2], "C-FXYZ": targets[1][:2]})
    print(f"{label:4s}: {len(pk)} peaks, matched {sorted(m)}, missed {miss}, false {len(fa)}")
    for k, v in m.items():
        print(f"      {k}: range {v[0]/1000:.1f} km, doppler {v[1]:+.1f} Hz, {v[2]:.1f} dB")
print("range resolution c/B = %.0f m (FM 200 kHz)" % (299792458 / 200e3))

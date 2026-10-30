"""Write a synthetic scene as .cf32 (interleaved float32 I/Q) for the Rust worker or GNU Radio.

    python -m pradar.export_cf32 data/ref.cf32 data/surv.cf32
"""
import sys

import numpy as np

from .signals import scene

TARGETS = ((15_000, 80.0, -42), (32_000, -55.0, -45))


def main(ref_path, surv_path, seconds=1.0):
    ref, surv = scene(fs=250_000, seconds=seconds, targets=TARGETS)
    ref.astype(np.complex64).tofile(ref_path)
    surv.astype(np.complex64).tofile(surv_path)


if __name__ == "__main__":
    main(*sys.argv[1:3])

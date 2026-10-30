import json
import os
import subprocess
import tempfile
import unittest

import numpy as np

from pradar import export_cf32

from pradar.caf import caf
from pradar.cfar import ca_cfar, peaks
from pradar.eca import eca
from pradar.signals import scene
from pradar.truth import aircraft_state, bistatic, lla_to_ecef

FS = 250_000


class TestPassiveRadar(unittest.TestCase):
    def test_eca_suppresses_clutter(self):
        ref, surv = scene(fs=FS, seconds=0.2, targets=())
        out = eca(ref, surv, n_taps=40)
        supp = 10 * np.log10(np.mean(np.abs(surv) ** 2) / np.mean(np.abs(out) ** 2))
        self.assertGreater(supp, 8)

    def test_target_found_after_eca(self):
        ref, surv = scene(fs=FS, seconds=1.0, targets=((20_000, 60.0, -40),))
        p, r, d = caf(ref, eca(ref, surv, 40, batch=FS // 4), FS, 40_000)
        det, _ = ca_cfar(p)
        pk = peaks(p, det, r, d)
        self.assertTrue(any(abs(x[0] - 20_000) < 1500 and abs(x[1] - 60) < 3 for x in pk), pk[:3])

    def test_bistatic_geometry(self):
        tx = lla_to_ecef(45.40, -75.70, 100)
        rx = lla_to_ecef(45.42, -75.60, 80)
        pos, vel = aircraft_state(45.50, -75.65, 3000, 0, 0)
        rng, dop = bistatic(tx, rx, pos, vel, 100e6)
        self.assertGreater(rng, 0)
        self.assertAlmostEqual(dop, 0, places=6)          # stationary -> no Doppler
        pos, vel = aircraft_state(45.50, -75.65, 3000, 250, 180)   # flying south, toward both sites
        _, dop = bistatic(tx, rx, pos, vel, 100e6)
        self.assertGreater(dop, 0)                         # closing -> positive Doppler


if __name__ == "__main__":
    unittest.main()


class TestRustWorkerMatchesPython(unittest.TestCase):
    BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dsp-rs", "target", "release", "pradar-dsp")

    def test_same_detections(self):
        if not os.path.exists(self.BIN):
            self.skipTest("build dsp-rs first: cargo build --release")
        d = tempfile.mkdtemp()
        ref_p, surv_p = os.path.join(d, "ref.cf32"), os.path.join(d, "surv.cf32")
        export_cf32.main(ref_p, surv_p)
        rust = json.loads(subprocess.check_output([self.BIN, "--ref", ref_p, "--surv", surv_p]))["detections"]
        r = np.fromfile(ref_p, np.complex64).astype(complex)
        s = np.fromfile(surv_p, np.complex64).astype(complex)
        p, rg, dp = caf(r, eca(r, s, 40, batch=62_500), FS, 45_000)
        det, _ = ca_cfar(p)
        py = peaks(p, det, rg, dp)
        self.assertEqual(len(rust), len(py))
        for a, b in zip(rust, py):
            self.assertAlmostEqual(a["range_m"], b[0], delta=1.0)
            self.assertAlmostEqual(a["doppler_hz"], b[1], delta=0.01)
            self.assertAlmostEqual(a["snr_db"], b[2], delta=0.1)

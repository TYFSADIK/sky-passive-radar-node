"""Synthetic reference and surveillance channels for developing the pipeline without RF.

A noise-like broadcast (FM-like occupied bandwidth) is a good stand-in: what matters
for the cross-ambiguity function is bandwidth and integration time.
"""
import numpy as np

C = 299_792_458.0


def broadcast(fs, n, bw_hz, rng):
    """Band-limited complex noise of bandwidth bw_hz (unit power)."""
    x = rng.normal(size=n) + 1j * rng.normal(size=n)
    X = np.fft.fft(x)
    f = np.fft.fftfreq(n, 1 / fs)
    X[np.abs(f) > bw_hz / 2] = 0
    x = np.fft.ifft(X)
    return x / np.sqrt(np.mean(np.abs(x) ** 2))


def delay_doppler(x, fs, delay_s, doppler_hz):
    n = len(x)
    f = np.fft.fftfreq(n, 1 / fs)
    y = np.fft.ifft(np.fft.fft(x) * np.exp(-2j * np.pi * f * delay_s))
    return y * np.exp(2j * np.pi * doppler_hz * np.arange(n) / fs)


def scene(fs=250_000, seconds=0.5, bw_hz=200_000, targets=((12_000, 120.0, -45),),
          clutter=((0, 0), (600, -10), (1800, -20), (4200, -25)), direct_db=0, snr_noise_db=-10, seed=0):
    """targets: (bistatic_range_m, doppler_hz, power_db rel. direct). clutter: (range_m, power_db) at 0 Hz."""
    rng = np.random.default_rng(seed)
    n = int(fs * seconds)
    ref = broadcast(fs, n, bw_hz, rng)
    surv = np.zeros(n, complex)
    for r, p in clutter:
        surv += 10 ** ((p + direct_db) / 20) * delay_doppler(ref, fs, r / C, 0.0)
    for r, fd, p in targets:
        surv += 10 ** (p / 20) * delay_doppler(ref, fs, r / C, fd)
    noise_amp = 10 ** (snr_noise_db / 20)
    surv += noise_amp * (rng.normal(size=n) + 1j * rng.normal(size=n)) / np.sqrt(2)
    ref_noisy = ref + 0.01 * (rng.normal(size=n) + 1j * rng.normal(size=n))
    return ref_noisy, surv

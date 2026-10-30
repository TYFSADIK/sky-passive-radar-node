# Sky: Passive Aerial Early-Warning Node

Private research repo. A receive-only passive radar on a KrakenSDR 5-channel coherent SDR. Broadcast reflections off aircraft are processed into range-Doppler maps and scored against ADS-B truth.

> **Keep this repo private.** Your project page notes that passive radar processing may fall under an export-control category. Check Canada's Export Control List with Global Affairs Canada before publishing the code.

Full write-up: [`docs/project-page.md`](docs/project-page.md)

## Pipeline

```
ref (Yagi -> Tx) ─┐
                  ├─ ECA-B clutter cancel ─> batches CAF (range-Doppler) ─> 2D CA-CFAR ─> peaks
surv (array)  ────┘                                                             │
ADS-B (dump1090) ─> bistatic range/Doppler prediction ──────────────────────────┴─> associate + score
```

## What's here

| File | Purpose |
|---|---|
| `pradar/signals.py` | Synthetic scene: band-limited broadcast, direct path, 0-Hz clutter, delayed and Doppler-shifted targets |
| `pradar/eca.py` | **ECA** least-squares clutter cancellation, batched (ECA-B), optional Doppler columns (ECA-S style) |
| `pradar/caf.py` | Cross-ambiguity function with the **batches algorithm** (FFT range per batch, FFT across batches for Doppler) |
| `pradar/cfar.py` | **2D CA-CFAR** using summed-area tables, threshold from the design Pfa, zero-Doppler ridge excluded |
| `pradar/truth.py` | WGS-84 → ECEF, bistatic range and Doppler from ADS-B (lat, lon, alt, gs, track, vrate), gated association |
| `pradar/krakensdr.py` | Placeholder for the KrakenSDR heimdall DAQ input |

## Rust real-time worker (`dsp-rs/`)

The Python package is for research. `dsp-rs` is the same pipeline (ECA-B, then batched CAF, then 2D CA-CFAR, then peaks) in **Rust**, multithreaded with rayon and reading raw `.cf32` IQ (the GNU Radio, KrakenSDR, and SoapySDR format).

| 1 s CPI, 250 kS/s, 40 taps, 45 km | Python (NumPy) | Rust |
|---|---|---|
| Processing time (M-series Mac) | ~390 ms | **~13 ms** |
| Detections | identical | identical (cross-checked in `tests/`) |

```bash
(cd dsp-rs && cargo build --release && cargo test --release)
python -m pradar.export_cf32 /tmp/ref.cf32 /tmp/surv.cf32
dsp-rs/target/release/pradar-dsp --ref /tmp/ref.cf32 --surv /tmp/surv.cf32
# Raspberry Pi 5: rustup target add aarch64-unknown-linux-gnu && cargo zigbuild --release --target aarch64-unknown-linux-gnu
```

## Quickstart

```bash
pip install -r requirements.txt
python demo.py && python -m unittest -v
```

## Next steps
- [ ] Wire `krakensdr.py` to the heimdall DAQ stream, using ch0 as the reference and ch1–4 as surveillance
- [ ] T3 (FM, about 1500 m resolution) vs T4 (ATSC 6 MHz, about 50 m): run the same airspace on both illuminators
- [ ] Use the four surveillance channels for angle of arrival (MUSIC on the target cell) to get position, not just bistatic range
- [ ] Track across CPIs (a Kalman filter in range and Doppler) before scoring, then report Pd vs ADS-B per range bin
- [ ] Move the CAF to the GPU (CuPy) or a C++/FFTW worker if the Pi can't keep up in real time

//! pradar-dsp --ref ref.cf32 --surv surv.cf32 [--fs 250000] [--max-range 45000]
//! Prints JSON: {"cpi_s":..,"elapsed_ms":..,"detections":[{range_m,doppler_hz,snr_db},..]}
use clap::Parser;
use pradar_dsp::{process, read_cf32, Config};
use std::{fs, time::Instant};

#[derive(Parser)]
struct Args {
    #[arg(long = "ref")]
    reference: String,
    #[arg(long)]
    surv: String,
    #[arg(long, default_value_t = 250_000.0)]
    fs: f64,
    #[arg(long, default_value_t = 45_000.0)]
    max_range: f64,
    #[arg(long, default_value_t = 40)]
    taps: usize,
    #[arg(long, default_value_t = 62_500)]
    batch: usize,
}

fn main() {
    let a = Args::parse();
    let r = read_cf32(&fs::read(&a.reference).expect("read ref"));
    let s = read_cf32(&fs::read(&a.surv).expect("read surv"));
    let cfg = Config { fs: a.fs, max_range_m: a.max_range, taps: a.taps, eca_batch: a.batch, ..Default::default() };
    let t0 = Instant::now();
    let det = process(&r, &s, &cfg);
    let ms = t0.elapsed().as_secs_f64() * 1e3;
    println!("{}", serde_json::json!({"cpi_s": r.len() as f64 / a.fs, "elapsed_ms": ms, "detections": det}));
}

use crate::{caf::RangeDoppler, Detection};

/// 2D CA-CFAR (square-law), summed-area table, wrap padding (matches the Python implementation).
pub fn ca_cfar(p: &[f32], d: usize, r: usize, guard: (usize, usize), train: (usize, usize), pfa: f64, excl: usize) -> Vec<bool> {
    let (gd, gr) = guard;
    let (td, tr) = train;
    let (pd, pr) = (gd + td, gr + tr);
    let (hd, wr) = (d + 2 * pd, r + 2 * pr);
    // summed-area table of the wrap-padded map, f64 to avoid cancellation error
    let mut sat = vec![0f64; (hd + 1) * (wr + 1)];
    for y in 0..hd {
        let sy = (y + d - pd % d) % d;
        let mut row = 0f64;
        for x in 0..wr {
            let sx = (x + r * (pr / r + 1) - pr) % r;
            row += p[sy * r + sx] as f64;
            sat[(y + 1) * (wr + 1) + x + 1] = sat[y * (wr + 1) + x + 1] + row;
        }
    }
    let boxsum = |y0: usize, y1: usize, x0: usize, x1: usize| {
        sat[y1 * (wr + 1) + x1] - sat[y0 * (wr + 1) + x1] - sat[y1 * (wr + 1) + x0] + sat[y0 * (wr + 1) + x0]
    };
    let n_train = ((2 * pd + 1) * (2 * pr + 1) - (2 * gd + 1) * (2 * gr + 1)) as f64;
    let alpha = n_train * (pfa.powf(-1.0 / n_train) - 1.0);
    let mid = d / 2;
    let mut det = vec![false; d * r];
    for y in 0..d {
        if excl > 0 && y + excl >= mid && y <= mid + excl {
            continue;
        }
        let yy = y + pd;
        for x in 0..r {
            let xx = x + pr;
            let outer = boxsum(yy - pd, yy + pd + 1, xx - pr, xx + pr + 1);
            let inner = boxsum(yy - gd, yy + gd + 1, xx - gr, xx + gr + 1);
            det[y * r + x] = p[y * r + x] as f64 > alpha * (outer - inner) / n_train;
        }
    }
    det
}

pub fn peaks(m: &RangeDoppler, det: &[bool], max_peaks: usize) -> Vec<Detection> {
    let (d, r) = (m.n_dopp, m.n_lags);
    let mut sorted: Vec<f32> = m.power.clone();
    let mid = sorted.len() / 2;
    let median = *sorted.select_nth_unstable_by(mid, |a, b| a.total_cmp(b)).1 as f64;
    let mut out = Vec::new();
    for y in 0..d {
        for x in 0..r {
            if !det[y * r + x] {
                continue;
            }
            let v = m.power[y * r + x];
            let mut is_max = true;
            for yy in y.saturating_sub(1)..(y + 2).min(d) {
                for xx in x.saturating_sub(1)..(x + 2).min(r) {
                    if m.power[yy * r + xx] > v {
                        is_max = false;
                    }
                }
            }
            if is_max {
                out.push(Detection { range_m: m.ranges_m[x], doppler_hz: m.doppler_hz[y], snr_db: 10.0 * (v as f64 / median).log10() });
            }
        }
    }
    out.sort_by(|a, b| b.snr_db.total_cmp(&a.snr_db));
    out.truncate(max_peaks);
    out
}

"""Detection rate of the wideband energy detector and the tile detector on an FHSS link.

Each detector's threshold is the 99th percentile of its statistic over noise-only
captures, so the false alarm rate per capture is about 1 %. Both detectors see the same
captures. The tile is n_frames x n_bins spectrogram cells (256-point FFT, 12.8 us and
78.1 kHz per cell). SNR is packet power over noise power in the
whole capture bandwidth (fs_hz). The link parameters are assumptions chosen to look like
a 2.4 GHz FSK control radio; they are not taken from a particular protocol.

    python experiments/detection_curves.py
"""
import argparse

import numpy as np

from rfdrone.detect import energy_statistic, tile_statistic
from rfdrone.links import fhss_control

FS_HZ = 20e6
DURATION_S = 10e-3
LINK = {"channels_hz": np.arange(-8, 9) * 1e6, "dwell_s": 2e-3, "packet_s": 0.5e-3,
        "sym_rate_hz": 250e3, "dev_hz": 50e3}


def noise(n, power, rng):
    return np.sqrt(power / 2) * (rng.standard_normal(n) + 1j * rng.standard_normal(n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--noise-trials", type=int, default=2000)
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--tile", type=int, nargs=2, default=[39, 2], metavar=("FRAMES", "BINS"))
    args = ap.parse_args()

    detectors = {
        "energy": energy_statistic,
        "tile": lambda x: tile_statistic(x, n_frames=args.tile[0], n_bins=args.tile[1]),
    }
    rng = np.random.default_rng(args.seed)
    n = round(DURATION_S * FS_HZ)
    h0 = {k: [] for k in detectors}
    for _ in range(args.noise_trials):
        x = noise(n, 1.0, rng)
        for k, f in detectors.items():
            h0[k].append(f(x))
    thr_db = {k: np.quantile(v, 0.99) for k, v in h0.items()}
    for k, t in thr_db.items():
        print(f"{k} threshold {t:.2f} dB from {args.noise_trials} noise-only captures")

    print("snr_db  " + "  ".join(f"{k:>6}" for k in detectors))
    for snr_db in [-30, -25, -22, -20, -18, -15, -10, -8, -6, -4, 0]:
        hits = dict.fromkeys(detectors, 0)
        for _ in range(args.trials):
            iq, _ = fhss_control(FS_HZ, DURATION_S, rng=rng, **LINK)
            x = iq + noise(n, 10 ** (-snr_db / 10), rng)
            for k, f in detectors.items():
                hits[k] += f(x) > thr_db[k]
        print(f"{snr_db:6d}  " + "  ".join(f"{hits[k] / args.trials:6.3f}" for k in detectors))


if __name__ == "__main__":
    main()

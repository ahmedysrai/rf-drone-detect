"""Detection rate of the wideband energy detector on a simulated FHSS control link.

The threshold is the 99th percentile of the statistic over noise-only captures, so the
false alarm rate per capture is about 1 %. SNR is packet power over noise power in the
whole capture bandwidth (fs_hz). The link parameters are assumptions chosen to look like
a 2.4 GHz FSK control radio; they are not taken from a particular protocol.

    python experiments/energy_baseline.py
"""
import argparse

import numpy as np

from rfdrone.detect import energy_statistic
from rfdrone.links import fhss_control

FS_HZ = 20e6
DURATION_S = 10e-3
LINK = {"channels_hz": np.arange(-8, 9) * 1e6, "dwell_s": 2e-3, "packet_s": 0.5e-3,
        "sym_rate_hz": 250e3, "dev_hz": 50e3}


def noise(n, power, rng):
    return np.sqrt(power / 2) * (rng.standard_normal(n) + 1j * rng.standard_normal(n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--noise-trials", type=int, default=400)
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    n = round(DURATION_S * FS_HZ)
    h0 = [energy_statistic(noise(n, 1.0, rng)) for _ in range(args.noise_trials)]
    thr_db = np.quantile(h0, 0.99)
    print(f"threshold {thr_db:.2f} dB from {args.noise_trials} noise-only captures")

    print("snr_db  p_detect")
    for snr_db in [-20, -15, -10, -8, -6, -4, 0]:
        hits = 0
        for _ in range(args.trials):
            iq, _ = fhss_control(FS_HZ, DURATION_S, rng=rng, **LINK)
            stat = energy_statistic(iq + noise(n, 10 ** (-snr_db / 10), rng))
            hits += stat > thr_db
        print(f"{snr_db:6d}  {hits / args.trials:.3f}")


if __name__ == "__main__":
    main()

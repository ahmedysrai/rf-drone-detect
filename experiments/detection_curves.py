"""Detection rate of the wideband energy detector and the tile detector on an FHSS link.

Each detector's threshold is the 99th percentile of its statistic over noise-only
captures, so the false alarm rate per capture is about 1 %. Both detectors see the same
captures. The tile is n_frames x n_bins spectrogram cells (256-point FFT, 12.8 us and
78.1 kHz per cell). SNR is packet power over noise power in the
whole capture bandwidth (fs_hz). The link parameters are assumptions chosen to look like
a 2.4 GHz FSK control radio; they are not taken from a particular protocol. A second
table runs the same detectors on captures holding only a Wi-Fi interferer, so every
detection there is a false alarm, and a third puts the link and Wi-Fi in one capture.
The "narrow" column is the tile detector with a limit on the occupied bandwidth of the
region it found, which is meant to reject wideband emitters such as Wi-Fi. "masked" is
the same after leaving out the frames a wideband burst raised (detect.wideband_frames),
with its own noise-only threshold.

    python experiments/detection_curves.py
"""
import argparse

import numpy as np

from rfdrone.detect import energy_statistic, occupied_bins, tile_statistic
from rfdrone.links import WIFI_20MHZ, fhss_control, ofdm_bursts

FS_HZ = 20e6
DURATION_S = 10e-3
LINK = {"channels_hz": np.arange(-8, 9) * 1e6, "dwell_s": 2e-3, "packet_s": 0.5e-3,
        "sym_rate_hz": 250e3, "dev_hz": 50e3}
# Wi-Fi interferer on the capture centre. Burst length and mean gap are assumptions
# (about a 1500 byte frame at 6 Mbit/s, and a lightly loaded channel), not measured traffic.
WIFI = {**WIFI_20MHZ, "fc_hz": 0.0, "burst_s": 2e-3, "gap_s": 5e-3}
# "narrow" is the tile detector plus a limit on occupied bandwidth (78.1 kHz bins). 12 bins
# sits between the 2 to 9 a control packet gave and the 18 or more of a Wi-Fi burst at
# -5 dB, in a trial run on seed 1 (NOTES.md, 2026-11-22). The tables below use seed 0.
MAX_BINS = 12


def noise(n, power, rng):
    return np.sqrt(power / 2) * (rng.standard_normal(n) + 1j * rng.standard_normal(n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--noise-trials", type=int, default=2000)
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--tile", type=int, nargs=2, default=[39, 2], metavar=("FRAMES", "BINS"))
    ap.add_argument("--max-bins", type=int, default=MAX_BINS)
    args = ap.parse_args()

    detectors = {
        "energy": energy_statistic,
        "tile": lambda x: tile_statistic(x, *args.tile),
        "masked": lambda x: tile_statistic(x, *args.tile, mask_wideband=True),
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

    def decide(x):
        d = {k: f(x) > thr_db[k] for k, f in detectors.items()}
        d["narrow"] = d["tile"] and occupied_bins(x, *args.tile) <= args.max_bins
        d["masked"] = d["masked"] and \
            occupied_bins(x, *args.tile, mask_wideband=True) <= args.max_bins
        return d

    columns = ["energy", "tile", "narrow", "masked"]

    def table(title, snrs, make):
        print(title)
        print("snr_db  " + "  ".join(f"{k:>6}" for k in columns))
        for snr_db in snrs:
            hits = dict.fromkeys(columns, 0)
            for _ in range(args.trials):
                for k, v in decide(make(snr_db)).items():
                    hits[k] += v
            print(f"{snr_db:6d}  " + "  ".join(f"{hits[k] / args.trials:6.3f}" for k in columns))

    def link_only(snr_db):
        iq, _ = fhss_control(FS_HZ, DURATION_S, rng=rng, **LINK)
        return iq + noise(n, 10 ** (-snr_db / 10), rng)

    # SNR is burst power over noise power in the whole capture
    def wifi_only(snr_db):
        iq, _ = ofdm_bursts(FS_HZ, DURATION_S, rng=rng, **WIFI)
        return iq + noise(n, 10 ** (-snr_db / 10), rng)

    # Wi-Fi bursts at a fixed 0 dB under the link; SNR is the link's, as in the first table
    def link_and_wifi(snr_db):
        iq, _ = fhss_control(FS_HZ, DURATION_S, rng=rng, **LINK)
        wifi, _ = ofdm_bursts(FS_HZ, DURATION_S, rng=rng, **WIFI)
        p_noise = 10 ** (-snr_db / 10)
        return iq + np.sqrt(p_noise) * wifi + noise(n, p_noise, rng)

    table("FHSS link", [-30, -25, -22, -20, -18, -15, -10, -8, -6, -4, 0, 10, 20], link_only)
    table("Wi-Fi only, no link", [-20, -15, -10, -5, 0, 10], wifi_only)
    table("FHSS link with 0 dB Wi-Fi", [-20, -15, -10, -5, 0, 10], link_and_wifi)


if __name__ == "__main__":
    main()

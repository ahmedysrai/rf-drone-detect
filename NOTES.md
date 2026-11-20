# Notes

## 2026-11-19

First end to end run: FHSS control link (17 channels on a 1 MHz grid, 0.5 ms
packet every 2 ms dwell, 2-FSK at 250 kbaud with +/-50 kHz deviation, all
assumed) in a 20 MHz wide, 10 ms capture. Detector is the crudest one: total
energy per 256-sample frame, peak over median, threshold at the 99th
percentile of 400 noise-only captures (1.57 dB). 200 trials per SNR, seed 0.
(`python experiments/energy_baseline.py`)

    snr_db  p_detect
       -20  0.005
       -15  0.020
       -10  0.065
        -8  0.315
        -6  0.970
        -4  1.000
         0  1.000

SNR here is over the whole 20 MHz. The packet's main lobe is about 600 kHz
(2 x deviation + 2 x symbol rate), so in its own band it is roughly 15 dB
better off: at -8 dB wideband the packet sits about 7 dB above the noise in
its own bins and the detector still misses two thirds of captures. Summing
all 256 bins throws that away. Next step is a per-bin statistic on the
spectrogram so the noise outside the hop channel stops counting.

The 1 % false alarm figure rests on 4 exceedances out of 400, so it is
rough. Worth more noise trials once the detector is fast enough.

## 2026-11-20

Per-bin detector: average the spectrogram over a sliding tile of n_frames x
n_bins cells and take the peak over the median cell (`tile_statistic`).
Thresholds now from 2000 noise-only captures (about 20 exceedances at 1 %),
which moved the energy threshold from 1.57 to 1.52 dB. Same link and seed
as yesterday, 200 trials per SNR, SNR still over the full 20 MHz.

Tile size sweep, all 39 frames (one 0.5 ms packet) unless stated:

    tile    thr_db  p_det -22 dB  p_det -20 dB
    8x8     4.93    -             0.100
    78x8    2.70    -             0.515
    39x16   2.73    -             0.380
    39x8    3.17    -             0.755
    20x4    4.56    0.165         0.775
    39x4    3.72    0.350         0.970
    39x3    3.95    0.545         1.000
    39x2    4.27    0.695         1.000

(the first four came from a run before -22 and -18 dB were in the SNR list)

Narrower is better, which contradicts yesterday's guess of a 600 kHz main
lobe. Measured on a clean packet: the two strongest 78 kHz bins hold 72 % of
the power, three hold 94 %, five 99.6 %. With +/-50 kHz deviation the two
tones are only 1.3 bins apart, so the packet is about 2 to 3 bins wide, not 8.
Matching the tile length to the packet also matters: 8 frames is far worse
than 39, and 78 frames dilutes it again.

Kept 39x2 as the default (`python experiments/detection_curves.py`):

    snr_db  energy    tile
       -25   0.025   0.055
       -22   0.005   0.695
       -20   0.010   1.000
       -15   0.030   1.000
       -10   0.085   1.000
        -8   0.450   1.000
        -6   1.000   1.000

About 14 dB better than the wideband detector at the point where each first
reaches 0.97+ (-20 vs -6 dB). The tile is tuned to this exact packet, so the
number is optimistic for a link whose packet length and deviation are not
known in advance. A bank of tile sizes with the threshold set on the max over
the bank is the obvious next step once there is a second link type to test.

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

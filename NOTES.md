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

## 2026-11-21

Wi-Fi interferer: `ofdm_bursts` with the 802.11a 20 MHz numbers (64-point
FFT, 52 used subcarriers, 0.8 us CP) on the capture centre, so it covers
16.6 of the 20 MHz. Bursts of 2 ms (a 1500 byte frame at 6 Mbit/s) with
exponential gaps, mean 5 ms; both assumed. No drone link in these
captures, same thresholds as the link table, 200 trials per SNR, seed 0
(`python experiments/detection_curves.py`, second table):

    snr_db  energy    tile
       -20   0.000   0.010
       -15   0.020   0.010
       -10   0.055   0.055
        -5   0.760   0.830
         0   0.800   0.870
        10   0.790   0.880

From -5 dB up both detectors alarm on Wi-Fi alone. The ceiling is set by the
traffic model: with a 5 ms mean gap, e^-2 = 13.5 % of 10 ms captures hold no
burst, so the tile detector fires on nearly every capture that has one. Not
sure yet why the energy detector sits a few points lower; 200 trials gives
about +/-0.03, so it may be noise. Either way, energy above the floor says
nothing about what made it. A Wi-Fi burst is 2 ms long and 212 bins wide,
the control packet 0.5 ms and 2 to 3 bins, so the shape of the occupied
region should separate them. That is the next thing to measure.

## 2026-11-22

Shape feature, first part: occupied bandwidth of the region the tile detector
found (`occupied_bins`). Average the spectrogram over the 39 frames of the
peak tile, then count bins more than 3 noise sigma above the floor (median
cell / ln 2) and within 20 dB of the strongest bin.

Trial run on seed 1, 10 captures each: noise alone 2 to 4 bins (the peak
tile itself), control packet 2 to 9 from -22 to 0 dB, Wi-Fi 18 to 46 at
-5 dB and 115 to 221 from 0 dB up. Without the 20 dB limit the packet grew
to 15-25 bins at +20 dB and 26-63 at +30 dB, because the CPFSK skirts (no
pulse shaping) rise above the floor; with it the packet stays at 5-6 bins
at any SNR. Picked 12 bins (940 kHz) as the cut between the two. Wi-Fi at
-10 dB already measures 2 to 9, so the cut only helps once Wi-Fi is strong
enough to be seen at all.

Seed 0, 200 trials, same thresholds as before. "narrow" is tile detector
fired and occupied_bins <= 12 (`python experiments/detection_curves.py`).
Link alone: narrow is identical to tile at every SNR from -30 to +20 dB
(1.000 from -20 dB). Wi-Fi alone:

    snr_db  energy    tile  narrow
       -10   0.065   0.080   0.080
        -5   0.805   0.840   0.000
         0   0.805   0.850   0.005
        10   0.790   0.885   0.000

Link and Wi-Fi in the same capture, Wi-Fi at 0 dB:

    snr_db  energy    tile  narrow
       -20   0.810   1.000   0.170
       -10   0.840   1.000   0.400
         0   1.000   1.000   0.580
        10   1.000   1.000   1.000

So the width test removes the Wi-Fi false alarms and costs nothing on a
clean link, but it throws the link away whenever a Wi-Fi burst is on during
the packet's frames: the count is over the whole band, so the Wi-Fi bins
add to the packet's. At +10 dB the packet is more than 20 dB above the
Wi-Fi bins and they drop out. Measuring width only over the bins connected
to the peak, or masking wideband frames first, should fix most of this.
The Wi-Fi-only numbers moved by a point or two from 11-21 because two more
link SNRs now run first and shift the random stream.

## 2026-11-23

Looked at why the width gate loses the link when Wi-Fi is on. Seed 1, 40
mixed captures each (Wi-Fi at 0 dB): the peak tile lands on the packet in
65 % of captures at -20 dB and in all of them at -10 and 0 dB, but a Wi-Fi
burst overlaps the tile's frames in 73 % at -10 dB and 40 % at 0 dB. So the
gate fails mostly because the packet and a burst are on at the same time,
not because the tile picks the Wi-Fi burst. The link channels (-8 to +8 MHz)
all sit inside the +/-8.1 MHz Wi-Fi band, so counting only bins connected to
the peak should not help much, and it did not: 0.60 / 0.77 / 0.83 of
captures under 12 connected bins at -20 / -10 / 0 dB, before the detection
threshold is applied.

Masking wideband frames instead (`detect.wideband_frames`). A Wi-Fi burst
raises the median bin of the frames it covers; the packet's few bins do not.
On seed 1 the per-frame median over the capture median had sd 0.11 on noise
alone, and over burst frames it averaged 1.02 / 1.08 / 1.21 / 1.61 at Wi-Fi
-15 / -10 / -5 / 0 dB. Single frames are too noisy to call, so the median is
averaged over 8 frames and a frame is flagged above median + 4 x 1.4826 MAD.
Flagged frames are set to the median of the frames left, and the floor for
both the tile statistic and the bandwidth count comes from those frames too.
Taking the floor from the whole spectrogram, as before, left mixed detection
at 0.62 at -20 dB in a 100-trial prototype; the masked floor gave 0.88.
Averaging over 16 frames, or widening the mask by 4 or 8 frames each side,
moved nothing by more than 0.01, so it stays at 8 and no widening.

Seed 0, 200 trials, `python experiments/detection_curves.py`. "masked" has its
own noise-only threshold, which came out the same as the tile's (4.27 dB):
on noise alone the mask almost never fires. Link alone: masked is the same as
tile at every SNR. Wi-Fi alone:

    snr_db  energy    tile  narrow  masked
       -10   0.065   0.080   0.080   0.080
        -5   0.805   0.840   0.000   0.020
         0   0.805   0.850   0.005   0.010
        10   0.790   0.885   0.000   0.015

Link with 0 dB Wi-Fi:

    snr_db  energy    tile  narrow  masked
       -20   0.810   1.000   0.170   0.955
       -15   0.750   1.000   0.315   0.925
       -10   0.840   1.000   0.400   0.885
        -5   1.000   1.000   0.530   0.930
         0   1.000   1.000   0.580   0.955
        10   1.000   1.000   1.000   1.000

The masked false alarms on Wi-Fi alone sit at about the 1 % the threshold
was set for: once the burst frames are gone the rest is noise. The narrow
column was below that only because the burst inflated the width of noise
peaks too. The 5 to 12 % still missed with Wi-Fi on is not explained yet.
Two guesses to check: every packet in the capture fell under a burst (5
packets in 10 ms, bursts on about 29 % of the time), or the 8-frame average
leaves burst edges unflagged and those frames win the tile. Wi-Fi weaker
than about -10 dB is not flagged, but at that level it did not upset the
gate either. Columns energy, tile and narrow match 11-22 exactly, since the
mask draws nothing from the random stream.

## 2026-11-24

The 5 to 12 % of links still missed with 0 dB Wi-Fi on (11-23) were neither
of the two guesses. In every miss at -20, -10 and 0 dB (seed 0, 200 trials
each) at least one packet sat in unflagged frames, so packets hidden under
bursts were not it. In 41 of the 45 misses the mask had flagged no frame
at all, while Wi-Fi covered 375 to 584 of the 781 frames. With bursts on for
more than about half the capture the median frame is a Wi-Fi frame, the
threshold rises with it, and occupied_bins then counts the Wi-Fi bins (60 to
142) and the width gate rejects the capture. 2000 draws of the Wi-Fi model
gave more than half the capture busy in 8 % of them, which is about the miss
rate. Of the other 4, all at -20 dB, one had only 246 of 361 burst frames
flagged and failed the width gate, and 3 had the bursts masked and a tile
statistic of 3.8 to 4.3 dB, just under the 4.27 dB threshold: plain misses.

Changed wideband_frames to compare each frame with the 10th percentile of
the 8-frame averages instead of the median and MAD, flagging above 1.3 x
that. On 500 noise-only captures (seed 1) the largest ratio of average to
10th percentile was 1.24 (median 1.18), and 1.25 with a -10 dB link added,
so 1.3 leaves a little room. On 500 more (seed 2) no frame was flagged.
This needs 10 % of the frames to be quiet, which every draw of this Wi-Fi
model had.

`python experiments/detection_curves.py`, seed 0. Link alone and Wi-Fi alone
are the same as 11-23 in every column, masked included. Link with 0 dB
Wi-Fi:

    snr_db  energy    tile  narrow  masked
       -20   0.810   1.000   0.170   0.990
       -15   0.750   1.000   0.315   1.000
       -10   0.840   1.000   0.400   1.000
        -5   1.000   1.000   0.530   1.000
         0   1.000   1.000   0.580   1.000
        10   1.000   1.000   1.000   1.000

The rise of 1.3 is about 1.1 dB above the quiet frames, so Wi-Fi weaker
than about -6 dB over 20 MHz (52 of 64 subcarriers lifting each bin by 0.3)
is still not flagged; at -10 dB it did not upset
the width gate in the 11-23 tables, but the range in between is untested.

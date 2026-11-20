# rf-drone-detect

Detect drone control and video links in 2.4 and 5.8 GHz SDR captures, classify
the link type, and estimate its bearing with a small antenna array.

The project is simulation based and covers detection and direction finding
only. So far there is a frequency hopping control link generator, a
spectrogram, a wideband energy detector kept as the baseline, and a tile
detector that looks for energy in a packet-sized patch of the spectrogram.
On the simulated control link the tile detector reaches full detection at
-20 dB SNR (over 20 MHz) against -6 dB for the baseline, both at 1 % false
alarms per capture. `NOTES.md` has the measured detection rates.

```sh
pip install -e .[dev]
pytest
python experiments/detection_curves.py
```

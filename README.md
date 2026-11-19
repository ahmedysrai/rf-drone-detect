# rf-drone-detect

Detect drone control and video links in 2.4 and 5.8 GHz SDR captures, classify
the link type, and estimate its bearing with a small antenna array.

The project is simulation based and covers detection and direction finding
only. So far there is a frequency hopping control link generator, a
spectrogram, and a wideband energy detector kept as the baseline that later
detectors have to beat. `NOTES.md` has the measured detection rates.

```sh
pip install -e .[dev]
pytest
python experiments/energy_baseline.py
```

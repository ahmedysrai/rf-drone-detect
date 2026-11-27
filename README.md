# rf-drone-detect

Detect drone control and video links in 2.4 and 5.8 GHz SDR captures, classify
the link type, and estimate its bearing with a small antenna array.

The project is simulation based and covers detection and direction finding
only. So far there is a frequency hopping control link generator, a Wi-Fi
style OFDM burst generator used as an interferer, a spectrogram, a wideband
energy detector kept as the baseline, and a tile detector that looks for
energy in a packet-sized patch of the spectrogram. On the simulated control
link the tile detector reaches full detection at -20 dB SNR (over 20 MHz)
against -6 dB for the baseline, both at 1 % false alarms per capture.
A Wi-Fi burst at -5 dB with no drone present sets off both detectors.
Adding a limit on the occupied bandwidth of the detected region cuts those
false alarms to 0.5 % or less, but on its own it rejects most real detections
whenever Wi-Fi is on the air at the same time as the link. Leaving out the
parts of the spectrogram a Wi-Fi burst raises before running the tile detector
and the bandwidth limit, with the noise floor for that limit taken from the
detected region's own frames, fixes that. The mask works per sub-band, so it
also covers a Wi-Fi channel up to 15 MHz off centre that only partly falls in
the capture. With Wi-Fi from -10 to 0 dB, centred or off centre, the link is
found in 94.5 % or more of captures at -20 dB and in at least 99 % from -15 dB
up. Wi-Fi alone sets the detector off in 4 % of captures or less, except a
-5 dB channel 15 MHz off centre, which does in 14 %.
`NOTES.md` has the measured rates.

```sh
pip install -e .[dev]
pytest
python experiments/detection_curves.py
```

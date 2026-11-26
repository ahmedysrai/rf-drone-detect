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
frames a Wi-Fi burst covers before running the tile detector and the bandwidth
limit, with the noise floor for that limit taken from the detected region's own
frames, fixes that: with Wi-Fi from -10 to 0 dB in the capture the link is found
in 98 % or more of captures at -20 dB and in at least 99.5 % from -15 dB up, and
Wi-Fi alone sets it off in 1 to 2 %. Those figures are for a Wi-Fi channel
centred on the capture. With the channel 5 to 15 MHz off centre, so that only
part of it falls in the capture, the frame mask misses the bursts: Wi-Fi alone
at -5 dB then sets off the detector in a third to a half of captures, and a
0 dB channel 15 MHz off centre hides the link in up to 83 % of them.
`NOTES.md` has the measured rates.

```sh
pip install -e .[dev]
pytest
python experiments/detection_curves.py
```

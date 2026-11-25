import numpy as np
import pytest

from rfdrone.detect import (
    _box_mean,
    energy_statistic,
    occupied_bins,
    tile_statistic,
    wideband_frames,
)
from rfdrone.links import WIFI_20MHZ, ofdm_bursts
from rfdrone.spectro import bin_freqs, spectrogram


@pytest.fixture
def rng():
    return np.random.default_rng(5)


def test_white_noise_bins_average_to_its_variance(rng):
    s2 = 0.3
    iq = np.sqrt(s2 / 2) * (rng.standard_normal(256 * 400) + 1j * rng.standard_normal(256 * 400))
    P = spectrogram(iq, 256)
    # 102400 exponential samples: standard error of the mean is about 0.3 %
    assert P.mean() == pytest.approx(s2, rel=0.01)


def test_tone_lands_in_its_bin():
    fs_hz, nfft = 20e6, 256
    f_hz = 40 * fs_hz / nfft - fs_hz / 2  # exactly on column 40
    iq = np.exp(2j * np.pi * f_hz * np.arange(nfft * 4) / fs_hz)
    P = spectrogram(iq, nfft)
    assert np.all(P.argmax(axis=1) == 40)
    assert bin_freqs(nfft, fs_hz)[40] == pytest.approx(f_hz)


def test_hop_sets_frame_count():
    iq = np.zeros(1000, dtype=complex)
    assert spectrogram(iq, 256).shape == (3, 256)
    assert spectrogram(iq, 256, hop=128).shape == (6, 256)


def test_energy_statistic_rises_with_a_burst(rng):
    n = 256 * 200
    noise = (rng.standard_normal(n) + 1j * rng.standard_normal(n)) / np.sqrt(2)
    burst = np.zeros(n, dtype=complex)
    burst[256 * 50:256 * 60] = 1.0
    assert energy_statistic(noise + burst) > energy_statistic(noise) + 2.0


def test_box_mean_matches_a_direct_sum(rng):
    P = rng.random((12, 10))
    t = _box_mean(P, 3, 4)
    assert t.shape == (10, 7)
    assert t[2, 5] == pytest.approx(P[2:5, 5:9].mean())
    assert t[-1, -1] == pytest.approx(P[-3:, -4:].mean())


def test_tile_statistic_finds_a_narrow_burst_the_energy_detector_misses(rng):
    fs_hz, nfft = 20e6, 256
    n = nfft * 200
    noise = (rng.standard_normal(n) + 1j * rng.standard_normal(n)) / np.sqrt(2)
    # tone 5 dB below the noise power in the whole band, on for 10 of 200 frames
    k = np.arange(nfft * 10)
    burst = np.zeros(n, dtype=complex)
    burst[nfft * 50:nfft * 60] = np.sqrt(0.3) * np.exp(2j * np.pi * 1e6 * k / fs_hz)
    clean = tile_statistic(noise, 10, 4)
    assert tile_statistic(noise + burst, 10, 4) > clean + 5
    assert energy_statistic(noise + burst) < energy_statistic(noise) + 2


def test_on_bin_tone_occupies_the_hann_main_lobe():
    # an on-bin tone through a Hann window lands in its bin and the two either side at
    # -6 dB; every other bin is a null, far more than 20 dB down
    fs_hz, nfft = 20e6, 256
    f_hz = 40 * fs_hz / nfft - fs_hz / 2
    iq = np.exp(2j * np.pi * f_hz * np.arange(nfft * 100) / fs_hz)
    iq += 1e-3 * np.random.default_rng(1).standard_normal(len(iq))
    assert occupied_bins(iq, 39, 2) == 3


def test_ofdm_burst_occupies_its_subcarriers_and_a_tone_does_not(rng):
    fs_hz = 20e6
    burst, _ = ofdm_bursts(fs_hz, 2e-3, 0.0, burst_s=2e-3, gap_s=1e-9, rng=rng, **WIFI_20MHZ)
    # one burst in 10 ms, so most cells are still noise and the median floor holds
    wifi = np.concatenate([np.zeros(100_000, dtype=complex), burst, np.zeros(60_000)])
    n = len(wifi)
    noise = 0.1 * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
    # 52 x 312.5 kHz = 16.25 MHz is 208 bins of 78.1 kHz. The symbols have no edge
    # windowing, so their sinc skirts add a few dozen more bins within 20 dB.
    assert occupied_bins(wifi + noise, 39, 2) >= 200
    tone = np.exp(2j * np.pi * 1.3e6 * np.arange(n) / fs_hz)
    assert occupied_bins(tone + noise, 39, 2) <= 4


def test_noise_alone_occupies_only_the_peak_tile(rng):
    n = 256 * 781
    counts = [occupied_bins((rng.standard_normal(n) + 1j * rng.standard_normal(n)), 39, 2)
              for _ in range(20)]
    # the max tile is the noisiest pair of bins, so they usually pass; little else should
    assert max(counts) <= 6


def test_only_the_frames_of_the_peak_tile_are_counted(rng):
    fs_hz, nfft = 20e6, 256
    n = nfft * 781
    k = np.arange(nfft * 39)
    x = 0.1 * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
    x[:len(k)] += np.exp(2j * np.pi * 1.3e6 * k / fs_hz)
    # a weaker Wi-Fi burst well after the tone, in frames the peak tile does not cover
    burst, _ = ofdm_bursts(fs_hz, 2e-3, 0.0, burst_s=2e-3, gap_s=1e-9, rng=rng, **WIFI_20MHZ)
    x[nfft * 400:nfft * 400 + len(burst)] += burst
    assert occupied_bins(x, 39, 2) <= 4


def _wifi_in_noise(rng, start, n, power):
    fs_hz = 20e6
    burst, _ = ofdm_bursts(fs_hz, 2e-3, 0.0, burst_s=2e-3, gap_s=1e-9, rng=rng, **WIFI_20MHZ)
    x = (rng.standard_normal(n) + 1j * rng.standard_normal(n)) / np.sqrt(2)
    x[start:start + len(burst)] += np.sqrt(power) * burst
    return x


def test_wideband_frames_flags_a_wifi_burst_and_little_else(rng):
    nfft = 256
    x = _wifi_in_noise(rng, nfft * 300, nfft * 781, 1.0)
    busy = wideband_frames(spectrogram(x, nfft))
    # the 2 ms burst covers frames 300 to 455; the 8-frame average blurs its edges
    assert busy[305:450].all()
    assert np.count_nonzero(busy[:290]) + np.count_nonzero(busy[465:]) <= 3


def test_a_narrow_burst_is_not_a_wideband_frame(rng):
    fs_hz, nfft = 20e6, 256
    n = nfft * 781
    x = (rng.standard_normal(n) + 1j * rng.standard_normal(n)) / np.sqrt(2)
    k = np.arange(nfft * 39)
    x[nfft * 300:nfft * 339] += 100 * np.exp(2j * np.pi * 1.3e6 * k / fs_hz)
    assert not wideband_frames(spectrogram(x, nfft))[290:350].any()


def test_masking_moves_the_peak_tile_off_the_wifi_frames(rng):
    # a weak tone through the whole capture, Wi-Fi on top of it for 2 ms: the tone plus
    # Wi-Fi frames hold the strongest tile until they are masked
    fs_hz, nfft = 20e6, 256
    n = nfft * 781
    x = _wifi_in_noise(rng, nfft * 300, n, 1.0)
    x += 0.5 * np.exp(2j * np.pi * 1.3e6 * np.arange(n) / fs_hz)
    assert occupied_bins(x, 39, 2) >= 100
    assert occupied_bins(x, 39, 2, mask_wideband=True) <= 6


def test_masking_drops_the_tile_statistic_of_wifi_alone(rng):
    # noise alone gives about 3.7 to 4.1 dB on a capture this size; the detection curves
    # threshold is 4.3 dB
    x = _wifi_in_noise(rng, 256 * 300, 256 * 781, 1.0)
    assert tile_statistic(x, 39, 2) > 6
    assert tile_statistic(x, 39, 2, mask_wideband=True) < 4.2


def test_wideband_frames_flags_wifi_on_most_of_the_capture(rng):
    # three 2 ms bursts cover about 60 % of the frames, so the median frame is a Wi-Fi frame
    nfft = 256
    x = _wifi_in_noise(rng, nfft * 100, nfft * 781, 1.0)
    for start in (260, 420):
        burst, _ = ofdm_bursts(20e6, 2e-3, 0.0, burst_s=2e-3, gap_s=1e-9, rng=rng,
                               **WIFI_20MHZ)
        x[nfft * start:nfft * start + len(burst)] += burst
    busy = wideband_frames(spectrogram(x, nfft))
    assert busy[105:250].all() and busy[265:410].all() and busy[425:570].all()
    assert np.count_nonzero(busy[:90]) + np.count_nonzero(busy[590:]) <= 3


def test_local_floor_drops_the_bins_of_wifi_too_weak_to_mask(rng):
    # a -10 dB burst is under the mask's rise, so its frames stay in. A weak tone in the
    # same frames holds the peak tile, and against the capture's floor the lifted Wi-Fi
    # bins near the threshold count as occupied
    fs_hz, nfft = 20e6, 256
    k = np.arange(nfft * 39)
    plain, local = [], []
    for _ in range(10):
        x = _wifi_in_noise(rng, nfft * 300, nfft * 781, 0.1)
        x[nfft * 320:nfft * 359] += np.sqrt(0.1) * np.exp(2j * np.pi * 1.3e6 * k / fs_hz)
        plain.append(occupied_bins(x, 39, 2, mask_wideband=True))
        local.append(occupied_bins(x, 39, 2, mask_wideband=True, local_floor=True))
    assert np.mean(local) <= 6
    assert np.mean(local) < 0.7 * np.mean(plain)

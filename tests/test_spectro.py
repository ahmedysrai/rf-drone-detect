import numpy as np
import pytest

from rfdrone.detect import _box_mean, energy_statistic, tile_statistic
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

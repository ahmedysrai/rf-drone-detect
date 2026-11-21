import numpy as np
import pytest

from rfdrone.links import WIFI_20MHZ, ofdm_bursts

FS_HZ = 20e6
N_FFT, N_CP = 64, 16


def make(fc_hz=0.0, rng=5, duration_s=2e-3, **kw):
    params = {**WIFI_20MHZ, "burst_s": 200e-6, "gap_s": 100e-6, **kw}
    return ofdm_bursts(FS_HZ, duration_s, fc_hz, rng=rng, **params)


def symbols(iq, bursts):
    """Useful parts (CP removed) of every whole symbol, shape (n_symbols, N_FFT)."""
    out = []
    for start, stop in bursts:
        n_whole = (stop - start) // (N_FFT + N_CP)
        seg = iq[start:start + n_whole * (N_FFT + N_CP)].reshape(n_whole, N_FFT + N_CP)
        out.append(seg[:, N_CP:])
    return np.concatenate(out)


def test_cyclic_prefix_copies_end_of_symbol():
    iq, bursts = make()
    n_sym = N_FFT + N_CP
    for start, stop in bursts:
        for s in range(start, stop - n_sym + 1, n_sym):
            np.testing.assert_allclose(iq[s:s + N_CP], iq[s + N_FFT:s + n_sym], atol=1e-12)


def test_only_used_subcarriers_carry_energy():
    # fc of 3 bins keeps the shift periodic over one symbol, so bins stay exact
    iq, bursts = make(fc_hz=3 * 312.5e3)
    spec = np.abs(np.fft.fft(symbols(iq, bursts), axis=1)) ** 2
    k = (np.fft.fftfreq(N_FFT, 1 / N_FFT) - 3).astype(int)
    used = (np.abs(k) <= 26) & (k != 0)
    assert np.all(spec[:, ~used] < 1e-18)
    # QPSK has constant modulus, so every used bin has the same power
    np.testing.assert_allclose(spec[:, used], spec[0, used][0], rtol=1e-9)


def test_unit_power_in_bursts_and_silence_between():
    iq, bursts = make(duration_s=20e-3)
    on = np.zeros(len(iq), dtype=bool)
    for start, stop in bursts:
        on[start:stop] = True
    assert not np.any(iq[~on])
    # CP samples repeat part of the symbol, so a burst's power is 1 only on average;
    # over ~70 bursts of 50 symbols the mean is within a percent
    assert np.mean(np.abs(iq[on]) ** 2) == pytest.approx(1.0, rel=0.01)


def test_burst_length_is_whole_symbols():
    _, bursts = make(duration_s=20e-3)
    lengths = np.diff(bursts, axis=1).ravel()[:-1]   # the last one may be cut by the capture
    assert np.all(lengths == 50 * (N_FFT + N_CP))   # 200 us / 4 us
    assert np.all(bursts[1:, 0] >= bursts[:-1, 1])


def test_mean_gap_follows_gap_s():
    _, bursts = make(duration_s=200e-3, gap_s=300e-6)
    gaps_s = (bursts[1:, 0] - bursts[:-1, 1]) / FS_HZ
    # exponential gaps: standard error of the mean is gap_s / sqrt(n), n is about 400 here
    assert np.mean(gaps_s) == pytest.approx(300e-6, rel=0.15)


def test_channel_outside_capture_raises():
    with pytest.raises(ValueError, match="fc must lie within"):
        make(fc_hz=2e6)


def test_spacing_that_does_not_divide_fs_raises():
    with pytest.raises(ValueError, match="whole number"):
        make(subcarrier_hz=300e3)

import numpy as np
import pytest

from rfdrone.links import fhss_control

FS_HZ = 20e6
CHANNELS_HZ = np.arange(-8, 9) * 1e6


def make(rng=3, duration_s=10e-3, channels_hz=CHANNELS_HZ):
    return fhss_control(FS_HZ, duration_s, channels_hz, dwell_s=2e-3, packet_s=0.5e-3,
                        sym_rate_hz=250e3, dev_hz=50e3, rng=rng)


def test_packet_power_sits_on_its_channel():
    iq, hops = make()
    n_pkt = round(0.5e-3 * FS_HZ)
    for start, ch in hops:
        seg = iq[int(start):int(start) + n_pkt]
        p = np.abs(np.fft.fft(seg)) ** 2
        f = np.fft.fftfreq(len(seg), 1 / FS_HZ)
        # tones at ch +/- 50 kHz plus the sinc skirts of 4 us symbols
        near = np.abs(f - ch) < 1e6
        assert p[near].sum() / p.sum() > 0.95


def test_unit_power_during_packet_and_silence_between():
    iq, hops = make()
    n_pkt = round(0.5e-3 * FS_HZ)
    on = np.zeros(len(iq), dtype=bool)
    for start, _ in hops:
        on[int(start):int(start) + n_pkt] = True
    np.testing.assert_allclose(np.abs(iq[on]), 1.0, rtol=1e-12)
    assert not np.any(iq[~on])


def test_hops_use_listed_channels_and_never_repeat():
    _, hops = make(duration_s=200e-3)
    assert len(hops) == 100
    assert set(hops[:, 1]) <= set(CHANNELS_HZ)
    assert np.all(np.diff(hops[:, 1]) != 0)


def test_same_seed_gives_same_capture():
    a, _ = make(rng=11)
    b, _ = make(rng=11)
    np.testing.assert_array_equal(a, b)


def test_channel_outside_capture_raises():
    with pytest.raises(ValueError, match="channels must lie within"):
        make(channels_hz=[9.9e6])

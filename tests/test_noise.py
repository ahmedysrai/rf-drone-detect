import numpy as np
import pytest

from rfdrone.noise import add_awgn


@pytest.mark.parametrize("snr_db", [-5, 0, 10])
def test_measured_snr(snr_db):
    t = np.arange(200_000)
    iq = np.exp(2j * np.pi * 0.01 * t)
    noisy = add_awgn(iq, snr_db, rng=1)
    noise = noisy - iq
    measured = 10 * np.log10(np.mean(np.abs(iq) ** 2) / np.mean(np.abs(noise) ** 2))
    assert measured == pytest.approx(snr_db, abs=0.1)

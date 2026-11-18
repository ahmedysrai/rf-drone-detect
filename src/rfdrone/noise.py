import numpy as np


def add_awgn(iq, snr_db, rng=None):
    """Add complex white Gaussian noise to `iq` at the given SNR.

    SNR is measured against the mean power of `iq` itself.
    """
    rng = np.random.default_rng(rng)
    iq = np.asarray(iq, dtype=complex)
    p_sig = np.mean(np.abs(iq) ** 2)
    p_noise = p_sig / 10 ** (snr_db / 10)
    noise = rng.normal(size=iq.shape) + 1j * rng.normal(size=iq.shape)
    return iq + noise * np.sqrt(p_noise / 2)

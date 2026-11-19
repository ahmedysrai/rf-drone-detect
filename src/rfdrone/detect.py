"""Link detectors. Each returns a statistic; the threshold is set by the caller."""
import numpy as np

from rfdrone.spectro import spectrogram


def energy_statistic(iq, nfft=256):
    """Wideband energy detector: peak frame energy over median frame energy, in dB.

    The median stands in for the noise floor. It is biased upwards once a link is on in
    more than half the frames, which a hopping control link with short packets is not.
    """
    e = spectrogram(iq, nfft).sum(axis=1)
    return 10 * np.log10(e.max() / np.median(e))

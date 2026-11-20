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


def _box_mean(P, n_frames, n_bins):
    """Mean of P over every n_frames x n_bins block (valid positions only)."""
    c = np.cumsum(np.cumsum(P, axis=0), axis=1)
    c = np.pad(c, ((1, 0), (1, 0)))
    s = c[n_frames:, n_bins:] - c[:-n_frames, n_bins:] - c[n_frames:, :-n_bins] \
        + c[:-n_frames, :-n_bins]
    return s / (n_frames * n_bins)


def tile_statistic(iq, n_frames, n_bins, nfft=256):
    """Peak over median of the spectrogram averaged over n_frames x n_bins tiles, in dB.

    A narrowband burst only raises the bins it occupies, so averaging over a tile about the
    size of one packet keeps its energy and drops the noise in the rest of the band. The
    tile slides one frame and one bin at a time; tiles do not wrap around the band edge.
    """
    P = spectrogram(iq, nfft)
    if n_frames > P.shape[0] or n_bins > nfft:
        raise ValueError(f"tile {n_frames}x{n_bins} larger than spectrogram {P.shape}")
    t = _box_mean(P, n_frames, n_bins)
    return 10 * np.log10(t.max() / np.median(P))

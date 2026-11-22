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


def occupied_bins(iq, n_frames, n_bins, nfft=256, k_sigma=3.0, drop_db=20.0):
    """Number of spectrogram bins occupied during the strongest n_frames x n_bins tile.

    The spectrogram is averaged over the frames of the tile that tile_statistic would pick,
    giving one spectrum. A bin counts as occupied if it is more than k_sigma noise standard
    deviations above the floor and within drop_db of the strongest bin. The floor is the
    median cell over ln 2, since the median of exponentially distributed cell powers is ln 2
    times their mean; averaging n_frames independent frames leaves a standard deviation of
    floor / sqrt(n_frames). The drop_db limit keeps the window sidelobes and the skirts of a
    strong narrowband signal from counting as bandwidth.

    Bins are counted over the whole band, not only those next to the peak, so a second
    emitter on the air during the same frames adds its bins to the count. The floor estimate
    assumes more than half the cells hold only noise; a band that is busy most of the time
    raises it and hides the occupied bins.
    """
    P = spectrogram(iq, nfft)
    if n_frames > P.shape[0] or n_bins > nfft:
        raise ValueError(f"tile {n_frames}x{n_bins} larger than spectrogram {P.shape}")
    t = _box_mean(P, n_frames, n_bins)
    f0, _ = np.unravel_index(t.argmax(), t.shape)
    s = P[f0:f0 + n_frames].mean(axis=0)
    floor = np.median(P) / np.log(2)
    thr = max(floor * (1 + k_sigma / np.sqrt(n_frames)), s.max() * 10 ** (-drop_db / 10))
    return int(np.count_nonzero(s > thr))

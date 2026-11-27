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


def _moving_mean(x, n):
    """Mean over n rows centred on each row of x, over the rows that exist at the ends."""
    c = np.pad(np.cumsum(x, axis=0), ((1, 0), (0, 0)))
    i = np.arange(len(x)) - n // 2
    lo, hi = np.clip(i, 0, None), np.minimum(i + n, len(x))
    return (c[hi] - c[lo]) / (hi - lo)[:, None]


def _sub_band_rise(P, n_sub, n_avg, ref_quantile):
    """Level of each sub-band in each frame, and that level over its quiet reference.

    The level is the lower quartile of the n_sub bins of the spectrogram averaged over
    n_avg frames. Averaging first leaves each bin with a small spread, and the lower
    quartile ignores a narrowband signal and its skirts until they cover most of the
    sub-band. The reference is the ref_quantile of the level over the capture.
    """
    n_frames, nfft = P.shape
    if nfft % n_sub:
        raise ValueError(f"{nfft} bins do not split into sub-bands of {n_sub}")
    A = _moving_mean(P, n_avg).reshape(n_frames, nfft // n_sub, n_sub)
    level = np.quantile(A, 0.25, axis=2)
    return level, level / np.quantile(level, ref_quantile, axis=0)


def _grow(x, n_frames, n_cols):
    """Running maximum of x over n_frames rows and n_cols columns each way.

    Columns wrap around: the DFT is circular, so the leakage of a strong emitter just under
    +fs/2 lands in the first bins at -fs/2.
    """
    out = x.copy()
    for d in range(1, n_frames + 1):
        out[d:] = np.maximum(out[d:], x[:-d])
        out[:-d] = np.maximum(out[:-d], x[d:])
    grown = out.copy()
    for d in range(1, n_cols + 1):
        grown = np.maximum(grown, np.maximum(np.roll(out, d, axis=1), np.roll(out, -d, axis=1)))
    return grown


# Sub-band widths in bins and the rise each needs. Each rise sits just above the largest
# ratio seen in 500 noise-only captures of 781 frames on seed 1 (1.42, 1.26, 1.18, 1.12);
# none of 500 more on seed 2 reached them (NOTES.md, 2026-11-27).
SUB_BANDS = ((32, 1.45), (64, 1.28), (128, 1.2), (256, 1.13))


def wideband_cells(P, sub_bands=SUB_BANDS, n_avg=32, ref_quantile=0.1, keep_db=15.0):
    """Boolean mask, shape of P, of the cells that a wideband emitter has raised.

    For each (width, rise) in sub_bands the band is cut into sub-bands of that many bins,
    and a sub-band is flagged in a frame when its level is more than rise times its quiet
    reference (_sub_band_rise). Narrow sub-bands keep a Wi-Fi channel that covers only part
    of the capture visible, where over the whole band its median barely moves (NOTES.md,
    2026-11-26). Wide ones average more bins, so their level spreads less and a weaker
    burst that fills them still shows. A cell is flagged if any width flags it. The
    reference is a low quantile because Wi-Fi can be on for more than half of a capture,
    so only ref_quantile of the frames need to be quiet.

    A sub-band that a channel edge covers in part rises less and the averaging blurs the
    start and end of a burst, so the flags are grown by n_avg // 2 frames and one sub-band
    each way, wrapping from one band edge to the other. Inside the flagged region only cells
    within keep_db of the highest flagged level nearby are marked: a drone link strong
    enough to raise its own sub-band with its skirts (about 20 dB SNR and up with this
    unshaped CPFSK) keeps its packet. A Wi-Fi cell in a sub-band it fills exceeds keep_db
    with a probability of about e^-28, as cell powers are exponential. The level comes from
    the flagged sub-bands nearby, not the cell's own, because a sub-band that a channel edge
    only grazes has a level near the noise and strong Wi-Fi bins in it.
    """
    busy = np.zeros(P.shape, dtype=bool)
    near = np.zeros(P.shape)
    for n_sub, rise in sub_bands:
        level, r = _sub_band_rise(P, n_sub, n_avg, ref_quantile)
        flagged = r > rise
        busy |= np.repeat(_grow(flagged, n_avg // 2, 1), n_sub, axis=1)
        near = np.maximum(near, np.repeat(_grow(level * flagged, n_avg // 2, 1), n_sub, axis=1))
    return busy & (P < near * 10 ** (keep_db / 10))


def _spectrogram_and_floor(iq, nfft, mask_wideband):
    """Spectrogram and its median cell, with wideband cells replaced if asked.

    The median is then taken over the cells left, and flagged cells are set to the noise
    mean, median / ln 2, so a Wi-Fi burst neither raises the floor nor offers the tile
    detector a region to pick. The mean rather than the median keeps a partly masked frame
    from looking quieter than the noise bins next to it.
    """
    P = spectrogram(iq, nfft)
    if not mask_wideband:
        return P, np.median(P)
    busy = wideband_cells(P)
    med = np.median(P[~busy])
    P[busy] = med / np.log(2)
    return P, med


def tile_statistic(iq, n_frames, n_bins, nfft=256, mask_wideband=False):
    """Peak over median of the spectrogram averaged over n_frames x n_bins tiles, in dB.

    A narrowband burst only raises the bins it occupies, so averaging over a tile about the
    size of one packet keeps its energy and drops the noise in the rest of the band. The
    tile slides one frame and one bin at a time; tiles do not wrap around the band edge.
    With mask_wideband, cells flagged by wideband_cells are left out first.
    """
    P, med = _spectrogram_and_floor(iq, nfft, mask_wideband)
    if n_frames > P.shape[0] or n_bins > nfft:
        raise ValueError(f"tile {n_frames}x{n_bins} larger than spectrogram {P.shape}")
    t = _box_mean(P, n_frames, n_bins)
    return 10 * np.log10(t.max() / med)


def occupied_bins(iq, n_frames, n_bins, nfft=256, k_sigma=3.0, drop_db=20.0,
                  mask_wideband=False, local_floor=False):
    """Number of spectrogram bins occupied during the strongest n_frames x n_bins tile.

    The spectrogram is averaged over the frames of the tile that tile_statistic would pick,
    giving one spectrum. A bin counts as occupied if it is more than k_sigma noise standard
    deviations above the floor and within drop_db of the strongest bin. The floor is the
    median cell over ln 2, since the median of exponentially distributed cell powers is ln 2
    times their mean; averaging n_frames independent frames leaves a standard deviation of
    floor / sqrt(n_frames). The drop_db limit keeps the window sidelobes and the skirts of a
    strong narrowband signal from counting as bandwidth.

    Bins are counted over the whole band, not only those next to the peak, so a second
    emitter on the air during the same frames adds its bins to the count. mask_wideband
    leaves out the cells flagged by wideband_cells, so a Wi-Fi burst only adds bins where
    it was too weak to be flagged. The floor estimate assumes more than half the cells hold
    only noise; a band that is busy most of the time raises it and hides the occupied bins.

    local_floor takes the floor from the median bin of the tile's own spectrum instead of
    the median cell of the capture. A Wi-Fi burst too weak for the mask (about -6 dB and
    under) then raises the floor along with its own bins, and they stop counting. The median
    of a mean of n_frames cells is close to the mean, so there is no ln 2 here. Without
    the mask it would let Wi-Fi through the width gate, since a burst that fills the tile's
    frames sets the floor itself.
    """
    P, med = _spectrogram_and_floor(iq, nfft, mask_wideband)
    if n_frames > P.shape[0] or n_bins > nfft:
        raise ValueError(f"tile {n_frames}x{n_bins} larger than spectrogram {P.shape}")
    t = _box_mean(P, n_frames, n_bins)
    f0, _ = np.unravel_index(t.argmax(), t.shape)
    s = P[f0:f0 + n_frames].mean(axis=0)
    floor = np.median(s) if local_floor else med / np.log(2)
    thr = max(floor * (1 + k_sigma / np.sqrt(n_frames)), s.max() * 10 ** (-drop_db / 10))
    return int(np.count_nonzero(s > thr))

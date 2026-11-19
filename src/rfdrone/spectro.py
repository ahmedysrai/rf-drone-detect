"""Short-time spectra of complex captures."""
import numpy as np


def spectrogram(iq, nfft, hop=None):
    """Power spectrogram with a Hann window, shape (n_frames, nfft).

    Columns are fftshifted, so column 0 is -fs/2 and column nfft // 2 is DC. The window
    power is divided out: for white noise of variance s2 every bin has mean s2. Frames
    that would run past the end of iq are dropped. hop defaults to nfft (no overlap).
    """
    hop = nfft if hop is None else hop
    n_frames = (len(iq) - nfft) // hop + 1
    if n_frames < 1:
        raise ValueError(f"capture of {len(iq)} samples shorter than nfft {nfft}")
    w = np.hanning(nfft)
    idx = np.arange(nfft) + hop * np.arange(n_frames)[:, None]
    X = np.fft.fft(iq[idx] * w, axis=1)
    return np.fft.fftshift(np.abs(X) ** 2, axes=1) / np.sum(w**2)


def bin_freqs(nfft, fs_hz):
    """Centre frequency in Hz of each spectrogram column."""
    return np.fft.fftshift(np.fft.fftfreq(nfft, 1 / fs_hz))

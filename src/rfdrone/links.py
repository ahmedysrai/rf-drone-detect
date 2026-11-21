"""Simulated drone link waveforms at complex baseband."""
import numpy as np


def fhss_control(fs_hz, duration_s, channels_hz, dwell_s, packet_s, sym_rate_hz, dev_hz, rng=None):
    """Frequency hopping control link: one binary CPFSK packet at the start of each dwell.

    channels_hz are offsets from the capture centre. Each dwell picks a channel at random,
    never the one used in the previous dwell. The packet has unit power and the rest of the
    dwell is silent. There is no Gaussian pulse shaping, so the spectrum has wider skirts
    than a real GFSK radio.

    Returns (iq, hops): iq is complex, length round(duration_s * fs_hz); hops is an
    (n_hops, 2) array of [start_sample, channel_hz].
    """
    channels_hz = np.asarray(channels_hz, dtype=float)
    edge_hz = fs_hz / 2 - dev_hz - sym_rate_hz
    if np.any(np.abs(channels_hz) > edge_hz):
        raise ValueError(f"channels must lie within +/-{edge_hz:g} Hz for fs {fs_hz:g} Hz")
    if packet_s > dwell_s:
        raise ValueError(f"packet {packet_s:g} s longer than dwell {dwell_s:g} s")

    rng = np.random.default_rng(rng)
    n = round(duration_s * fs_hz)
    n_dwell = round(dwell_s * fs_hz)
    n_pkt = round(packet_s * fs_hz)
    iq = np.zeros(n, dtype=complex)
    hops = []
    prev = None
    for start in range(0, n, n_dwell):
        choices = channels_hz if prev is None or len(channels_hz) == 1 else \
            channels_hz[channels_hz != prev]
        ch = rng.choice(choices)
        m = min(n_pkt, n - start)
        k = np.arange(m)
        sym_idx = (k * sym_rate_hz / fs_hz).astype(int)
        bits = rng.integers(0, 2, size=sym_idx[-1] + 1) * 2 - 1
        f_inst = ch + dev_hz * bits[sym_idx]
        # phase is the running integral of frequency, so it stays continuous across symbols
        phase = 2 * np.pi * np.cumsum(f_inst) / fs_hz + rng.uniform(0, 2 * np.pi)
        iq[start:start + m] = np.exp(1j * phase)
        hops.append((start, ch))
        prev = ch
    return iq, np.array(hops)


# 802.11a/g 20 MHz channel: 64-point FFT at 20 MHz (312.5 kHz spacing), 52 used subcarriers
# (-26..26 without DC), 0.8 us guard interval, 4 us per symbol. From the Keysight 89600B help,
# "802.11 OFDM Overview", 802.11a timing parameters table.
WIFI_20MHZ = {"subcarrier_hz": 312.5e3, "n_used": 52, "cp_s": 0.8e-6}


def ofdm_bursts(fs_hz, duration_s, fc_hz, subcarrier_hz, n_used, cp_s, burst_s, gap_s, rng=None):
    """Bursts of OFDM symbols with random QPSK on every used subcarrier.

    The n_used subcarriers sit symmetrically around fc_hz with the DC one left empty, as in
    802.11a. fs_hz / subcarrier_hz must be a whole FFT size. Each burst holds as many whole
    symbols as fit in burst_s, and the idle time before each burst is exponential with mean
    gap_s (an assumption standing in for CSMA traffic). There is no preamble and no pilot
    pattern. Power is 1 averaged over a burst and 0 between bursts.

    Returns (iq, bursts): iq is complex, length round(duration_s * fs_hz); bursts is an
    (n_bursts, 2) array of [start_sample, stop_sample).
    """
    n_fft = fs_hz / subcarrier_hz
    if abs(n_fft - round(n_fft)) > 1e-9:
        raise ValueError(f"fs {fs_hz:g} Hz is not a whole number of {subcarrier_hz:g} Hz bins")
    n_fft = round(n_fft)
    if n_used % 2 or n_used + 1 > n_fft:
        raise ValueError(f"n_used must be even and below the FFT size {n_fft}")
    edge_hz = fs_hz / 2 - (n_used // 2) * subcarrier_hz
    if abs(fc_hz) > edge_hz:
        raise ValueError(f"fc must lie within +/-{edge_hz:g} Hz for fs {fs_hz:g} Hz")
    n_cp = round(cp_s * fs_hz)
    n_sym = n_fft + n_cp
    sym_per_burst = int(burst_s * fs_hz) // n_sym
    if sym_per_burst < 1:
        raise ValueError(f"burst {burst_s:g} s is shorter than one symbol")

    rng = np.random.default_rng(rng)
    n = round(duration_s * fs_hz)
    half = n_used // 2
    used = np.r_[-half:0, 1:half + 1] % n_fft
    iq = np.zeros(n, dtype=complex)
    bursts = []
    start = round(rng.exponential(gap_s) * fs_hz)
    while start < n:
        qpsk = (rng.integers(0, 2, (sym_per_burst, n_used)) * 2 - 1
                + 1j * (rng.integers(0, 2, (sym_per_burst, n_used)) * 2 - 1)) / np.sqrt(2)
        grid = np.zeros((sym_per_burst, n_fft), dtype=complex)
        grid[:, used] = qpsk
        # ifft divides by n_fft, so this scaling gives unit power over the useful part
        body = np.fft.ifft(grid, axis=1) * n_fft / np.sqrt(n_used)
        syms = np.concatenate([body[:, -n_cp:], body], axis=1) if n_cp else body
        burst = syms.ravel()
        stop = min(start + len(burst), n)
        t = np.arange(start, stop) / fs_hz
        iq[start:stop] = burst[:stop - start] * np.exp(2j * np.pi * fc_hz * t)
        bursts.append((start, stop))
        start = stop + round(rng.exponential(gap_s) * fs_hz)
    return iq, np.array(bursts, dtype=int).reshape(-1, 2)

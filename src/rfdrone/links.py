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

import math
from oscillators import SAMPLE_RATE


def apply_echo(samples, delay_time=0.3, decay=0.5, sample_rate=SAMPLE_RATE):
    delay_samples = int(delay_time * sample_rate)
    n = len(samples)
    result = [0.0] * n

    for i in range(n):
        result[i] = samples[i]
        if i >= delay_samples:
            result[i] += decay * result[i - delay_samples]

    max_val = max(abs(max(result)), abs(min(result)))
    if max_val > 1.0:
        result = [s / max_val for s in result]

    return result


def apply_reverb(samples, room_size=0.5, decay=0.6, sample_rate=SAMPLE_RATE):
    delays = [0.03, 0.05, 0.07, 0.11, 0.13, 0.17]
    gains = [0.8, 0.7, 0.6, 0.5, 0.4, 0.3]

    n = len(samples)
    result = list(samples)

    for delay_sec, gain in zip(delays, gains):
        delay_samples = int(delay_sec * sample_rate * (0.5 + room_size))
        for i in range(delay_samples, n):
            result[i] += gain * decay * samples[i - delay_samples]

    max_val = max(abs(max(result)), abs(min(result)))
    if max_val > 1.0:
        result = [s / max_val for s in result]

    return result


def apply_vibrato(samples, frequency_hz=5.0, depth_cents=50, sample_rate=SAMPLE_RATE):
    n = len(samples)
    result = [0.0] * n
    depth = depth_cents / 1200.0

    phase = 0.0
    phase_inc = 2 * math.pi * frequency_hz / sample_rate
    last_out = 0.0

    for i in range(n):
        mod = math.sin(phase) * depth
        delay = 1.0 + mod
        phase += phase_inc

        int_delay = int(delay)
        frac = delay - int_delay

        if i >= int_delay + 1:
            a = samples[i - int_delay]
            b = samples[i - int_delay - 1]
            result[i] = a + frac * (b - a)
        elif i >= int_delay:
            result[i] = samples[i - int_delay]
        else:
            result[i] = samples[i]

    return result


def apply_lowpass(samples, cutoff_freq=1000.0, sample_rate=SAMPLE_RATE):
    n = len(samples)
    result = [0.0] * n

    dt = 1.0 / sample_rate
    rc = 1.0 / (2 * math.pi * cutoff_freq)
    alpha = dt / (rc + dt)

    result[0] = samples[0]
    for i in range(1, n):
        result[i] = result[i - 1] + alpha * (samples[i] - result[i - 1])

    return result


def apply_highpass(samples, cutoff_freq=100.0, sample_rate=SAMPLE_RATE):
    n = len(samples)
    result = [0.0] * n

    dt = 1.0 / sample_rate
    rc = 1.0 / (2 * math.pi * cutoff_freq)
    alpha = rc / (rc + dt)

    result[0] = samples[0]
    for i in range(1, n):
        result[i] = alpha * (result[i - 1] + samples[i] - samples[i - 1])

    return result


def apply_gain(samples, gain):
    return [s * gain for s in samples]


def apply_distortion(samples, gain=2.0, threshold=0.8, sample_rate=SAMPLE_RATE):
    result = []
    for s in samples:
        s *= gain
        if s > threshold:
            s = threshold
        elif s < -threshold:
            s = -threshold
        s /= max(threshold, 1.0)
        result.append(s)
    return result


def apply_pan(samples, pan):
    pan = max(-1.0, min(1.0, pan))
    left_gain = math.sqrt((1.0 - pan) / 2.0)
    right_gain = math.sqrt((1.0 + pan) / 2.0)

    left = [s * left_gain for s in samples]
    right = [s * right_gain for s in samples]

    return left, right

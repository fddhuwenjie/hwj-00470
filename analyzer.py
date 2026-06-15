import math
import wave
from oscillators import SAMPLE_RATE, pcm_to_samples


def read_wav(filepath):
    with wave.open(filepath, 'rb') as wf:
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        frame_rate = wf.getframerate()
        n_frames = wf.getnframes()
        raw_data = wf.readframes(n_frames)

    if sample_width != 2:
        raise ValueError("Only 16-bit WAV files are supported")

    samples = pcm_to_samples(raw_data)

    if n_channels == 2:
        left = samples[::2]
        right = samples[1::2]
        mono = [(l + r) * 0.5 for l, r in zip(left, right)]
        return mono, frame_rate, n_channels
    else:
        return samples, frame_rate, n_channels


def ascii_waveform(samples, width=80, height=20):
    if not samples:
        return ""

    step = max(1, len(samples) // width)
    display_samples = samples[::step][:width]

    lines = []
    mid = height // 2

    for row in range(height):
        line = []
        for s in display_samples:
            amplitude = (s + 1.0) / 2.0
            sample_row = int(amplitude * (height - 1))
            if row == mid:
                if sample_row == row:
                    line.append('+')
                else:
                    line.append('-')
            elif sample_row == row:
                line.append('#')
            elif row < mid and sample_row > row and sample_row <= mid:
                line.append('|')
            elif row > mid and sample_row < row and sample_row >= mid:
                line.append('|')
            else:
                line.append(' ')
        lines.append(''.join(line))

    return '\n'.join(lines)


def fft(samples):
    n = len(samples)
    if n == 0:
        return []

    power = 1
    while power < n:
        power <<= 1
    N = power

    real = list(samples) + [0.0] * (N - n)
    imag = [0.0] * N

    j = 0
    for i in range(1, N):
        bit = N >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            real[i], real[j] = real[j], real[i]
            imag[i], imag[j] = imag[j], imag[i]

    size = 2
    while size <= N:
        half_size = size >> 1
        angle_step = -2 * math.pi / size

        for i in range(0, N, size):
            angle = 0.0
            for k in range(half_size):
                w_real = math.cos(angle)
                w_imag = math.sin(angle)

                even_idx = i + k
                odd_idx = i + k + half_size

                t_real = real[odd_idx] * w_real - imag[odd_idx] * w_imag
                t_imag = real[odd_idx] * w_imag + imag[odd_idx] * w_real

                real[odd_idx] = real[even_idx] - t_real
                imag[odd_idx] = imag[even_idx] - t_imag
                real[even_idx] = real[even_idx] + t_real
                imag[even_idx] = imag[even_idx] + t_imag

                angle += angle_step
        size <<= 1

    magnitudes = []
    for i in range(N // 2):
        mag = math.sqrt(real[i] * real[i] + imag[i] * imag[i])
        magnitudes.append(mag)

    return magnitudes


def spectrum_analysis(samples, sample_rate=SAMPLE_RATE, top_n=10):
    if not samples:
        return []

    n = min(len(samples), 8192)
    windowed = []
    for i in range(n):
        w = 0.5 * (1 - math.cos(2 * math.pi * i / (n - 1)))
        windowed.append(samples[i] * w)

    N = len(windowed)
    power = 1
    while power < N:
        power <<= 1
    M = power

    real = list(windowed) + [0.0] * (M - N)
    imag = [0.0] * M

    j = 0
    for i in range(1, M):
        bit = M >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            real[i], real[j] = real[j], real[i]
            imag[i], imag[j] = imag[j], imag[i]

    size = 2
    while size <= M:
        half_size = size >> 1
        angle_step = -2 * math.pi / size

        for i in range(0, M, size):
            angle = 0.0
            for k in range(half_size):
                w_real = math.cos(angle)
                w_imag = math.sin(angle)

                even_idx = i + k
                odd_idx = i + k + half_size

                t_real = real[odd_idx] * w_real - imag[odd_idx] * w_imag
                t_imag = real[odd_idx] * w_imag + imag[odd_idx] * w_real

                real[odd_idx] = real[even_idx] - t_real
                imag[odd_idx] = imag[even_idx] - t_imag
                real[even_idx] = real[even_idx] + t_real
                imag[even_idx] = imag[even_idx] + t_imag

                angle += angle_step
        size <<= 1

    freqs = []
    for i in range(M // 2):
        mag = math.sqrt(real[i] * real[i] + imag[i] * imag[i])
        freq = i * sample_rate / M
        freqs.append((freq, mag))

    freqs.sort(key=lambda x: x[1], reverse=True)
    return freqs[:top_n]


def ascii_spectrum(freq_mag_list, width=60, max_freq=4000):
    if not freq_mag_list:
        return ""

    bucket_size = max_freq / width
    buckets = [0.0] * width

    for freq, mag in freq_mag_list:
        if freq < max_freq:
            idx = min(int(freq / bucket_size), width - 1)
            buckets[idx] = max(buckets[idx], mag)

    max_mag = max(buckets) if max(buckets) > 0 else 1.0
    height = 10

    lines = []
    for row in range(height, 0, -1):
        line = ''
        threshold = (row / height) * max_mag
        for b in buckets:
            if b >= threshold:
                line += '#'
            else:
                line += ' '
        lines.append(line)

    freq_axis = ''
    for i in range(0, width, 10):
        label = f"{int(i * bucket_size)}"
        freq_axis += label
        if len(label) < 10:
            freq_axis += ' ' * (10 - len(label))
    freq_axis = freq_axis[:width]

    lines.append('-' * width)
    lines.append(freq_axis)

    return '\n'.join(lines)

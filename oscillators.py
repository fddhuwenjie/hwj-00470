import math
import struct
import random


SAMPLE_RATE = 44100
BITS = 16
MAX_AMPLITUDE = (1 << (BITS - 1)) - 1


def generate_wave(wave_type, frequency, duration, sample_rate=SAMPLE_RATE):
    n_samples = int(duration * sample_rate)
    samples = []

    if wave_type == "sine":
        for i in range(n_samples):
            t = i / sample_rate
            sample = math.sin(2 * math.pi * frequency * t)
            samples.append(sample)

    elif wave_type == "square":
        for i in range(n_samples):
            t = i / sample_rate
            phase = (frequency * t) % 1.0
            sample = 1.0 if phase < 0.5 else -1.0
            samples.append(sample)

    elif wave_type == "triangle":
        for i in range(n_samples):
            t = i / sample_rate
            phase = (frequency * t) % 1.0
            if phase < 0.25:
                sample = phase * 4.0
            elif phase < 0.75:
                sample = 2.0 - phase * 4.0
            else:
                sample = phase * 4.0 - 4.0
            samples.append(sample)

    elif wave_type == "sawtooth":
        for i in range(n_samples):
            t = i / sample_rate
            phase = (frequency * t) % 1.0
            sample = phase * 2.0 - 1.0
            samples.append(sample)

    elif wave_type == "noise":
        for i in range(n_samples):
            samples.append(random.uniform(-1.0, 1.0))

    else:
        raise ValueError(f"Unknown wave type: {wave_type}")

    return samples


class ADSR:
    def __init__(self, attack=0.01, decay=0.05, sustain=0.7, release=0.1, sample_rate=SAMPLE_RATE):
        self.attack = attack
        self.decay = decay
        self.sustain = sustain
        self.release = release
        self.sample_rate = sample_rate

    def apply(self, samples, note_duration):
        n = len(samples)
        result = [0.0] * n

        attack_samples = int(self.attack * self.sample_rate)
        decay_samples = int(self.decay * self.sample_rate)
        release_samples = int(self.release * self.sample_rate)
        sustain_samples = max(0, n - attack_samples - decay_samples - release_samples)

        idx = 0

        for i in range(attack_samples):
            if idx >= n:
                break
            env = i / max(1, attack_samples)
            result[idx] = samples[idx] * env
            idx += 1

        for i in range(decay_samples):
            if idx >= n:
                break
            env = 1.0 - (1.0 - self.sustain) * (i / max(1, decay_samples))
            result[idx] = samples[idx] * env
            idx += 1

        for i in range(sustain_samples):
            if idx >= n:
                break
            result[idx] = samples[idx] * self.sustain
            idx += 1

        for i in range(release_samples):
            if idx >= n:
                break
            env = self.sustain * (1.0 - i / max(1, release_samples))
            result[idx] = samples[idx] * env
            idx += 1

        return result


def samples_to_pcm(samples):
    pcm_data = bytearray()
    for s in samples:
        s = max(-1.0, min(1.0, s))
        val = int(s * MAX_AMPLITUDE)
        pcm_data.extend(struct.pack("<h", val))
    return bytes(pcm_data)


def pcm_to_samples(pcm_bytes):
    samples = []
    for i in range(0, len(pcm_bytes), 2):
        val = struct.unpack("<h", pcm_bytes[i:i+2])[0]
        samples.append(val / MAX_AMPLITUDE)
    return samples

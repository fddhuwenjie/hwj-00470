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


def generate_fm_wave(carrier_freq, duration, mod_ratio=2.0, mod_index=3.0,
                     mod_wave='sine', carrier_wave='sine', sample_rate=SAMPLE_RATE):
    n_samples = int(duration * sample_rate)
    samples = []

    mod_freq = carrier_freq * mod_ratio

    carrier_phase = 0.0
    mod_phase = 0.0

    carrier_phase_inc = 2 * math.pi * carrier_freq / sample_rate
    mod_phase_inc = 2 * math.pi * mod_freq / sample_rate

    for i in range(n_samples):
        if mod_wave == 'sine':
            mod_signal = math.sin(mod_phase)
        elif mod_wave == 'square':
            mod_signal = 1.0 if (mod_phase % (2 * math.pi)) < math.pi else -1.0
        elif mod_wave == 'triangle':
            p = (mod_phase % (2 * math.pi)) / (2 * math.pi)
            if p < 0.25:
                mod_signal = p * 4.0
            elif p < 0.75:
                mod_signal = 2.0 - p * 4.0
            else:
                mod_signal = p * 4.0 - 4.0
        elif mod_wave == 'sawtooth':
            p = (mod_phase % (2 * math.pi)) / (2 * math.pi)
            mod_signal = p * 2.0 - 1.0
        else:
            mod_signal = math.sin(mod_phase)

        freq_deviation = mod_freq * mod_index * mod_signal
        instant_carrier_freq = carrier_freq + freq_deviation
        carrier_phase_inc = 2 * math.pi * instant_carrier_freq / sample_rate

        carrier_phase += carrier_phase_inc
        mod_phase += mod_phase_inc

        if carrier_wave == 'sine':
            sample = math.sin(carrier_phase)
        elif carrier_wave == 'square':
            sample = 1.0 if (carrier_phase % (2 * math.pi)) < math.pi else -1.0
        elif carrier_wave == 'triangle':
            p = (carrier_phase % (2 * math.pi)) / (2 * math.pi)
            if p < 0.25:
                sample = p * 4.0
            elif p < 0.75:
                sample = 2.0 - p * 4.0
            else:
                sample = p * 4.0 - 4.0
        elif carrier_wave == 'sawtooth':
            p = (carrier_phase % (2 * math.pi)) / (2 * math.pi)
            sample = p * 2.0 - 1.0
        else:
            sample = math.sin(carrier_phase)

        samples.append(sample)

    return samples


def generate_layered_wave(frequency, duration, layer_config, sample_rate=SAMPLE_RATE):
    if not layer_config:
        return generate_wave('sine', frequency, duration, sample_rate)

    n_samples = int(duration * sample_rate)
    total_samples = [0.0] * n_samples
    total_mix = 0.0

    for layer in layer_config:
        wave_type = layer.get('wave_type', 'sine')
        mix = layer.get('mix', 1.0)
        detune_cents = layer.get('detune', 0.0)
        octave_shift = layer.get('octave', 0)

        detune_ratio = 2.0 ** (detune_cents / 1200.0)
        octave_ratio = 2.0 ** (octave_shift / 12.0)
        layer_freq = frequency * detune_ratio * octave_ratio

        layer_samples = generate_wave(wave_type, layer_freq, duration, sample_rate)

        for i in range(min(len(layer_samples), n_samples)):
            total_samples[i] += layer_samples[i] * mix

        total_mix += mix

    if total_mix > 0:
        total_samples = [s / total_mix for s in total_samples]

    return total_samples

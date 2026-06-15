import math
from oscillators import SAMPLE_RATE


class InstrumentPreset:
    def __init__(self, name, wave_types=None, adsr_params=None, effects=None,
                 fm_params=None, layer_config=None):
        self.name = name
        self.wave_types = wave_types or ['sine']
        self.adsr_params = adsr_params or {'attack': 0.01, 'decay': 0.05, 'sustain': 0.7, 'release': 0.1}
        self.effects = effects or {}
        self.fm_params = fm_params
        self.layer_config = layer_config

    def get_adsr_kwargs(self):
        return dict(self.adsr_params)

    def is_fm(self):
        return self.fm_params is not None


INSTRUMENT_PRESETS = {
    'piano': InstrumentPreset(
        name='piano',
        wave_types=['triangle', 'sine'],
        adsr_params={'attack': 0.002, 'decay': 0.25, 'sustain': 0.55, 'release': 0.3},
        effects={'lowpass': 4000.0},
        layer_config=[
            {'wave_type': 'triangle', 'mix': 0.7, 'detune': 0.0},
            {'wave_type': 'sine', 'mix': 0.3, 'detune': 0.0},
        ]
    ),
    'electric_guitar': InstrumentPreset(
        name='electric_guitar',
        wave_types=['sawtooth', 'square'],
        adsr_params={'attack': 0.005, 'decay': 0.1, 'sustain': 0.8, 'release': 0.25},
        effects={'distortion': True, 'lowpass': 3000.0, 'echo': {'delay': 0.2, 'decay': 0.3}},
        layer_config=[
            {'wave_type': 'sawtooth', 'mix': 0.6, 'detune': 0.0},
            {'wave_type': 'square', 'mix': 0.4, 'detune': 3.0},
        ]
    ),
    'bass': InstrumentPreset(
        name='bass',
        wave_types=['sawtooth', 'sine'],
        adsr_params={'attack': 0.008, 'decay': 0.15, 'sustain': 0.85, 'release': 0.2},
        effects={'lowpass': 800.0},
        layer_config=[
            {'wave_type': 'sine', 'mix': 0.6, 'detune': 0.0},
            {'wave_type': 'sawtooth', 'mix': 0.4, 'detune': 0.0},
        ]
    ),
    'strings': InstrumentPreset(
        name='strings',
        wave_types=['sawtooth', 'triangle'],
        adsr_params={'attack': 0.15, 'decay': 0.2, 'sustain': 0.85, 'release': 0.5},
        effects={'vibrato': {'freq': 5.5, 'depth': 15}, 'reverb': {'room': 0.6, 'decay': 0.7}},
        layer_config=[
            {'wave_type': 'sawtooth', 'mix': 0.5, 'detune': -3.0},
            {'wave_type': 'sawtooth', 'mix': 0.3, 'detune': 3.0},
            {'wave_type': 'triangle', 'mix': 0.2, 'detune': 0.0},
        ]
    ),
    'organ': InstrumentPreset(
        name='organ',
        wave_types=['sine', 'sine', 'sine', 'sine'],
        adsr_params={'attack': 0.01, 'decay': 0.02, 'sustain': 0.95, 'release': 0.08},
        effects={'reverb': {'room': 0.4, 'decay': 0.5}},
        layer_config=[
            {'wave_type': 'sine', 'mix': 0.4, 'detune': 0.0, 'octave': 0},
            {'wave_type': 'sine', 'mix': 0.3, 'detune': 0.0, 'octave': 12},
            {'wave_type': 'sine', 'mix': 0.2, 'detune': 0.0, 'octave': -12},
            {'wave_type': 'sine', 'mix': 0.1, 'detune': 0.0, 'octave': 7},
        ]
    ),
    'lead': InstrumentPreset(
        name='lead',
        wave_types=['square', 'sawtooth'],
        adsr_params={'attack': 0.005, 'decay': 0.08, 'sustain': 0.8, 'release': 0.2},
        effects={'vibrato': {'freq': 6.0, 'depth': 8}, 'distortion': True},
        layer_config=[
            {'wave_type': 'square', 'mix': 0.6, 'detune': 0.0},
            {'wave_type': 'sawtooth', 'mix': 0.4, 'detune': 5.0},
        ]
    ),
    'pad': InstrumentPreset(
        name='pad',
        wave_types=['sine', 'triangle'],
        adsr_params={'attack': 0.8, 'decay': 0.4, 'sustain': 0.7, 'release': 1.2},
        effects={'reverb': {'room': 0.8, 'decay': 0.85}, 'lowpass': 2500.0},
        layer_config=[
            {'wave_type': 'sine', 'mix': 0.5, 'detune': -7.0},
            {'wave_type': 'sine', 'mix': 0.3, 'detune': 7.0},
            {'wave_type': 'triangle', 'mix': 0.2, 'detune': 0.0},
        ]
    ),
    'drums': InstrumentPreset(
        name='drums',
        wave_types=['noise', 'sine'],
        adsr_params={'attack': 0.001, 'decay': 0.08, 'sustain': 0.0, 'release': 0.05},
        effects={},
        layer_config=[
            {'wave_type': 'noise', 'mix': 0.6, 'detune': 0.0},
            {'wave_type': 'sine', 'mix': 0.4, 'detune': 0.0},
        ]
    ),
}


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


class FMOperator:
    def __init__(self, frequency, wave_type='sine', level=1.0, sample_rate=SAMPLE_RATE):
        self.frequency = frequency
        self.wave_type = wave_type
        self.level = level
        self.sample_rate = sample_rate
        self.phase = 0.0

    def reset(self):
        self.phase = 0.0

    def generate_sample(self, freq_modulation=0.0):
        instant_freq = self.frequency + freq_modulation
        phase_inc = 2 * math.pi * instant_freq / self.sample_rate
        self.phase += phase_inc

        if self.wave_type == 'sine':
            return self.level * math.sin(self.phase)
        elif self.wave_type == 'square':
            return self.level * (1.0 if (self.phase % (2 * math.pi)) < math.pi else -1.0)
        elif self.wave_type == 'triangle':
            p = (self.phase % (2 * math.pi)) / (2 * math.pi)
            if p < 0.25:
                return self.level * (p * 4.0)
            elif p < 0.75:
                return self.level * (2.0 - p * 4.0)
            else:
                return self.level * (p * 4.0 - 4.0)
        elif self.wave_type == 'sawtooth':
            p = (self.phase % (2 * math.pi)) / (2 * math.pi)
            return self.level * (p * 2.0 - 1.0)
        return self.level * math.sin(self.phase)


def create_fm_instrument(mod_ratio=2.0, mod_index=3.0, carrier_wave='sine', mod_wave='sine'):
    return InstrumentPreset(
        name=f'fm_{mod_ratio}_{mod_index}',
        wave_types=[carrier_wave],
        adsr_params={'attack': 0.01, 'decay': 0.1, 'sustain': 0.7, 'release': 0.2},
        effects={},
        fm_params={
            'mod_ratio': mod_ratio,
            'mod_index': mod_index,
            'carrier_wave': carrier_wave,
            'mod_wave': mod_wave,
        }
    )


def get_instrument(name):
    if name in INSTRUMENT_PRESETS:
        return INSTRUMENT_PRESETS[name]

    if name.startswith('fm') or name.startswith('FM'):
        parts = name.split(':')
        mod_ratio = 2.0
        mod_index = 3.0
        carrier_wave = 'sine'
        mod_wave = 'sine'

        if len(parts) >= 2:
            try:
                mod_ratio = float(parts[1])
            except ValueError:
                pass
        if len(parts) >= 3:
            try:
                mod_index = float(parts[2])
            except ValueError:
                pass
        if len(parts) >= 4:
            carrier_wave = parts[3]
        if len(parts) >= 5:
            mod_wave = parts[4]

        return create_fm_instrument(mod_ratio, mod_index, carrier_wave, mod_wave)

    return INSTRUMENT_PRESETS['piano']


def list_instruments():
    return list(INSTRUMENT_PRESETS.keys())

import math


NOTE_SEMITONES = {
    'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11
}


ACCIDENTALS = {
    '#': 1, 'b': -1, '': 0
}


def note_name_to_midi(note_name):
    note_name = note_name.strip()
    if not note_name:
        return None

    root = note_name[0].upper()
    if root not in NOTE_SEMITONES:
        return None

    accidental = ''
    octave_idx = 1
    if len(note_name) > 1 and note_name[1] in ('#', 'b'):
        accidental = note_name[1]
        octave_idx = 2

    octave_str = note_name[octave_idx:]
    if not octave_str:
        octave = 4
    else:
        try:
            octave = int(octave_str)
        except ValueError:
            return None

    semitones = NOTE_SEMITONES[root] + ACCIDENTALS[accidental]
    midi = (octave + 1) * 12 + semitones
    return midi


def midi_to_frequency(midi_note):
    if midi_note is None:
        return 0.0
    return 440.0 * (2.0 ** ((midi_note - 69) / 12.0))


def note_name_to_frequency(note_name):
    midi = note_name_to_midi(note_name)
    return midi_to_frequency(midi)


JIANPU_TO_MIDI_OFFSET = {
    '1': 0, '2': 2, '3': 4, '4': 5, '5': 7, '6': 9, '7': 11
}


def jianpu_to_frequency(jianpu, base_octave=4):
    jianpu = jianpu.strip()
    if not jianpu or jianpu == '0' or jianpu.lower() == 'r':
        return 0.0

    base_midi = (base_octave + 1) * 12
    core = jianpu[0]

    if core not in JIANPU_TO_MIDI_OFFSET:
        return 0.0

    midi = base_midi + JIANPU_TO_MIDI_OFFSET[core]

    for ch in jianpu[1:]:
        if ch == '.':
            midi += 12
        elif ch == ',':
            midi -= 12
        elif ch == '#':
            midi += 1
        elif ch == 'b':
            midi -= 1

    return midi_to_frequency(midi)


def jianpu_to_midi(jianpu, base_octave=4):
    jianpu = jianpu.strip()
    if not jianpu or jianpu == '0' or jianpu.lower() == 'r':
        return None

    base_midi = (base_octave + 1) * 12
    core = jianpu[0]

    if core not in JIANPU_TO_MIDI_OFFSET:
        return None

    midi = base_midi + JIANPU_TO_MIDI_OFFSET[core]

    for ch in jianpu[1:]:
        if ch == '.':
            midi += 12
        elif ch == ',':
            midi -= 12
        elif ch == '#':
            midi += 1
        elif ch == 'b':
            midi -= 1

    return midi


def get_note_duration(value_type, bpm):
    beat_duration = 60.0 / bpm
    durations = {
        'whole': 4.0 * beat_duration,
        'half': 2.0 * beat_duration,
        'quarter': 1.0 * beat_duration,
        'eighth': 0.5 * beat_duration,
        'sixteenth': 0.25 * beat_duration,
        'whole_dotted': 6.0 * beat_duration,
        'half_dotted': 3.0 * beat_duration,
        'quarter_dotted': 1.5 * beat_duration,
        'eighth_dotted': 0.75 * beat_duration,
        'sixteenth_dotted': 0.375 * beat_duration,
    }
    return durations.get(value_type, 1.0 * beat_duration)


def parse_duration_suffix(suffix):
    base = 'quarter'
    dotted = False

    if suffix == '1':
        base = 'whole'
    elif suffix == '2':
        base = 'half'
    elif suffix == '4':
        base = 'quarter'
    elif suffix == '8':
        base = 'eighth'
    elif suffix == '16':
        base = 'sixteenth'
    elif suffix.endswith('.'):
        dotted = True
        core = suffix[:-1]
        if core == '1':
            base = 'whole'
        elif core == '2':
            base = 'half'
        elif core == '4':
            base = 'quarter'
        elif core == '8':
            base = 'eighth'
        elif core == '16':
            base = 'sixteenth'

    if dotted:
        return base + '_dotted'
    return base


DYNAMICS = {
    'ppp': 0.15,
    'pp': 0.25,
    'p': 0.4,
    'mp': 0.55,
    'mf': 0.7,
    'f': 0.85,
    'ff': 0.95,
    'fff': 1.0,
}


def get_dynamics_volume(dyn):
    return DYNAMICS.get(dyn.lower(), 0.7)

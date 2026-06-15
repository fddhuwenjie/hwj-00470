import re
from notes import note_name_to_midi, midi_to_frequency, note_name_to_frequency


CHORD_INTERVALS = {
    'maj': [0, 4, 7],
    '': [0, 4, 7],
    'M': [0, 4, 7],
    'min': [0, 3, 7],
    'm': [0, 3, 7],
    '-': [0, 3, 7],
    'dim': [0, 3, 6],
    'aug': [0, 4, 8],
    '+': [0, 4, 8],
    '7': [0, 4, 7, 10],
    'dom7': [0, 4, 7, 10],
    'maj7': [0, 4, 7, 11],
    'M7': [0, 4, 7, 11],
    'min7': [0, 3, 7, 10],
    'm7': [0, 3, 7, 10],
    '-7': [0, 3, 7, 10],
    'minmaj7': [0, 3, 7, 11],
    'mM7': [0, 3, 7, 11],
    'dim7': [0, 3, 6, 9],
    'm7b5': [0, 3, 6, 10],
    'half-dim7': [0, 3, 6, 10],
    'sus2': [0, 2, 7],
    'sus4': [0, 5, 7],
    'add9': [0, 4, 7, 14],
    '6': [0, 4, 7, 9],
    'maj6': [0, 4, 7, 9],
    'min6': [0, 3, 7, 9],
    'm6': [0, 3, 7, 9],
    '9': [0, 4, 7, 10, 14],
    'maj9': [0, 4, 7, 11, 14],
    'M9': [0, 4, 7, 11, 14],
    'min9': [0, 3, 7, 10, 14],
    'm9': [0, 3, 7, 10, 14],
}


CHORD_PATTERN = re.compile(
    r'^([A-Ga-g])([#b]?)((?:maj|min|dim|aug|sus|add|dom|half-dim|mM|m|M|-|\+)?(?:\d)?(?:7|9|b5)?(?:maj|min|dim|aug|sus|add)?\d*)$'
)


def parse_chord_name(chord_name):
    chord_name = chord_name.strip()
    if not chord_name:
        return None

    m = re.match(r'^([A-Ga-g])([#b]?)(.*)$', chord_name)
    if not m:
        return None

    root_letter = m.group(1).upper()
    accidental = m.group(2)
    quality_str = m.group(3)

    semitone_map = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
    accidental_map = {'#': 1, 'b': -1, '': 0}

    root_semitone = semitone_map[root_letter] + accidental_map.get(accidental, 0)

    intervals = None
    if quality_str in CHORD_INTERVALS:
        intervals = CHORD_INTERVALS[quality_str]
    else:
        for q in sorted(CHORD_INTERVALS.keys(), key=len, reverse=True):
            if q and quality_str.startswith(q):
                intervals = CHORD_INTERVALS[q]
                break
        if intervals is None:
            intervals = CHORD_INTERVALS['maj']

    return {
        'root': root_letter + accidental,
        'root_semitone': root_semitone,
        'quality': quality_str if quality_str else 'maj',
        'intervals': intervals
    }


def chord_to_midi_notes(chord_name, octave=4):
    parsed = parse_chord_name(chord_name)
    if parsed is None:
        return []

    base_midi = (octave + 1) * 12 + parsed['root_semitone']
    midi_notes = [base_midi + interval for interval in parsed['intervals']]
    return midi_notes


def chord_to_frequencies(chord_name, octave=4):
    midi_notes = chord_to_midi_notes(chord_name, octave)
    return [midi_to_frequency(m) for m in midi_notes]


def generate_arpeggio(midi_notes, pattern='up', speed=1.0, note_duration=0.25):
    if not midi_notes:
        return []

    if pattern == 'up':
        order = list(range(len(midi_notes)))
    elif pattern == 'down':
        order = list(range(len(midi_notes) - 1, -1, -1))
    elif pattern == 'alternate':
        order = list(range(len(midi_notes))) + list(range(len(midi_notes) - 2, 0, -1))
    else:
        order = list(range(len(midi_notes)))

    events = []
    step_duration = note_duration / max(0.1, speed)
    for idx in order:
        events.append({
            'midi_note': midi_notes[idx],
            'frequency': midi_to_frequency(midi_notes[idx]),
            'duration': step_duration
        })
    return events


class ChordEvent:
    def __init__(self, frequencies=None, midi_notes=None, duration=1.0, volume=0.7,
                 arpeggio=False, arpeggio_pattern='up', arpeggio_speed=1.0):
        self.frequencies = frequencies or []
        self.midi_notes = midi_notes or []
        self.duration = duration
        self.volume = volume
        self.arpeggio = arpeggio
        self.arpeggio_pattern = arpeggio_pattern
        self.arpeggio_speed = arpeggio_speed

    def is_arpeggio(self):
        return self.arpeggio

    def get_arpeggio_events(self):
        if not self.arpeggio:
            return []
        return generate_arpeggio(
            self.midi_notes,
            pattern=self.arpeggio_pattern,
            speed=self.arpeggio_speed,
            note_duration=self.duration
        )


def chord_from_name(chord_name, octave=4, duration=1.0, volume=0.7,
                    arpeggio=False, arpeggio_pattern='up', arpeggio_speed=1.0):
    midi_notes = chord_to_midi_notes(chord_name, octave)
    freqs = chord_to_frequencies(chord_name, octave)
    return ChordEvent(
        frequencies=freqs,
        midi_notes=midi_notes,
        duration=duration,
        volume=volume,
        arpeggio=arpeggio,
        arpeggio_pattern=arpeggio_pattern,
        arpeggio_speed=arpeggio_speed
    )


def parse_bracket_chord(chord_str, current_octave=4):
    chord_str = chord_str.strip()
    if chord_str.startswith('[') and chord_str.endswith(']'):
        chord_str = chord_str[1:-1].strip()

    note_tokens = chord_str.split()
    frequencies = []
    midi_notes = []

    for token in note_tokens:
        token = token.strip()
        if not token:
            continue
        freq = note_name_to_frequency(token)
        midi = note_name_to_midi(token)
        if freq > 0 and midi is not None:
            frequencies.append(freq)
            midi_notes.append(midi)

    return frequencies, midi_notes

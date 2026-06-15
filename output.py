import struct
import wave
from oscillators import SAMPLE_RATE, BITS, samples_to_pcm


def write_wav_mono(filepath, samples, sample_rate=SAMPLE_RATE, bits=BITS):
    pcm_data = samples_to_pcm(samples)

    n_channels = 1
    sample_width = bits // 8
    n_frames = len(samples)
    byte_rate = sample_rate * n_channels * sample_width
    block_align = n_channels * sample_width

    with wave.open(filepath, 'wb') as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.setnframes(n_frames)
        wf.writeframes(pcm_data)


def write_wav_stereo(filepath, left_samples, right_samples, sample_rate=SAMPLE_RATE, bits=BITS):
    if len(left_samples) != len(right_samples):
        n = min(len(left_samples), len(right_samples))
        left_samples = left_samples[:n]
        right_samples = right_samples[:n]

    pcm_data = bytearray()
    for l, r in zip(left_samples, right_samples):
        l = max(-1.0, min(1.0, l))
        r = max(-1.0, min(1.0, r))
        l_val = int(l * ((1 << (bits - 1)) - 1))
        r_val = int(r * ((1 << (bits - 1)) - 1))
        pcm_data.extend(struct.pack("<h", l_val))
        pcm_data.extend(struct.pack("<h", r_val))

    n_channels = 2
    sample_width = bits // 8
    n_frames = len(left_samples)
    byte_rate = sample_rate * n_channels * sample_width
    block_align = n_channels * sample_width

    with wave.open(filepath, 'wb') as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.setnframes(n_frames)
        wf.writeframes(bytes(pcm_data))


def write_wav(filepath, samples, sample_rate=SAMPLE_RATE, bits=BITS, stereo=False):
    if stereo and isinstance(samples, tuple) and len(samples) == 2:
        left, right = samples
        write_wav_stereo(filepath, left, right, sample_rate, bits)
    else:
        write_wav_mono(filepath, samples, sample_rate, bits)


def _midi_var_length(value):
    result = bytearray()
    buffer = value & 0x7F
    value >>= 7
    while value > 0:
        buffer <<= 8
        buffer |= ((value & 0x7F) | 0x80)
        value >>= 7
    while True:
        result.append(buffer & 0xFF)
        if buffer & 0x80:
            buffer >>= 8
        else:
            break
    return bytes(result)


def write_midi(filepath, tracks_data, bpm=120, ticks_per_quarter=480):
    microseconds_per_quarter = int(60000000 / bpm)

    with open(filepath, 'wb') as f:
        f.write(b'MThd')
        f.write(struct.pack('>I', 6))
        f.write(struct.pack('>H', 1))
        f.write(struct.pack('>H', len(tracks_data)))
        f.write(struct.pack('>H', ticks_per_quarter))

        for track_idx, track in enumerate(tracks_data):
            track_data = bytearray()

            if track_idx == 0:
                track_data.extend(_midi_var_length(0))
                track_data.append(0xFF)
                track_data.append(0x51)
                track_data.append(0x03)
                track_data.extend(struct.pack('>I', microseconds_per_quarter)[1:])

            current_time = 0
            active_notes = {}

            sorted_events = sorted(track.events, key=lambda e: getattr(e, 'start_time', 0))

            for event in track.events:
                if hasattr(event, 'start_time'):
                    start_ticks = int(event.start_time * bpm * ticks_per_quarter / 60.0)
                else:
                    start_ticks = current_time

                if hasattr(event, 'duration'):
                    duration_ticks = int(event.duration * bpm * ticks_per_quarter / 60.0)
                else:
                    duration_ticks = ticks_per_quarter

                if event.is_rest:
                    current_time = start_ticks + duration_ticks
                    continue

                midi_note = event.midi_note if event.midi_note is not None else 60
                velocity = int(getattr(event, 'volume', 0.7) * 127)
                velocity = max(0, min(127, velocity))

                delta_time = start_ticks - current_time
                track_data.extend(_midi_var_length(max(0, delta_time)))
                track_data.append(0x90 | (track_idx % 16))
                track_data.append(midi_note)
                track_data.append(velocity)
                current_time = start_ticks

                end_ticks = start_ticks + duration_ticks
                delta_time = end_ticks - current_time
                track_data.extend(_midi_var_length(max(0, delta_time)))
                track_data.append(0x80 | (track_idx % 16))
                track_data.append(midi_note)
                track_data.append(0)
                current_time = end_ticks

            track_data.extend(_midi_var_length(0))
            track_data.append(0xFF)
            track_data.append(0x2F)
            track_data.append(0x00)

            f.write(b'MTrk')
            f.write(struct.pack('>I', len(track_data)))
            f.write(bytes(track_data))

from effects import apply_gain, apply_pan


class Track:
    def __init__(self, name="Track", wave_type="sine", volume=0.8, pan=0.0, muted=False, solo=False):
        self.name = name
        self.wave_type = wave_type
        self.volume = volume
        self.pan = pan
        self.muted = muted
        self.solo = solo
        self.samples = []

    def set_samples(self, samples):
        self.samples = list(samples)

    def get_panned_samples(self):
        if self.muted:
            n = len(self.samples)
            return [0.0] * n, [0.0] * n

        gain_samples = apply_gain(self.samples, self.volume)
        return apply_pan(gain_samples, self.pan)


class Mixer:
    def __init__(self):
        self.tracks = []

    def add_track(self, track):
        self.tracks.append(track)

    def get_track(self, name):
        for t in self.tracks:
            if t.name == name:
                return t
        return None

    def mix(self, force_length=None):
        if not self.tracks:
            return [], []

        has_solo = any(t.solo for t in self.tracks)

        active_tracks = []
        for t in self.tracks:
            if t.solo or (not has_solo and not t.muted):
                active_tracks.append(t)

        if not active_tracks:
            return [], []

        if force_length is not None:
            max_len = force_length
        else:
            max_len = max(len(t.samples) for t in active_tracks)

        left_mix = [0.0] * max_len
        right_mix = [0.0] * max_len

        for t in active_tracks:
            left, right = t.get_panned_samples()
            for i in range(min(len(left), max_len)):
                left_mix[i] += left[i]
                right_mix[i] += right[i]

        max_val = 0.0
        for i in range(max_len):
            max_val = max(max_val, abs(left_mix[i]), abs(right_mix[i]))

        if max_val > 1.0:
            scale = 1.0 / max_val
            left_mix = [s * scale for s in left_mix]
            right_mix = [s * scale for s in right_mix]

        return left_mix, right_mix

    def mix_mono(self, force_length=None):
        left, right = self.mix(force_length)
        if not left:
            return []
        mono = [(l + r) * 0.5 for l, r in zip(left, right)]
        return mono

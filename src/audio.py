import pygame
import numpy as np

# Pre-init must happen before pygame.init() is called in the main loop
pygame.mixer.pre_init(44100, -16, 2, 256)

class Audio:
    def __init__(self):
        self.enabled = True
        self.muted = False
        self.sfx = {}
        self.pickup_idx = 0
        self.last_pickup_time = 0.0
        
        try:
            pygame.mixer.init()
            self._build()
        except Exception:
            self.enabled = False

    def _make(self, samples):
        samples = np.clip(samples, -1, 1)
        stereo = np.column_stack([samples, samples])
        arr = (stereo * 32767).astype(np.int16)
        return pygame.sndarray.make_sound(arr)

    def _build(self):
        sr = 44100
        
        d = 0.15; t = np.linspace(0, d, int(sr * d), endpoint=False)
        env = np.exp(-t * 15)
        freq = 600 - 400 * (t / d)
        self.sfx['dash'] = self._make(0.3 * env * np.sin(2 * np.pi * freq * t))
        
        d = 0.05; t = np.linspace(0, d, int(sr * d), endpoint=False)
        env = np.exp(-t * 40)
        self.sfx['hit'] = self._make(0.25 * env * np.sin(2 * np.pi * 800 * t))
        
        d = 0.3; t = np.linspace(0, d, int(sr * d), endpoint=False)
        env = np.exp(-t * 8)
        noise = np.random.uniform(-1, 1, len(t))
        self.sfx['explode'] = self._make(0.3 * env * noise + 0.2 * env * np.sin(2 * np.pi * 60 * t))
        
        d = 0.5; t = np.linspace(0, d, int(sr * d), endpoint=False)
        env = np.exp(-t * 3) * (1 - np.exp(-t * 50))
        freq = 400 + 800 * (t / d)
        self.sfx['levelup'] = self._make(0.3 * env * np.sin(2 * np.pi * freq * t))
        
        self.sfx['pickup'] = []
        for i in range(5):
            f = 800 + i * 150
            d = 0.08; t = np.linspace(0, d, int(sr * d), endpoint=False)
            env = np.exp(-t * 25)
            self.sfx['pickup'].append(self._make(0.15 * env * np.sin(2 * np.pi * f * t)))

    def play(self, name, vol=1.0):
        if self.enabled and not self.muted and name in self.sfx:
            s = self.sfx[name]
            if isinstance(s, list):
                s = s[self.pickup_idx]
                self.pickup_idx = (self.pickup_idx + 1) % len(self.sfx[name])
            s.set_volume(vol)
            s.play()

    def toggle_mute(self):
        self.muted = not self.muted

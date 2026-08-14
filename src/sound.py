import os
import random
import sys
import pygame


class SoundManager:
    """Load and play audio without overwhelming the browser mixer."""

    WEB_AUDIO_FORMAT = (24000, -16, 2, 2048)
    SFX_COOLDOWNS_MS = {
        "kick": 180,
        "walk": 120,
        "whistle": 300,
        "impact": 120,
    }

    def __init__(self, audio_path="assets/audio", master_volume=1.0):
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.is_web = sys.platform == "emscripten"
        # Pygbag's SDL/WebAudio path is most reliable with 24 kHz OGGs. Keep
        # the original higher-quality files for desktop, while retaining the
        # broadly supported Vorbis codec in the web copies.
        if self.is_web:
            audio_path = os.path.join(audio_path, "web")
        self.path = os.path.join(base_path, audio_path)
        self.sounds = {}
        self.impacts = []
        self.chants = []
        self.last_impact_time = -self.SFX_COOLDOWNS_MS["impact"]
        self.last_played = {}
        self.audio_enabled = False
        self.is_paused = False
        self.crowd_channel = None
        self.master_volume = master_volume

        # ``pre_init`` in main.py handles the normal path. This fallback keeps
        # SoundManager safe when a match is started directly during development.
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init(*self.WEB_AUDIO_FORMAT)
            except pygame.error as error:
                print(f"Warning: Audio is disabled ({error}).")

        if not pygame.mixer.get_init():
            return

        # Reserve one channel for the long-running crowd track. Short effects
        # use the remaining channels and cannot interrupt it.
        pygame.mixer.set_num_channels(8)
        pygame.mixer.set_reserved(1)
        self.crowd_channel = pygame.mixer.Channel(0)
        self.audio_enabled = True
        self.load_assets()

    def load_assets(self):
        try:
            self.sounds["kick"] = pygame.mixer.Sound(os.path.join(self.path, "kick.ogg"))
            self.sounds["walk"] = pygame.mixer.Sound(os.path.join(self.path, "walk.ogg"))
            self.sounds["whistle"] = pygame.mixer.Sound(os.path.join(self.path, "whistle.ogg"))
                        
            # Load impacts
            for i in range(5):
                file_path = os.path.join(self.path, f"impact{i}.ogg")
                self.impacts.append(pygame.mixer.Sound(file_path))
                        
            self.chants = [
                pygame.mixer.Sound(os.path.join(self.path, "chant0.ogg")),
                pygame.mixer.Sound(os.path.join(self.path, "chant1.ogg")),
                pygame.mixer.Sound(os.path.join(self.path, "chant2.ogg"))
            ]
        except pygame.error as error:
            self.audio_enabled = False
            self.sounds.clear()
            self.impacts.clear()
            self.chants.clear()
            print(f"Warning: Could not load audio files ({error}).")

    def update_ambient_chants(self):
        # Do not start a new chant while the match is paused. Existing audio is
        # paused separately by set_paused(), preserving its playback position.
        if (self.audio_enabled and not self.is_paused and self.crowd_channel
                and not self.crowd_channel.get_busy() and self.chants):
            next_chant = random.choice(self.chants)
            self.crowd_channel.set_volume(0.3*self.master_volume)
            self.crowd_channel.play(next_chant)

    def play_sfx(self, name, volume=1.0):
        if not self.audio_enabled or self.is_paused or name not in self.sounds:
            return False

        now = pygame.time.get_ticks()
        cooldown = self.SFX_COOLDOWNS_MS.get(name, 0)
        if now - self.last_played.get(name, -cooldown) < cooldown:
            return False
        channel = self.sounds[name].play()
        if channel is None:
            return False
        channel.set_volume(max(0.0, min((volume*self.master_volume), 1.0)))
        self.last_played[name] = now
        return True

    def play_impact(self):
        if not self.audio_enabled or self.is_paused or not self.impacts:
            return False

        now = pygame.time.get_ticks()
        cooldown = self.SFX_COOLDOWNS_MS["impact"]
        if now - self.last_impact_time < cooldown:
            return False

        channel = random.choice(self.impacts).play()
        if channel is None:
            return False
        channel.set_volume(0.6*self.master_volume)
        self.last_impact_time = now
        return True

    def set_paused(self, paused):
        """Pause or resume every mixer channel without resetting playback."""
        if not self.audio_enabled or paused == self.is_paused:
            return

        # mixer.pause() affects both the crowd channel and active sound effects,
        # so resume returns the match's audio exactly where it was stopped.
        if paused:
            pygame.mixer.pause()
        else:
            pygame.mixer.unpause()
        self.is_paused = paused

    def stop_all(self):
        """Clear match audio before returning to the menu or starting a new match."""
        if not self.audio_enabled:
            return

        # Unpause before the next match; otherwise pygame keeps the global
        # mixer paused even after this SoundManager has been discarded.
        pygame.mixer.stop()
        pygame.mixer.unpause()
        self.is_paused = False

import os
import random
import pygame

class SoundManager:
    def __init__(self, audio_path="assets/audio"):
        # Get base path relative to project root
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.path = os.path.join(base_path, audio_path)
        self.sounds = {}
        self.impacts = []
        self.chants = []
        
        # Initialize mixer
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except pygame.error as error:
                print(f"Warning: Audio is disabled ({error}).")

        self.load_assets()    
        # Channel for the chants
        self.crowd_channel = pygame.mixer.Channel(0) if pygame.mixer.get_init() else None

    def load_assets(self):
        # Load main SFX
        try:
            self.sounds["kick"] = pygame.mixer.Sound(os.path.join(self.path, "kick.ogg"))
            self.sounds["walk"] = pygame.mixer.Sound(os.path.join(self.path, "walk.ogg"))
            self.sounds["whistle"] = pygame.mixer.Sound(os.path.join(self.path, "whistle.ogg"))
            
            # Load impact sfx
            for i in range(5):
                file_path = os.path.join(self.path, f"impact{i}.ogg")
                self.impacts.append(pygame.mixer.Sound(file_path))
                
            # Load chants sfx
            self.chants = [
                os.path.join(self.path, "chant0.ogg"),
                os.path.join(self.path, "chant1.ogg"),
                os.path.join(self.path, "chant2.ogg")
            ]
        except Exception as e:
            print(f"Warning: Could not load some audio files. Error: {e}")

    def play_sfx(self, name, volume=1.0):
        if name in self.sounds:
            self.sounds[name].set_volume(volume)
            self.sounds[name].play()

    def play_impact(self):
        if self.impacts:
            snd = random.choice(self.impacts)
            snd.set_volume(0.6)
            snd.play()

    def update_ambient_chants(self):
        # Random chants in random order by checking if the channel is empty or not.
        if self.crowd_channel and not self.crowd_channel.get_busy() and self.chants:
            next_chant = pygame.mixer.Sound(random.choice(self.chants))
            self.crowd_channel.set_volume(0.4) # Background level
            self.crowd_channel.play(next_chant)

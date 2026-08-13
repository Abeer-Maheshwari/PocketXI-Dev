import os
import random
import pygame

class SoundManager:
    def __init__(self, audio_path="assets/audio"):
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.path = os.path.join(base_path, audio_path)
        self.sounds = {}
        self.impacts = []
        self.chants = []
        self.last_impact_time = 0

        # Initialize mixer with MONO (channels=1) to stop alternating buffer skips
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=1024)
            except pygame.error as error:
                print(f"Warning: Audio is disabled ({error}).")
                
        self.load_assets()
        
        if pygame.mixer.get_init():
            pygame.mixer.set_num_channels(8)
            self.crowd_channel = pygame.mixer.Channel(0)
        else:
            self.crowd_channel = None

    

    def load_assets(self):
        try:
            self.sounds["kick"] = pygame.mixer.Sound(os.path.join(self.path, "kick.ogg"))
            self.sounds["walk"] = pygame.mixer.Sound(os.path.join(self.path, "walk.ogg"))
            self.sounds["whistle"] = pygame.mixer.Sound(os.path.join(self.path, "whistle.ogg"))
                        
            # Load impacts
            for i in range(5):
                file_path = os.path.join(self.path, f"impact{i}.ogg")
                self.impacts.append(pygame.mixer.Sound(file_path))
                        
            # PRE-LOAD chants into Sound objects instead of file paths
            self.chants = [
                pygame.mixer.Sound(os.path.join(self.path, "chant0.ogg")),
                pygame.mixer.Sound(os.path.join(self.path, "chant1.ogg")),
                pygame.mixer.Sound(os.path.join(self.path, "chant2.ogg"))
            ]
        except Exception as e:
            print(f"Warning: Could not load some audio files. Error: {e}")

    def update_ambient_chants(self):
        # Play pre-loaded chant objects directly
        '''if self.crowd_channel and not self.crowd_channel.get_busy() and self.chants:
            next_chant = random.choice(self.chants)
            self.crowd_channel.set_volume(0.3)
            self.crowd_channel.play(next_chant)
'''
    def play_sfx(self, name, volume=1.0):
        '''if name in self.sounds:
            self.sounds[name].set_volume(volume)
            self.sounds[name].play()'''

    def play_impact(self):
        '''if self.impacts:
            snd = random.choice(self.impacts)
            snd.set_volume(0.6)
            snd.play()'''

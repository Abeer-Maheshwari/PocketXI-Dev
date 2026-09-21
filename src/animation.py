import os
import pygame


class AnimationManager:
    # Loads and caches sprite images
    def __init__(self, asset_dir):
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.asset_dir = os.path.join(base_path, asset_dir)
        self.images = {}

        self._loadAllAssets()
    
    def _loadAllAssets(self):
        # Player sprites
        self.images["p1_body"] = self._loadImage("players/red/red_body.png")
        self.images["p1_foot"] = self._loadImage("players/red/red_foot.png")
        self.images["p2_body"] = self._loadImage("players/blue/blue_body.png")
        self.images["p2_foot"] = self._loadImage("players/blue/blue_foot.png")
        
        # Pitch and ball
        self.images["grass"] = self._loadImage("pitch/grass.png")
        self.images["ball"] = self._loadImage("pitch/ball.png")
        
    def _loadImage(self, filename):
        filepath = os.path.join(self.asset_dir, filename)
        try:
            return pygame.image.load(filepath).convert_alpha()
        except FileNotFoundError:
            print(f"Warning: Missing sprite {filepath}")
            # Placeholder square if image is missing
            fallback = pygame.Surface((40, 40), pygame.SRCALPHA)
            pygame.draw.rect(fallback, "magenta", (0, 0, 40, 40))
            return fallback
        
    def get_image(self, image_id):
        return self.images.get(image_id)


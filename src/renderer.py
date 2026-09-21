import pygame


class PitchRenderer:
    # Renders the football pitch, tiled grass, and lines
    def __init__(self, screen_width, screen_height):
        self.width = screen_width
        self.height = screen_height
        
        self.line_color = (240, 255, 240)
        self.line_thickness = 4
    
    def drawBackground(self, screen, asset_manager):
        self._tileGrass(screen, asset_manager)
        self.drawPitchMarkings(screen)

    def _tileGrass(self, screen, asset_manager):
        grass_tile = asset_manager.get_image("grass")
        if grass_tile is None:
            screen.fill((46, 125, 50))
            return
        tile_width, tile_height = grass_tile.get_size()
        if tile_width <= 0 or tile_height <= 0:
            screen.fill((46, 125, 50))
            return

        for x in range(0, self.width, tile_width):
            for y in range(0, self.height, tile_height):
                screen.blit(grass_tile, (x, y))
    
    def drawPitchMarkings(self, screen):
        mid_x = self.width // 2
        mid_y = self.height // 2

        # Outer boundary lines
        pygame.draw.rect(screen, self.line_color, (50, 50, self.width - 100, self.height - 100), self.line_thickness)

        # Center line and circle
        pygame.draw.line(screen, self.line_color, (mid_x, 50), (mid_x, self.height - 50), self.line_thickness)
        pygame.draw.circle(screen, self.line_color, (mid_x, mid_y), 70, self.line_thickness)
        pygame.draw.circle(screen, self.line_color, (mid_x, mid_y), 6)

        # Penalty boxes
        pygame.draw.rect(screen, self.line_color, (50, mid_y - 120, 150, 240), self.line_thickness)
        pygame.draw.rect(screen, self.line_color, (self.width - 200, mid_y - 120, 150, 240), self.line_thickness)

        # Goal posts
        goal_color = (200, 200, 200)
        pygame.draw.rect(screen, goal_color, (10, mid_y - 60, 40, 120))
        pygame.draw.rect(screen, goal_color, (self.width - 50, mid_y - 60, 40, 120))


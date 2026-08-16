import sys
import math
import pygame

class Button:
    # Utility class that creates a clickable screen element. 
    def __init__(self, x, y, width, height, text, base_color, hover_color, text_color="white"):
        # Position vectors, colours and text parameters
        self.rect = pygame.Rect(x, y, width, height)
        self.original_rect = self.rect.copy()
        self.text = text
        self.base_color = pygame.Color(base_color)
        self.hover_color = pygame.Color(hover_color)
        self.current_color = pygame.Color(base_color)
        self.text_color = text_color
        self.font = pygame.font.SysFont(None, 32)
        self.scale = 1.0

    def draw(self, screen):
        # Checks active mouse coordinates to apply a hover effect
        mouse_pos = pygame.mouse.get_pos()
        is_hovered = self.original_rect.collidepoint(mouse_pos) # Use original_rect for collision
        
        target_color = self.hover_color if is_hovered else self.base_color
        target_scale = 1.05 if is_hovered else 1.0
        
        # Smoothly interpolate color and scale
        for i in range(3): # RGB
            self.current_color[i] = int(self.current_color[i] + (target_color[i] - self.current_color[i]) * 0.15)
        self.scale += (target_scale - self.scale) * 0.15
        
        # Apply scaling
        scaled_width = int(self.original_rect.width * self.scale)
        scaled_height = int(self.original_rect.height * self.scale)
        self.rect = pygame.Rect(0, 0, scaled_width, scaled_height)
        self.rect.center = self.original_rect.center
        
        # Render rectangle and label properties
        pygame.draw.rect(screen, self.current_color, self.rect, border_radius=8)
        if is_hovered:
            pygame.draw.rect(screen, "white", self.rect, 2, border_radius=8)
            
        text_surf = self.font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def is_clicked(self, mouse_pos):
        return self.original_rect.collidepoint(mouse_pos) # Use original_rect for click detection


class Slider:
    # Interactive slider for range-based settings (Volume, Difficulty)
    def __init__(self, x, y, width, height, min_val, max_val, initial_val, label):
        self.rect = pygame.Rect(x, y, width, height)
        self.min_val = min_val
        self.max_val = max_val
        self.val = initial_val
        self.label = label
        self.active = False
        
        # Handle position calculation
        self.handle_radius = height // 2 + 4
        self.update_handle_pos()

    def update_handle_pos(self):
        # Calculate handle x based on value
        ratio = (self.val - self.min_val) / (self.max_val - self.min_val)
        self.handle_x = self.rect.x + int(ratio * self.rect.width)

    def draw(self, screen):
        # Draw Label
        font = pygame.font.SysFont(None, 28)
        lbl_surf = font.render(f"{self.label}: {int(self.val) if self.max_val > 1 else round(self.val, 2)}", True, "white")
        screen.blit(lbl_surf, (self.rect.x, self.rect.y - 25))
        
        # Draw Track
        pygame.draw.rect(screen, (50, 50, 50), self.rect, border_radius=self.rect.height//2)
        pygame.draw.rect(screen, (100, 100, 100), self.rect, 2, border_radius=self.rect.height//2)
        
        # Draw Fill
        fill_rect = pygame.Rect(self.rect.x, self.rect.y, self.handle_x - self.rect.x, self.rect.height)
        pygame.draw.rect(screen, (59, 130, 246), fill_rect, border_radius=self.rect.height//2)
        
        # Draw Handle
        handle_color = (255, 255, 255) if self.active else (200, 200, 200)
        pygame.draw.circle(screen, handle_color, (self.handle_x, self.rect.centery), self.handle_radius)
        pygame.draw.circle(screen, (30, 58, 138), (self.handle_x, self.rect.centery), self.handle_radius, 2)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = event.pos
            handle_rect = pygame.Rect(self.handle_x - self.handle_radius, self.rect.y - self.handle_radius, self.handle_radius*2, self.rect.height + self.handle_radius*2)
            if handle_rect.collidepoint(mouse_pos) or self.rect.collidepoint(mouse_pos):
                self.active = True
                self.update_value(mouse_pos[0])
        elif event.type == pygame.MOUSEBUTTONUP:
            self.active = False
        elif event.type == pygame.MOUSEMOTION and self.active:
            self.update_value(event.pos[0])

    def update_value(self, mouse_x):
        # Clamp mouse_x to track bounds
        clamped_x = max(self.rect.x, min(mouse_x, self.rect.x + self.rect.width))
        ratio = (clamped_x - self.rect.x) / self.rect.width
        self.val = self.min_val + ratio * (self.max_val - self.min_val)
        self.handle_x = clamped_x


class MenuSystem:
    # Manages UI rendering, security and access checking by utilising GameLauncher
    def __init__(self, game_launcher, network_client=None):
        pygame.init()
        self.width = 1280
        self.height = 720
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Pocket XI - Main Menu")
        self.clock = pygame.time.Clock()
        self.font_title = pygame.font.SysFont("Arial", 42, bold=True)
        self.font_body = pygame.font.SysFont("Arial", 22)
        self.font_sub = pygame.font.SysFont("Arial", 16)
        
        # backend 
        self.game_launcher = game_launcher
        self.network_client = network_client
        
        # Global UI FSM Config
        self.current_state = "LOGIN_SCREEN"
        self.username_buffer = ""
        self.password_buffer = ""
        self.active_field = "username"
        self.notification_text = ""
        self.notification_color = "white"

        # Online Match
        self.join_code_buffer = ""
        self.lobby_status = "Not connected"
        self.lobby_status_color = "white"
        self.rect_host_room = pygame.Rect(self.width // 2 - 250, 220, 500, 60)
        self.rect_join_box = pygame.Rect(self.width // 2 - 250, 320, 320, 60)
        self.rect_join_btn = pygame.Rect(self.width // 2 + 80, 320, 170, 60)
        
        # Temporary runtime save dictionary
        self.temp_saved_profile = None

        # Button definitions
        self.rect_header = pygame.Rect(40, 30, self.width - 80, 80)
        self.rect_mode_1 = pygame.Rect(40, 150, 580, 200)
        self.rect_mode_2 = pygame.Rect(40, 380, 580, 200)
        self.rect_stats = pygame.Rect(660, 150, 580, 430)
        self.rect_settings = pygame.Rect(800, 610, 200, 60)
        self.rect_logout = pygame.Rect(1040, 610, 180, 60)
        self.rect_back = pygame.Rect(self.width // 2 - 100, 550, 200, 50)
        self.rect_auth_toggle = pygame.Rect(100, 530, 360, 50)
        self.rect_username = pygame.Rect(self.width // 2 - 250, 200, 500, 50)
        self.rect_password = pygame.Rect(self.width // 2 - 250, 280, 500, 50)
        self.rect_submit = pygame.Rect(self.width // 2 - 210, 360, 200, 50)
        self.rect_auth_toggle = pygame.Rect(self.width // 2 + 10, 360, 200, 50)

        # Settings Sliders
        self.vol_slider = Slider(self.width // 2 - 200, 280, 400, 15, 0.0, 1.0, self.game_launcher.master_volume, "Master Volume")
        self.diff_slider = Slider(self.width // 2 - 200, 380, 400, 15, 1, 5, self.game_launcher.base_difficulty_tier, "AI Difficulty")

        self.hover_mode1 = False
        self.hover_mode2 = False
        self.hover_settings = False
        self.hover_logout = False
        self.hover_back = False
        self.hover_auth_toggle = False
        self.hub_button_hover = {}
        self.auth_button_hover = {"submit": 0.0, "toggle": 0.0}

    def _draw_icon(self, screen, name, x, y, size=30, color="white"):
        # Helper to draw simple primitive icons
        if name == "play":
            pygame.draw.polygon(screen, color, [(x, y), (x + size, y + size//2), (x, y + size)])
        elif name == "settings":
            pygame.draw.circle(screen, color, (x + size//2, y + size//2), size//3, 3)
            for i in range(8):
                angle = math.radians(i * 45)
                start = (x + size//2 + math.cos(angle) * size//3, y + size//2 + math.sin(angle) * size//3)
                end = (x + size//2 + math.cos(angle) * size//2, y + size//2 + math.sin(angle) * size//2)
                pygame.draw.line(screen, color, start, end, 3)
        elif name == "stats":
            pygame.draw.rect(screen, color, (x, y + size//2, size//4, size//2))
            pygame.draw.rect(screen, color, (x + size//3, y + size//4, size//4, 3*size//4))
            pygame.draw.rect(screen, color, (x + 2*size//3, y, size//4, size))
        elif name == "logout":
            pygame.draw.rect(screen, color, (x, y, size, size), 2)
            pygame.draw.line(screen, color, (x + size//2, y + size//4), (x + size, y + size//4), 2)
            pygame.draw.polygon(screen, color, [(x + size, y + size//4), (x + size - 10, y + size//4 - 5), (x + size - 10, y + size//4 + 5)])

    def drawLoginScreen(self):
        title_text = "Login" if self.current_state == "LOGIN_SCREEN" else "Registration"
        
        # Pulse effect
        pulse = (math.sin(pygame.time.get_ticks() / 500) + 1) / 2
        title_color = (int(200 + 55 * pulse), int(200 + 55 * pulse), 255)
        
        panel = pygame.Rect(self.width // 2 - 330, 125, 660, 375)
        pygame.draw.rect(self.screen, (8, 14, 27), panel.move(0, 9), border_radius=18)
        pygame.draw.rect(self.screen, (30, 41, 59), panel, border_radius=18)
        pygame.draw.rect(self.screen, (100, 180, 255), panel, 2, border_radius=18)

        title_surf = self.font_title.render(title_text, True, title_color)
        title_rect = title_surf.get_rect(center=(self.width // 2, 165))
        self.screen.blit(title_surf, title_rect)

        # Draw input box backgrounds
        u_box = self.rect_username
        p_box = self.rect_password
        
        self._draw_auth_field(u_box, "username")
        self._draw_auth_field(p_box, "password")

        u_txt = self.font_body.render(f"Username: {self.username_buffer} {'|' if self.active_field == 'username' else ''}", True, "white")
        p_txt = self.font_body.render(f"Password: {'*' * len(self.password_buffer)} {'|' if self.active_field == 'password' else ''}", True, "white")
        
        self.screen.blit(u_txt, (u_box.x + 10, u_box.y + 10))
        self.screen.blit(p_txt, (p_box.x + 10, p_box.y + 10))

        toggle_text = "CREATE ACCOUNT" if self.current_state == "LOGIN_SCREEN" else "BACK TO LOGIN"
        self._draw_auth_button(self.rect_submit, "SUBMIT", (30, 120, 70), "submit")
        self._draw_auth_button(self.rect_auth_toggle, toggle_text, (42, 93, 170), "toggle")

        hint = self.font_sub.render("Press [TAB] to switch boxes | Press [ENTER] or Click Submit", True, "gray")
        self.screen.blit(hint, hint.get_rect(center=(self.width // 2, 465)))

    def _draw_auth_field(self, rect, field_name):
        active = self.active_field == field_name
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        fill = (35, 61, 105) if active else (20, 29, 45)
        border = (96, 210, 255) if active else ((105, 135, 175) if hovered else (66, 83, 110))
        pygame.draw.rect(self.screen, (8, 14, 27), rect.move(0, 3), border_radius=10)
        pygame.draw.rect(self.screen, fill, rect, border_radius=10)
        pygame.draw.rect(self.screen, border, rect, 2, border_radius=10)

    def _draw_auth_button(self, rect, label, accent, key):
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        progress = self.auth_button_hover[key]
        progress += ((1.0 if hovered else 0.0) - progress) * 0.2
        self.auth_button_hover[key] = progress

        scale = 1.0 + progress * 0.03
        draw_rect = pygame.Rect(0, 0, int(rect.width * scale), int(rect.height * scale))
        draw_rect.center = rect.center
        colour = pygame.Color(30, 41, 59).lerp(pygame.Color(accent), 0.35 + progress * 0.45)
        pygame.draw.rect(self.screen, (8, 14, 27), draw_rect.move(0, int(6 - progress * 3)), border_radius=10)
        pygame.draw.rect(self.screen, colour, draw_rect, border_radius=10)
        pygame.draw.rect(self.screen, accent, draw_rect, 3 if hovered else 1, border_radius=10)

        text = self.font_sub.render(label, True, "white")
        self.screen.blit(text, text.get_rect(center=draw_rect.center))
    
    def drawMainHub(self):
        pulse = (math.sin(pygame.time.get_ticks() / 500) + 1) / 2
        title_color = (int(200 + 55 * pulse), 255, int(200 + 55 * pulse))
        
        title_surf = self.font_title.render(f"Pocket XI - {self.game_launcher.active_user_session}", True, title_color)
        title_rect = title_surf.get_rect(center=(self.width // 2, 100))
        self.screen.blit(title_surf, title_rect)

        buttons = [
            (self.rect_mode_1, "QUICK MATCH", "SPACE", (30, 120, 70)),
            (self.rect_mode_2, "PLAY WITH A FRIEND", "ENTER", (118, 91, 185)),
            (self.rect_stats, "GAME STATS", "S", (42, 93, 170)),
            (self.rect_settings, "SETTINGS", "E", (112, 78, 170)),
            (self.rect_logout, "LOG OUT", "O", (155, 65, 70)),
        ]
        for rect, label, shortcut, accent in buttons:
            self._draw_hub_button(rect, label, shortcut, accent)

    def _draw_hub_button(self, rect, label, shortcut, accent):
        """Draw a responsive hub button without changing its clickable area."""
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        progress = self.hub_button_hover.get(label, 0.0)
        target = 1.0 if hovered else 0.0
        progress += (target - progress) * 0.2
        self.hub_button_hover[label] = progress

        scale = 1.0 + progress * 0.025
        draw_rect = pygame.Rect(0, 0, int(rect.width * scale), int(rect.height * scale))
        draw_rect.center = rect.center
        shadow_rect = draw_rect.move(0, int(7 - progress * 3))
        base_colour = pygame.Color(30, 41, 59)
        accent_colour = pygame.Color(accent)
        colour = base_colour.lerp(accent_colour, 0.35 + progress * 0.45)

        pygame.draw.rect(self.screen, (8, 14, 27), shadow_rect, border_radius=12)
        pygame.draw.rect(self.screen, colour, draw_rect, border_radius=12)
        pygame.draw.rect(self.screen, accent_colour, draw_rect, 2 if hovered else 1, border_radius=12)

        label_font = pygame.font.SysFont("Arial", 28, bold=True)
        label_surface = label_font.render(label, True, "white")
        label_rect = label_surface.get_rect(center=(draw_rect.centerx, draw_rect.centery - 10))
        self.screen.blit(label_surface, label_rect)

        shortcut_surface = self.font_sub.render(f"[{shortcut}]", True, (220, 230, 245))
        shortcut_rect = shortcut_surface.get_rect(center=(draw_rect.centerx, draw_rect.centery + 28))
        self.screen.blit(shortcut_surface, shortcut_rect)

    def drawOnlineLobby(self):
        """Renders the multiplayer room hosting and joining dashboard."""
        self.screen.fill((15, 23, 42))
        title_surf = self.font_title.render("Multiplayer Lobby", True, (147, 197, 253))
        self.screen.blit(title_surf, title_surf.get_rect(center=(self.width // 2, 100)))

        # Display Network Status
        status_surf = self.font_body.render(self.lobby_status, True, self.lobby_status_color)
        self.screen.blit(status_surf, status_surf.get_rect(center=(self.width // 2, 160)))

        # Host Room Card
        hover_host = self.rect_host_room.collidepoint(pygame.mouse.get_pos())
        host_bg = (30, 58, 138) if hover_host else (30, 41, 59)
        pygame.draw.rect(self.screen, host_bg, self.rect_host_room, border_radius=12)
        pygame.draw.rect(self.screen, (96, 165, 250), self.rect_host_room, 2, border_radius=12)
        
        if self.network_client and self.network_client.room_code and self.network_client.player_role == "p1":
            host_text = f"ROOM CODE: {self.network_client.room_code} (WAITING...)"
        else:
            host_text = "CREATE PRIVATE ROOM (HOST)"
        h_surf = self.font_body.render(host_text, True, "white")
        self.screen.blit(h_surf, h_surf.get_rect(center=self.rect_host_room.center))

        # Join Room Box
        pygame.draw.rect(self.screen, (20, 29, 45), self.rect_join_box, border_radius=12)
        pygame.draw.rect(self.screen, (96, 165, 250), self.rect_join_box, 2, border_radius=12)
        join_display = f"CODE: {self.join_code_buffer}|" if self.join_code_buffer else "ENTER 4-LETTER CODE"
        j_surf = self.font_body.render(join_display, True, "white" if self.join_code_buffer else "gray")
        self.screen.blit(j_surf, (self.rect_join_box.x + 20, self.rect_join_box.y + 18))

        # Join Button
        hover_join = self.rect_join_btn.collidepoint(pygame.mouse.get_pos())
        join_btn_bg = (30, 120, 70) if hover_join else (22, 101, 52)
        pygame.draw.rect(self.screen, join_btn_bg, self.rect_join_btn, border_radius=12)
        pygame.draw.rect(self.screen, (74, 222, 128), self.rect_join_btn, 2, border_radius=12)
        j_btn_surf = self.font_body.render("JOIN", True, "white")
        self.screen.blit(j_btn_surf, j_btn_surf.get_rect(center=self.rect_join_btn.center))

        self._draw_back_button()

    def drawSettingsMenu(self):
        high_contrast = self.game_launcher.high_contrast_active
        bg = (255, 255, 255) if high_contrast else (15, 23, 42)
        txt = (0, 0, 0) if high_contrast else (255, 255, 255)
        
        self.screen.fill(bg)
        title_surf = pygame.font.SysFont(None, 60).render("Settings Menu", True, txt)
        title_rect = title_surf.get_rect(center=(self.width // 2, 100))
        self.screen.blit(title_surf, title_rect)
        
        # Draw Sliders
        self.vol_slider.draw(self.screen)
        self.diff_slider.draw(self.screen)
        
        # Update launcher state from slider
        self.game_launcher.base_difficulty_tier = int(self.diff_slider.val)
        self.game_launcher.master_volume = round(self.vol_slider.val, 2)

        self._draw_back_button(high_contrast)
    
    def drawStatsDashboard(self):
        title = self.font_title.render("Performance History Menu", True, "white")
        self.screen.blit(title, (100, 150))
        
        if self.temp_saved_profile and isinstance(self.temp_saved_profile, dict):
            g_lbl = self.font_body.render(f"Total Goals Scored: {self.temp_saved_profile.get('goals', 0)}", True, "white")
            s_lbl = self.font_body.render(f"Total Shots Logged: {self.temp_saved_profile.get('shots', 0)}", True, "white")
            p_lbl = self.font_body.render(f"Possession Time   : {self.temp_saved_profile.get('possession_time', 0.0):.2f}s", True, "white")
            
            self.screen.blit(g_lbl, (120, 260))
            self.screen.blit(s_lbl, (120, 320))
            self.screen.blit(p_lbl, (120, 380))
            
        self._draw_back_button()

    def _draw_back_button(self, high_contrast=False):
        """Draw the shared return button with its current hover state."""
        hovered = self.rect_back.collidepoint(pygame.mouse.get_pos())
        self.hover_back = hovered
        progress = self.hub_button_hover.get("back", 0.0)
        progress += ((1.0 if hovered else 0.0) - progress) * 0.2
        self.hub_button_hover["back"] = progress

        scale = 1.0 + progress * 0.03
        draw_rect = pygame.Rect(0, 0, int(self.rect_back.width * scale), int(self.rect_back.height * scale))
        draw_rect.center = self.rect_back.center
        background = (28, 86, 150) if high_contrast else (39, 102, 185)
        border = (0, 0, 0) if high_contrast else (150, 210, 255)

        pygame.draw.rect(self.screen, (8, 14, 27), draw_rect.move(0, 5), border_radius=10)
        pygame.draw.rect(self.screen, background, draw_rect, border_radius=10)
        pygame.draw.rect(self.screen, border, draw_rect, 3 if hovered else 2, border_radius=10)

        label = self.font_sub.render("← RETURN TO MAIN MENU", True, "white")
        self.screen.blit(label, label.get_rect(center=draw_rect.center))

    def update_hover_states(self, mouse_pos):
        # Checks active mouse coordinates to update hover flags for UI elements
        self.hover_mode1 = self.rect_mode_1.collidepoint(mouse_pos)
        self.hover_mode2 = self.rect_mode_2.collidepoint(mouse_pos)
        self.hover_settings = self.rect_settings.collidepoint(mouse_pos)
        self.hover_logout = self.rect_logout.collidepoint(mouse_pos)
        self.hover_back = self.rect_back.collidepoint(mouse_pos)
        self.hover_auth_toggle = self.rect_auth_toggle.collidepoint(mouse_pos)

    def executeSubmitAction(self):
        # Backend trigger that changes state based on login authentication result
        if self.current_state == "LOGIN_SCREEN":
            res = self.game_launcher.login(self.username_buffer, self.password_buffer)
            if res == True:
                self.temp_saved_profile = self.game_launcher.temp_saved_profile
                self.notification_text = "Login Successful."
                self.notification_color = (100, 255, 100)
                self.current_state = "MAIN_HUB"
            else:
                self.notification_text = self.game_launcher.status_message
                self.notification_color = (255, 100, 100)
        else:
            status = self.game_launcher.register(self.username_buffer, self.password_buffer)
            if status == True:
                self.notification_text = "Successful Registration, Return to Login Menu."
                self.notification_color = (100, 255, 100)
                self.current_state = "LOGIN_SCREEN"
                self.password_buffer = ""
            else:
                self.notification_text = self.game_launcher.status_message
                self.notification_color = (255, 100, 100)
    
    def executeLogoutAction(self):
        # Log out by resetting variables
        self.game_launcher.active_user_session = None
        self.temp_saved_profile = None
        self.username_buffer = ""
        self.password_buffer = ""
        self.notification_text = "Session exited via logout."
        self.notification_color = "white"
        self.current_state = "LOGIN_SCREEN"
    
    async def processEvents(self):
        # Poll network inbox if in lobby
        if self.network_client and self.current_state == "ONLINE_LOBBY":
            if self.network_client.match_started:
                return "LAUNCH_ONLINE_MATCH"
            if self.network_client.error_message:
                self.lobby_status = self.network_client.error_message
                self.lobby_status_color = (255, 100, 100)

        # Orchestrates inputs across the keyboard and mouse pointer
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            # Pass events to sliders if in settings
            if self.current_state == "SETTINGS_MENU":
                self.vol_slider.handle_event(event)
                self.diff_slider.handle_event(event)
                # Apply Volume Live
                if pygame.mixer.get_init():
                    pygame.mixer.music.set_volume(self.vol_slider.val)

            # Hover state update
            mouse_pos = event.pos if hasattr(event, "pos") else pygame.mouse.get_pos()
            self.update_hover_states(mouse_pos)

            # --- Mouse ---
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.current_state in ["LOGIN_SCREEN", "REGISTER_SCREEN"]:
                    if self.rect_username.collidepoint(mouse_pos):
                        self.active_field = "username"
                    elif self.rect_password.collidepoint(mouse_pos):
                        self.active_field = "password"
                    elif self.rect_submit.collidepoint(mouse_pos):
                        self.executeSubmitAction()
                    elif self.rect_auth_toggle.collidepoint(mouse_pos):
                        self.current_state = "REGISTER_SCREEN" if self.current_state == "LOGIN_SCREEN" else "LOGIN_SCREEN"
                        self.notification_text = ""
                
                if self.current_state == "MAIN_HUB":
                    if self.rect_mode_1.collidepoint(mouse_pos):
                        return "LAUNCH_MATCH"
                    elif self.rect_mode_2.collidepoint(mouse_pos):
                        self.current_state = "ONLINE_LOBBY"
                        self.lobby_status = "Connecting to Server..."
                        self.lobby_status_color = (255, 200, 100)
                        if self.network_client:
                            connected = await self.network_client.connect()
                            if connected:
                                self.lobby_status = "Connected to Server. Ready to play."
                                self.lobby_status_color = (100, 255, 100)
                            else:
                                self.lobby_status = self.network_client.error_message or "Connection failed"
                                self.lobby_status_color = (255, 100, 100)
                    elif self.rect_stats.collidepoint(mouse_pos):
                        self.current_state = "STATS_DASHBOARD"
                    elif self.rect_settings.collidepoint(mouse_pos):
                        self.current_state = "SETTINGS_MENU"
                    elif self.rect_logout.collidepoint(mouse_pos):
                        self.executeLogoutAction()

                elif self.current_state == "ONLINE_LOBBY":
                    if self.rect_host_room.collidepoint(mouse_pos) and self.network_client:
                        self.lobby_status = "Creating Room..."
                        await self.network_client.create_room()
                    elif self.rect_join_btn.collidepoint(mouse_pos) and self.network_client:
                        if len(self.join_code_buffer) >= 4:
                            self.lobby_status = f"Joining {self.join_code_buffer}..."
                            await self.network_client.join_room(self.join_code_buffer)
                    elif self.rect_back.collidepoint(mouse_pos):
                        self.current_state = "MAIN_HUB"
                
                elif self.current_state in ["SETTINGS_MENU", "STATS_DASHBOARD"]:
                    if self.rect_back.collidepoint(mouse_pos):
                        self.current_state = "MAIN_HUB"

            # --- Keyboard ---
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE and self.current_state not in ["MAIN_HUB"]:
                    self.game_launcher.high_contrast_active = not self.game_launcher.high_contrast_active
                
                if self.current_state in ["LOGIN_SCREEN", "REGISTER_SCREEN"]:
                    if event.key == pygame.K_TAB:
                        self.active_field = "password" if self.active_field == "username" else "username"
                    elif event.key == pygame.K_ESCAPE:
                        self.current_state = "REGISTER_SCREEN" if self.current_state == "LOGIN_SCREEN" else "LOGIN_SCREEN"
                        self.notification_text = ""
                    elif event.key == pygame.K_RETURN:
                        self.executeSubmitAction()
                    elif event.key == pygame.K_BACKSPACE:
                        if self.active_field == "username":
                            self.username_buffer = self.username_buffer[:-1]
                        else:
                            self.password_buffer = self.password_buffer[:-1]
                    else:
                        if event.unicode.isalnum() or event.unicode in ['@', '.', '_']:
                            if self.active_field == "username":
                                self.username_buffer += event.unicode
                            else:
                                self.password_buffer += event.unicode

                elif self.current_state == "ONLINE_LOBBY":
                    if event.key == pygame.K_BACKSPACE:
                        self.join_code_buffer = self.join_code_buffer[:-1]
                    elif event.key == pygame.K_ESCAPE:
                        self.current_state = "MAIN_HUB"
                    elif event.key == pygame.K_RETURN and len(self.join_code_buffer) >= 4 and self.network_client:
                        self.lobby_status = f"Joining {self.join_code_buffer}..."
                        await self.network_client.join_room(self.join_code_buffer)
                    else:
                        if event.unicode.isalnum() and len(self.join_code_buffer) < 4:
                            self.join_code_buffer += event.unicode.upper()
                                
                elif self.current_state == "MAIN_HUB":
                    if event.key in [pygame.K_RETURN, pygame.K_SPACE]:
                        return "LAUNCH_MATCH"
                    elif event.key == pygame.K_e:
                        self.current_state = "SETTINGS_MENU"
                    elif event.key == pygame.K_s:
                        self.current_state = "STATS_DASHBOARD"
                    elif event.key == pygame.K_o:
                        self.executeLogoutAction()

                elif self.current_state in ["SETTINGS_MENU", "STATS_DASHBOARD"]:
                    if event.key == pygame.K_BACKSPACE or event.key == pygame.K_ESCAPE:
                        self.current_state = "MAIN_HUB"

        return "KEEP_RUNNING"

    def renderDisplay(self):
        self.update_hover_states(pygame.mouse.get_pos())
        self.screen.fill((15, 23, 42))
        
        if self.notification_text:
            msg = self.font_sub.render(self.notification_text, True, self.notification_color)
            self.screen.blit(msg, (100, 50))
            
        if self.current_state in ["LOGIN_SCREEN", "REGISTER_SCREEN"]:
            self.drawLoginScreen()
        elif self.current_state == "MAIN_HUB":
            self.drawMainHub()
        elif self.current_state == "ONLINE_LOBBY":
            self.drawOnlineLobby()
        elif self.current_state == "SETTINGS_MENU":
            self.drawSettingsMenu()
        elif self.current_state == "STATS_DASHBOARD":
            self.drawStatsDashboard()
            
        pygame.display.flip()

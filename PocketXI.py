import pygame
import sys
import os
import math
import random
import json
import base64
from cryptography.fernet import Fernet
import hashlib
import secrets

class EncryptionEngine:
    # Module that utilises a cryptography library to encrypt user profile data
    @staticmethod
    def generate_secure_key():
        return Fernet.generate_key()
    
    @staticmethod
    def encryptData(payload_dict, secret_key):
        # Converts a dictionary to JSON and encrypts it into a secure token string.
        try:
            serialised_data = json.dumps(payload_dict).encode('utf-8')
            cipher = Fernet(secret_key)
            encrypted_token = cipher.encrypt(serialised_data)
            return encrypted_token.decode('utf-8')
        except Exception as e:
            print(f"ERROR: Encryption failure: {e}")
            return None
    
    def decryptData(encrypted_token, secret_key):
        # Decrypts a secure token string back into the dictionary format.
        try:
            cipher = Fernet(secret_key)
            decrypted_bytes = cipher.decrypt(encrypted_token.encode('utf-8'))
            return json.loads(decrypted_bytes.decode('utf-8'))
        except Exception as e:
            print(f"ERROR: Decryption failure: {e}")
            return None


class GameLauncher:
    # Gatekeeper that manages authentication, saving, and dashboards before passing execution to main game loop.
    
    def __init__(self):

        # Initialises the launcher window, assets, and default security states.
        pygame.init()
        self.width = 1280
        self.height = 720
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Pocket XI - Login")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 40)
        
        # Path configuration
        base_path = os.path.dirname(os.path.abspath(__file__))
        self.auth_path = os.path.join(base_path, "auth.json")
        self.userdata_path = os.path.join(base_path, "userdata.json")
        self._initialise_local_storage_files()
        
        # Login Configuration
        self.menu_state = "LOGIN_SCREEN"
        self.username_input = ""
        self.password_input = ""
        self.active_input_box = "username"
        self.status_message = ""
        self.status_color = "white"
        
        # Session Management
        self.active_user_session = None
        self.temp_saved_profile = None

    def _initialise_local_storage_files(self):
        # Verifies files and thier paths exist and generates empty files if missing.
        if not os.path.exists(self.auth_path):
            with open(self.auth_path, 'w') as f:
                json.dump({}, f)
        if not os.path.exists(self.userdata_path):
            with open(self.userdata_path, 'w') as f:
                json.dump({}, f)
    
    def validateCredentials(self, username, password):
        # Enforces length and alphanumeric conditions
        u_clean = username.strip().replace(" ", "")
        p_clean = password.strip().replace(" ", "")
        
        # Constraint boundaries
        if not (3 <= len(u_clean) <= 15):
            self.status_message = "Username must be between 3 and 15 characters long."
            self.status_color = (255, 100, 100)
            return False
        if len(p_clean) < 8:
            self.status_message = "Password must be at least 8 characters long."
            self.status_color = (255, 100, 100)
            return False
            
        # Character parsing filter to block injection symbols
        for char in u_clean:
            if not (char.isalnum() or char in ['_', '.', '@',]):
                self.status_message = "'_', '.', or '@' characters not allowed in username."
                self.status_color = (255, 100, 100)
                return False
        return True

    def register(self, username, password):
        # Computes salted SHA-256 hashes and saves initialised profile data to disk.
        u_clean = username.strip().replace(" ", "")
        p_clean = password.strip().replace(" ", "")
        
        if not self.validateCredentials(u_clean, p_clean):
            return False
            
        with open(self.auth_path, 'r') as f:
            auth_db = json.load(f)
            
        if u_clean in auth_db:
            self.status_message = "Username already exists."
            self.status_color = (255, 100, 100)
            return False
            
        # Salting
        salt = secrets.token_hex(16)
        salted_password = p_clean + salt
        password_hash = hashlib.sha256(salted_password.encode('utf-8')).hexdigest()
        
        # Generate key directly from the password
        derived_key = hashlib.sha256(p_clean.encode('utf-8')).digest()
        fernet_key = base64.urlsafe_b64encode(derived_key)
        
        # Base progress template
        initial_stats_payload = {
            "goals": 0,
            "shots": 0,
            "possession_time": 0.0
        }
        
        # Reversible data encryption
        encrypted_data_token = EncryptionEngine.encryptData(initial_stats_payload, fernet_key)
        if not encrypted_data_token:
            self.status_message = "Cryptographic processing failed."
            self.status_color = (255, 100, 100)
            return False
            
        # Commit records across both storage files
        try:
            auth_db[u_clean] = {"salt": salt, "hash": password_hash}
            with open(self.auth_path, 'w') as f:
                json.dump(auth_db, f, indent=4)
                
            with open(self.userdata_path, 'r') as f:
                user_db = json.load(f)
            user_db[u_clean] = encrypted_data_token
            with open(self.userdata_path, 'w') as f:
                json.dump(user_db, f, indent=4)
                
            self.status_message = "Successful Registration, Proceed to Login"
            self.status_color = (100, 255, 100)
            self.menu_state = "LOGIN_SCREEN"
            self.password_input = ""
            return True
        except Exception as e:
            self.status_message = f"FILE SYNC ERROR: Rollback triggered. Error: {e}"
            self.status_color = (255, 100, 100)
            return False
    
    def login(self, username, password):
        # Reconstructs salted hashes from the database and extracts decoded session history
        u_clean = username.strip().replace(" ", "")
        p_clean = password.strip().replace(" ", "")
        
        if not self.validateCredentials(u_clean, p_clean):
            return False
            
        with open(self.auth_path, 'r') as f:
            auth_db = json.load(f)
            
        if u_clean not in auth_db:
            self.status_message = "AUTHENTICATION REFUSED: Username does not match records."
            self.status_color = (255, 100, 100)
            return False
            
        # Reconstruct and verify calculated hash values against target database contents
        stored_salt = auth_db[u_clean]["salt"]
        stored_hash = auth_db[u_clean]["hash"]
        computed_hash = hashlib.sha256((p_clean + stored_salt).encode('utf-8')).hexdigest()
        
        if computed_hash != stored_hash:
            self.status_message = "AUTHENTICATION REFUSED: Incorrect password."
            self.status_color = (255, 100, 100)
            return False
            
        # Password matches -> derive secret key
        derived_key = hashlib.sha256(p_clean.encode('utf-8')).digest()
        fernet_key = base64.urlsafe_b64encode(derived_key)
        
        with open(self.userdata_path, 'r') as f:
            user_db = json.load(f)
        encrypted_token_string = user_db.get(u_clean)
        
        # Extract plaintext dictionaries
        decrypted_profile = EncryptionEngine.decryptData(encrypted_token_string, fernet_key)
        
        if decrypted_profile is not None:
            self.active_user_session = u_clean
            self.temp_saved_profile = decrypted_profile
            self.status_message = f"WELCOME BACK: {u_clean}. Session active."
            self.status_color = (100, 255, 100)
            self.menu_state = "MAIN_HUB"
            return True
        else:
            self.status_message = "DECRYPTION ERROR: JSON stream extraction rejected."
            self.status_color = (255, 100, 100)
            return False


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
    def __init__(self, game_launcher):
        pygame.init()
        self.width = 1280
        self.height = 720
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Pocket XI - Main Menu")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 40)
        
        # backend 
        self.game_launcher = game_launcher
        
        # Global UI FSM Config
        self.current_state = "LOGIN_SCREEN"
        self.username_buffer = ""
        self.password_buffer = ""
        self.active_field = "username"
        self.notification_text = ""
        self.notification_color = "white"
        
        # Temporary runtime save dictionary
        self.temp_saved_profile = None

        # Button instantiation
        self.login_buttons = {
            "submit": Button(100, 390, 160, 45, "Submit", (30, 58, 138), (59, 130, 246)),
            "toggle": Button(280, 390, 240, 45, "Toggle Login/Register", (71, 85, 105), (100, 116, 139))
        }
        self.hub_buttons = {
            "match": Button(100, 540, 240, 50, "Launch Game", (22, 101, 52), (34, 197, 94)),
            "stats": Button(360, 540, 240, 50, "Past Match Stats", (30, 58, 138), (59, 130, 246)),
            "settings": Button(620, 540, 240, 50, "Settings Menu", (146, 64, 14), (234, 179, 8)),
            "logout": Button(880, 540, 240, 50, "Quit Game", (153, 27, 27), (239, 68, 68))
        }
        self.back_button = Button(0, 600, 280, 45, "Return to Main Menu", (71, 85, 105), (100, 116, 139))
        self.back_button.original_rect.centerx = self.width // 2
        self.back_button.rect.centerx = self.width // 2

        # Settings Sliders
        self.vol_slider = Slider(self.width // 2 - 200, 280, 400, 15, 0.0, 1.0, 0.8, "Master Volume")
        self.diff_slider = Slider(self.width // 2 - 200, 380, 400, 15, 1, 5, 3, "AI Difficulty")

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
        title_color = (200 + 55 * pulse, 200 + 55 * pulse, 255)
        
        title_surf = pygame.font.SysFont(None, 60).render(title_text, True, title_color)
        title_rect = title_surf.get_rect(center=(self.width // 2, 100))
        self.screen.blit(title_surf, title_rect)

        # Draw input box backgrounds
        u_box = pygame.Rect(self.width // 2 - 250, 200, 500, 50)
        p_box = pygame.Rect(self.width // 2 - 250, 280, 500, 50)
        
        # Highlight active box
        u_color = (30, 58, 138) if self.active_field == "username" else (50, 50, 50)
        p_color = (30, 58, 138) if self.active_field == "password" else (50, 50, 50)
        
        pygame.draw.rect(self.screen, u_color, u_box, border_radius=10)
        pygame.draw.rect(self.screen, p_color, p_box, border_radius=10)
        pygame.draw.rect(self.screen, "cyan" if self.active_field == "username" else "gray", u_box, 2, border_radius=10)
        pygame.draw.rect(self.screen, "cyan" if self.active_field == "password" else "gray", p_box, 2, border_radius=10)

        u_txt = self.font.render(f"Username: {self.username_buffer} {'|' if self.active_field == 'username' else ''}", True, "white")
        p_txt = self.font.render(f"Password: {'*' * len(self.password_buffer)} {'|' if self.active_field == 'password' else ''}", True, "white")
        
        self.screen.blit(u_txt, (u_box.x + 10, u_box.y + 10))
        self.screen.blit(p_txt, (p_box.x + 10, p_box.y + 10))

        # Re-center buttons
        self.login_buttons["submit"].rect.centerx = self.width // 2 - 130
        self.login_buttons["submit"].rect.y = 360
        self.login_buttons["toggle"].rect.centerx = self.width // 2 + 90
        self.login_buttons["toggle"].rect.y = 360

        hint = pygame.font.SysFont(None, 25).render("Press [TAB] to switch boxes | Press [ENTER] or Click Submit", True, "gray")
        self.screen.blit(hint, hint.get_rect(center=(self.width // 2, 450)))

        for btn in self.login_buttons.values():
            btn.draw(self.screen)
    
    def drawMainHub(self):
        # Pulse effect
        pulse = (math.sin(pygame.time.get_ticks() / 500) + 1) / 2
        title_color = (200 + 55 * pulse, 255, 200 + 55 * pulse)
        
        title_surf = pygame.font.SysFont(None, 60).render(f"Pocket XI - {self.game_launcher.active_user_session}", True, title_color)
        title_rect = title_surf.get_rect(center=(self.width // 2, 100))
        self.screen.blit(title_surf, title_rect)

        options = [
            ("[Quick Match] : Press [SPACEBAR] or Click button", "play"),
            ("[Game Stats]  : Press [S] or Click button", "stats"),
            ("[Settings]    : Press [E] or Click button", "settings"),
            ("[Log Out]     : Press [O] or Click button", "logout")
        ]
        
        for i, (text, icon_name) in enumerate(options):
            txt_surf = self.font.render(text, True, "white")
            txt_rect = txt_surf.get_rect(center=(self.width // 2, 220 + i * 50))
            self.screen.blit(txt_surf, txt_rect)
            # Draw icon next to text
            self._draw_icon(self.screen, icon_name, txt_rect.left - 50, txt_rect.centery - 15)

        # Align buttons in a row
        btn_w, btn_h = 240, 50
        total_w = 4 * btn_w + 3 * 20
        start_x = (self.width - total_w) // 2
        
        for i, btn in enumerate(self.hub_buttons.values()):
            btn.rect.x = start_x + i * (btn_w + 20)
            btn.rect.y = 500
            btn.draw(self.screen)

    def drawSettingsMenu(self):
        title_surf = pygame.font.SysFont(None, 60).render("Settings Menu", True, "white")
        title_rect = title_surf.get_rect(center=(self.width // 2, 100))
        self.screen.blit(title_surf, title_rect)
        
        # Draw Sliders
        self.vol_slider.draw(self.screen)
        self.diff_slider.draw(self.screen)
        
        self.back_button.draw(self.screen)
    
    def drawStatsDashboard(self):
        title = self.font.render("Performance History Menu", True, "white")
        self.screen.blit(title, (100, 150))
        
        if self.temp_saved_profile and isinstance(self.temp_saved_profile, dict):
            g_lbl = self.font.render(f"Total Goals Scored: {self.temp_saved_profile.get('goals', 0)}", True, "white")
            s_lbl = self.font.render(f"Total Shots Logged: {self.temp_saved_profile.get('shots', 0)}", True, "white")
            p_lbl = self.font.render(f"Possession Time   : {self.temp_saved_profile.get('possession_time', 0.0):.2f}s", True, "white")
            
            self.screen.blit(g_lbl, (120, 260))
            self.screen.blit(s_lbl, (120, 320))
            self.screen.blit(p_lbl, (120, 380))
            
        self.back_button.draw(self.screen)

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
        self.game_launcher.user_session = None
        self.temp_saved_profile = None
        self.username_buffer = ""
        self.password_buffer = ""
        self.notification_text = "Session exited via logout."
        self.notification_color = "white"
        self.current_state = "LOGIN_SCREEN"
    
    def processEvents(self):
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
                pygame.mixer.music.set_volume(self.vol_slider.val)
                # In this project, we might want to apply to all sounds
                # For simplicity, let's just use the value in the next match launch

            # --- Mouse ---
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_click_pos = event.pos
                
                if self.current_state in ["LOGIN_SCREEN", "REGISTER_SCREEN"]:
                    if self.login_buttons["submit"].is_clicked(mouse_click_pos):
                        self.executeSubmitAction()
                    elif self.login_buttons["toggle"].is_clicked(mouse_click_pos):
                        self.current_state = "REGISTER_SCREEN" if self.current_state == "LOGIN_SCREEN" else "LOGIN_SCREEN"
                        self.notification_text = ""
                        
                elif self.current_state == "MAIN_HUB":
                    if self.hub_buttons["match"].is_clicked(mouse_click_pos):
                        return "LAUNCH_MATCH"
                    elif self.hub_buttons["stats"].is_clicked(mouse_click_pos):
                        self.current_state = "STATS_DASHBOARD"
                    elif self.hub_buttons["settings"].is_clicked(mouse_click_pos):
                        self.current_state = "SETTINGS_MENU"
                    elif self.hub_buttons["logout"].is_clicked(mouse_click_pos):
                        self.executeLogoutAction()
                        
                elif self.current_state in ["SETTINGS_MENU", "STATS_DASHBOARD"]:
                    if self.back_button.is_clicked(mouse_click_pos):
                        self.current_state = "MAIN_HUB"

            # --- Keyboard ---
            if event.type == pygame.KEYDOWN:
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
                                
                elif self.current_state == "MAIN_HUB":
                    if event.key == pygame.K_SPACE:
                        return "LAUNCH_MATCH"
                    elif event.key == pygame.K_s:
                        self.current_state = "STATS_DASHBOARD"
                    elif event.key == pygame.K_e:
                        self.current_state = "SETTINGS_MENU"
                    elif event.key == pygame.K_o:
                        self.executeLogoutAction()
                        
                elif self.current_state in ["SETTINGS_MENU", "STATS_DASHBOARD"]:
                    if event.key == pygame.K_BACKSPACE or event.key == pygame.K_ESCAPE:
                        self.current_state = "MAIN_HUB"
        return "KEEP_RUNNING"

    def renderDisplay(self):
        self.screen.fill((15, 23, 42))
        
        # Background animation effect
        time_ms = pygame.time.get_ticks()
        pulse = (math.sin(time_ms / 500) + 1) / 2 # 0 to 1
        
        if self.notification_text:
            msg = self.font.render(self.notification_text, True, self.notification_color)
            self.screen.blit(msg, (100, 50))
            
        if self.current_state in ["LOGIN_SCREEN", "REGISTER_SCREEN"]:
            self.drawLoginScreen()
        elif self.current_state == "MAIN_HUB":
            self.drawMainHub()
        elif self.current_state == "SETTINGS_MENU":
            self.drawSettingsMenu()
        elif self.current_state == "STATS_DASHBOARD":
            self.drawStatsDashboard()
            
        pygame.display.flip()


class TeamLoader:
    # Parses JSON data to player attributes 
    def __init__(self, filepath="assets/teams.json"):
        base_path = os.path.dirname(os.path.abspath(__file__))
        self.filepath = os.path.join(base_path, filepath)
        self.teams_data = {}
        self._loadAllTeams()

    def _loadAllTeams(self):
        # Load attributes from teams.json file
        try:
            with open(self.filepath, 'r') as file:
                self.teams_data = json.load(file)
                print(f"Loaded team data from {self.filepath}")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            # Fallback to base constants if file is missing/corrupted
            print(f"WARNING: Could not load team data ({e}). Defaulting to fallback.")
            self.teams_data = {
                "default": {
                    "speed": 250, 
                    "sprint_speed": 380, 
                    "max_stamina": 100.0, 
                    "spin": 1.0, 
                    "strength": 1.0
                }
            }
    
    def get_team_stats(self, team_name):
        # Fetches specific team stats
        return self.teams_data.get(team_name, self.teams_data.get("default"))


class MatchController:
    # manages the game loop, state transitions, and assigns tasks to other engines / modules
    def __init__(self):
        # core variables
        self.screen_width = 1280
        self.screen_height = 720
        self.fps = 60
        self.screen = None
        self.clock = None
        self.dt = 0.0

        # game state variables
        self.p1_score = 0
        self.p2_score = 0
        self.MAX_GOALS = 3
        self.is_game_over = False
        self.is_paused = False
        self.match_time_remaining = 300.0

        # component modules (initialised later)
        self.player1 = None
        self.player2 = None
        self.ball = None
        self.physics_engine = None
        self.graphics_manager = None
        self.pitch_renderer = None
        self.sound_manager = None

    def initialiseGame(self):
        # Boots pygame, creates screen, and instantiates all required game objects
        pygame.init()
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Pocket XI")
        self.clock = pygame.time.Clock()

        # Load Data Modules
        self.team_loader = TeamLoader()
        p1_stats = self.team_loader.get_team_stats("red_team")
        p2_stats = self.team_loader.get_team_stats("blue_team")

        # Instantiate AIManager with the pitch boundaries
        pitch_rect = pygame.Rect(50, 50, self.screen_width - 100, self.screen_height - 100)
        self.ai_manager = AIManager(pitch_rect)

        self.asset_manager = AnimationManager("assets")
        self.sound_manager = SoundManager("assets/audio")
        self.stats_tracker = StatsTracker()
        # Populates stats tracker with loaded userdata history 
        if 'launcher_backend' in globals() and 'menu_system' in globals():
            user_id = launcher_backend.active_user_session
            if user_id and menu_system.temp_saved_profile:
                # Accumulate historical stats
                self.stats_tracker.stats["p1"]["goals"] = menu_system.temp_saved_profile.get("goals", 0)
                self.stats_tracker.stats["p1"]["shots"] = menu_system.temp_saved_profile.get("shots", 0)
                self.stats_tracker.stats["p1"]["possession_time"] = menu_system.temp_saved_profile.get("possession_time", 0.0)
                print(f"Player data loaded in memory for: {user_id}")

        self.pitch_renderer = PitchRenderer(self.screen_width, self.screen_height)
        self.particle_system = ParticleSystem()
        self.physics_engine = PhysicsEngine(pygame.Rect(50, 50, self.screen_width - 100, self.screen_height - 100), self.sound_manager, self.stats_tracker, self.ai_manager, self.particle_system)
        self.sound_manager.play_sfx("whistle") # Kickoff whistle

        self.player1 = Player(self.sound_manager, player_id="p1", start_pos=(400, 360), controls="WASD", stats=p1_stats)
        self.player2 = Player(self.sound_manager, player_id="p2", start_pos=(880, 360), controls="ARROWS", stats=p2_stats)
        self.ball = Ball(start_pos=(self.screen_width // 2, self.screen_height // 2))
        
        # Goal positions for FSM reference
        self.p1_goal_pos = pygame.Vector2(10, self.screen_height // 2)
        self.p2_goal_pos = pygame.Vector2(self.screen_width - 50, self.screen_height // 2)

        print("Game Initialised Successfully.")

    def handleMainEvents(self):
        # Processes system-level events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.terminateGame()
            
            if event.type == pygame.KEYDOWN:
                if self.is_game_over:
                    if event.key == pygame.K_r:
                        self._hardResetMatch()
                    elif event.key == pygame.K_ESCAPE:
                        return "EXIT_TO_MENU"
                else:
                    if event.key == pygame.K_ESCAPE or event.key == pygame.K_p:
                        self.is_paused = not self.is_paused
        return "KEEP_RUNNING"

    def _hardResetMatch(self):
        # Full reset of the match state
        self.p1_score = 0
        self.p2_score = 0
        self.match_time_remaining = 300.0
        self.is_game_over = False
        self.is_paused = False
        self._resetPositions()
        # Reset stats for the NEW match session (but keep P1 loaded stats)
        # Actually, p1 should keep its base stats, only reset the "current match" contribution
        # For simplicity in this NEA, we just reset the scoreboard and timer.
        print("Match Reset Successful.")

    def updateTimer(self):
        # Subtracts dt from remaining match time every frame. 
        if self.match_time_remaining > 0:
            self.match_time_remaining -= self.dt
            
            # Prevent negative time 
            if self.match_time_remaining < 0:
                self.match_time_remaining = 0
        
    def heuristicAdapt(self, ai_score, user_score, match_time):
        # Dynamically Adjusts the difficulty of the AI's gameplay

        # Positive G means AI is winning, negative G means AI is losing.
        G = ai_score - user_score 
        
        # Default fallback modifiers
        speed_modifier = 1.0
        reaction_delay = 0.0
        
        # AI losing by > 2 goals
        if G < -2:
            # Boost ReactionSpeed & MaxVelocity
            speed_modifier = 1.35  # 35% speed boost
            reaction_delay = 0.0   # Instant reaction
            
        # AI winning by > 3 goals
        elif G > 3:
            # Apply ReactionDelay & Reduce Speed
            speed_modifier = 0.80  # 20% speed reduction
            reaction_delay = 0.5   # 0.5 seconds reaction delay
            
        #  Compile in one dictionary
        modifiers = {
            "max_velocity_mult": speed_modifier,
            "reaction_delay": reaction_delay
        }
        
        return modifiers
    
    def updateMatchState(self):
        # Coordinates physics and movement updates while match is running
        if self.is_game_over or self.is_paused:
            return
        
        # Decrement Match Timer
        self.updateTimer()

        # Update VFX
        self.particle_system.update(self.dt)

        # Play ambient sound
        self.sound_manager.update_ambient_chants()

        # Check AFK Status for both players
        self.player1.checkAFK()
        self.player2.checkAFK()

        # Update Player 1
        self.player1.handleInput()
        if self.player1.is_afk:
            # Calculate modifiers specifically for Player 1 AI
            p1_modifiers = self.heuristicAdapt(self.p1_score, self.p2_score, self.match_time_remaining)
            self.ai_manager.updateFSM(self.player1, self.player2, self.ball, self.p1_goal_pos, self.p2_goal_pos, p1_modifiers)
        self.player1.updatePosition(self.dt)
        
        # Update Player 2
        self.player2.handleInput()
        if self.player2.is_afk:
            # Calculate modifiers specifically for Player 2 AI
            p2_modifiers = self.heuristicAdapt(self.p2_score, self.p1_score, self.match_time_remaining)
            self.ai_manager.updateFSM(self.player2, self.player1, self.ball, self.p2_goal_pos, self.p1_goal_pos, p2_modifiers)
        self.player2.updatePosition(self.dt)

        # Apply Curve before linear friction
        if self.ball.vel.length() > 0:
            self.ball.vel = self.physics_engine.calculateCurve(self.ball.vel, self.ball.active_spin, self.ball.target_offset)
            
        self.ball.applyPhysics(self.dt)

        # Possession Update based on proximity and last touch
        if self.ball.last_touched_by:
            # Match the ID to the player object
            active_player = self.player1 if self.ball.last_touched_by == "p1" else self.player2
            
            # Maximum radius to be considered in possession
            possession_radius = 80.0 
            
            # Calculate distance between player and ball
            distance = (active_player.pos - self.ball.pos).length()
            
            # Only log time if they are within the radius
            if distance <= possession_radius:
                self.stats_tracker.log_possession(active_player.player_id, self.dt)

        # Resolve Collisions
        self.physics_engine.resolveBoundaryCollision(self.player1)
        self.physics_engine.resolveBoundaryCollision(self.player2)
        self.physics_engine.resolveBoundaryCollision(self.ball)
        
        self.physics_engine.checkPvPCollision(self.player1, self.player2)
        self.physics_engine.checkPvBCollision(self.player1, self.ball)
        self.physics_engine.checkPvBCollision(self.player2, self.ball)

        # WinCondition Check 
        self._checkGoalConditions()
    
    def _checkGoalConditions(self):
        # Private method that checks if the ball has crossed the goal lines
        goal_scored = False

        # Check Player 2 Scores (left goal)
        if self.ball.pos.x < 50:
            self.p2_score += 1
            goal_scored = True
            self.stats_tracker.log_goal("p2")
            self.particle_system.spawn_explosion(self.ball.pos.x, self.ball.pos.y, (100, 100, 255), count=50)
            print("Goal for Player 2!")

        # Check Player 1 (right goal)
        elif self.ball.pos.x > self.screen_width - 50:
            self.p1_score += 1
            goal_scored = True
            self.stats_tracker.log_goal("p1")
            self.particle_system.spawn_explosion(self.ball.pos.x, self.ball.pos.y, (255, 100, 100), count=50)
            print("Goal for Player 1!")

        # Blows whistle and resets pitch if goal scored
        if goal_scored:
            self.sound_manager.play_sfx("whistle")
            self._resetPositions()
        
        # Game Over Condition
        if self.match_time_remaining <= 0:
            self.is_game_over = True
            self.sound_manager.play_sfx("whistle") # End match whistle
            print("Match Finished!")
    
    def _resetPositions(self):
        # Resets entities to their kickoff positions after a goal
        self.ball.pos = pygame.Vector2(self.screen_width // 2, self.screen_height // 2)
        self.ball.vel = pygame.Vector2(0, 0)
        
        self.player1.pos = pygame.Vector2(400, 360)
        self.player1.vel = pygame.Vector2(0, 0)
        self.player1.power_charge_level = 0.0
        
        self.player2.pos = pygame.Vector2(880, 360)
        self.player2.vel = pygame.Vector2(0, 0)
        self.player2.power_charge_level = 0.0
    
    def renderScene(self):
        # Manages the visual stack and drawing elements in order
        # BG
        self.pitch_renderer.drawBackground(self.screen, self.asset_manager)

        # Entities
        self.ball.draw(self.screen, self.asset_manager)
        self.player1.drawAnimated(self.screen, self.asset_manager)
        self.player2.drawAnimated(self.screen, self.asset_manager)

        # VFX
        self.particle_system.draw(self.screen)

        # UI
        self._drawScoreBoard()

        if self.is_game_over:
            self._drawGameOverScreen()
        
        if self.is_paused:
            self._drawPauseMenu()

        pygame.display.flip()

    def _drawPauseMenu(self):
        # Renders a semi-transparent overlay and the pause state
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150)) 
        self.screen.blit(overlay, (0, 0))

        font = pygame.font.SysFont(None, 80)
        sub_font = pygame.font.SysFont(None, 40)

        title_surf = font.render("PAUSED", True, "white")
        self.screen.blit(title_surf, title_surf.get_rect(center=(self.screen_width // 2, self.screen_height // 2 - 50)))

        sub_surf = sub_font.render("Press 'ESC' or 'P' to Resume", True, (200, 200, 200))
        self.screen.blit(sub_surf, sub_surf.get_rect(center=(self.screen_width // 2, self.screen_height // 2 + 50)))

    def _drawScoreBoard(self):
        # Renders the current score at the top of the screen.
        font = pygame.font.SysFont(None, 48)
        
        # Render text surfaces
        p1_text = font.render(f"P1: {self.p1_score}", True, "red")
        p2_text = font.render(f"P2: {self.p2_score}", True, "blue")

        # Float to MM:SS
        minutes = int(self.match_time_remaining) // 60
        seconds = int(self.match_time_remaining) % 60
        # Ensure single digits have a leading zero
        time_text = font.render(f"{minutes:02d}:{seconds:02d}", True, "white")
        
        # Blit them to the top center of the screen
        self.screen.blit(p1_text, (self.screen_width // 2 - 200, 10))
        self.screen.blit(p2_text, (self.screen_width // 2 + 100, 10))

        # Draw timer in center
        time_rect = time_text.get_rect(center=(self.screen_width // 2, 25))
        self.screen.blit(time_text, time_rect)

    def _drawGameOverScreen(self):
        # Renders a semi-transparent overlay and the final win state
        # Overlay
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200)) 
        self.screen.blit(overlay, (0, 0))

        # fonts
        title_font = pygame.font.SysFont(None, 80)
        sub_font = pygame.font.SysFont(None, 40)
        stat_font = pygame.font.SysFont(None, 50)

        # Title
        if self.p1_score > self.p2_score:
            win_msg, text_color = "PLAYER 1 (RED) WINS!", (255, 100, 100)
        elif self.p2_score > self.p1_score:
            win_msg, text_color = "PLAYER 2 (BLUE) WINS!", (100, 100, 255)
        else:
            win_msg, text_color = "DRAW!", (200, 200, 200)
        
        title_surf = title_font.render(win_msg, True, text_color)
        self.screen.blit(title_surf, title_surf.get_rect(center=(self.screen_width // 2, 150)))

        # Fetch Stats
        p1_poss, p2_poss = self.stats_tracker.get_possession_percentages()
        p1_shots = self.stats_tracker.stats["p1"]["shots"]
        p2_shots = self.stats_tracker.stats["p2"]["shots"]

        # Stat Labels
        stats_data = [
            ("GOALS", str(self.p1_score), str(self.p2_score)),
            ("SHOTS", str(p1_shots), str(p2_shots)),
            ("POSSESSION", f"{p1_poss}%", f"{p2_poss}%")
        ]

        # Draw Stats Table
        start_y = 280
        for i, (label, p1_val, p2_val) in enumerate(stats_data):
            y_pos = start_y + (i * 60)
            
            # Label
            lbl_surf = stat_font.render(label, True, "white")
            self.screen.blit(lbl_surf, lbl_surf.get_rect(center=(self.screen_width // 2, y_pos)))
            
            # P1 Stat
            p1_surf = stat_font.render(p1_val, True, (255, 100, 100))
            self.screen.blit(p1_surf, p1_surf.get_rect(center=(self.screen_width // 2 - 200, y_pos)))
            
            # P2 Stat
            p2_surf = stat_font.render(p2_val, True, (100, 100, 255))
            self.screen.blit(p2_surf, p2_surf.get_rect(center=(self.screen_width // 2 + 200, y_pos)))
    
        # Restart Prompt
        sub_surf = sub_font.render("Press 'R' to Play Again", True, (200, 255, 200))
        self.screen.blit(sub_surf, sub_surf.get_rect(center=(self.screen_width // 2, self.screen_height - 120)))

        exit_surf = sub_font.render("Press 'ESC' to Save & Return to Main Menu", True, (255, 200, 200))
        self.screen.blit(exit_surf, exit_surf.get_rect(center=(self.screen_width // 2, self.screen_height - 70)))

    def runMatchLoop(self):
        self.initialiseGame()
        running = True
        
        while running:
            # Update dt
            self.dt = self.clock.tick(self.fps) / 1000.0 

            signal = self.handleMainEvents()
            if signal == "EXIT_TO_MENU":
                # Save stats before leaving
                self.saveStatsAndHistory()
                running = False
                continue

            self.updateMatchState()
            self.renderScene()

    def saveStatsAndHistory(self):
        # Dedicated method to save data without quitting
        user_id = launcher_backend.active_user_session
        if user_id:
            final_stats = self.stats_tracker.stats.get("p1")
            # Derive the key from the password (still stored in buffer)
            derived_key = hashlib.sha256(menu_system.password_buffer.strip().replace(" ", "").encode('utf-8')).digest()
            fernet_key = base64.urlsafe_b64encode(derived_key)
            
            encrypted_data = EncryptionEngine.encryptData(final_stats, fernet_key)
            if encrypted_data:
                with open(launcher_backend.userdata_path, 'r') as f:
                    user_db = json.load(f)
                user_db[user_id] = encrypted_data
                with open(launcher_backend.userdata_path, 'w') as f:
                    json.dump(user_db, f, indent=4)
                print(f"Progress saved for {user_id}.")
        
        if hasattr(self, 'ai_manager') and hasattr(self.ai_manager, 'pattern_analyser'):
            self.ai_manager.pattern_analyser.saveHistory()

    def terminateGame(self):
        # Clears memory, autosaves data and quits safely
        self.saveStatsAndHistory()
        pygame.quit()
        sys.exit()

    def _resetMatch(self):
        # Reset scores and unflag the game state.
        self.p1_score = 0
        self.p2_score = 0
        self.is_game_over = False


class AIManager:
    # Manages transitions between Attack, Defend, and Intercept states
    def __init__(self, pitch_bounds):
        self.pitch_bounds = pitch_bounds
        self.current_state = "INTERCEPT"
        self.target_pos = pygame.Vector2(0, 0)
        self.pattern_analyser = PatternAnalyser(pitch_bounds)
        self.current_bias_data = None
        
        # Reaction & Shoot variables
        self.reaction_timer = 0.0
        self.shoot_timer = 0.0

    def predictIntercept(self, P_b, V_b, P_ai, S_ai):
        # Kinematics that predict ball location with friction
        
        # Friction constant from Ball class
        friction = 0.98
        
        # Calculate Current Distance
        direction_vector = P_b - P_ai
        D = direction_vector.length()
        
        # Estimate Intercept Time
        if S_ai > 0:
            delta_t = D / S_ai
        else:
            delta_t = 0.0
            
        # Ball displacement with friction: sum(v * friction^t)
        # Approximate: P_target = P_b + V_b * (1 - friction^delta_t) / (1 - friction)
        # But for small delta_t, let's use a simpler decay:
        decay = (1.0 - math.pow(friction, delta_t * 60)) / (1.0 - friction) / 60.0
        P_target = P_b + (V_b * decay)
        
        # Clamp P_target to Pitch Boundary
        P_target.x = max(self.pitch_bounds.left, min(P_target.x, self.pitch_bounds.right))
        P_target.y = max(self.pitch_bounds.top, min(P_target.y, self.pitch_bounds.bottom))
        
        return P_target

    def updateFSM(self, ai_player, opponent, ball, my_goal_pos, enemy_goal_pos, modifiers):
        # A Finite State Machine for non-linear decision-making
        
        # Read Player.pos, Ball.pos, GameState, and Score
        # is player AFK?
        if not ai_player.is_afk:
            return # Manual Controlc

        # Fixed dt for AI logic
        dt = 1/60.0 
        
        # Decide whether to RECALCULATE state/target
        recalculate = True
        if self.reaction_timer > 0:
            self.reaction_timer -= dt
            recalculate = False # Keep moving toward last target

        # Adjust Difficulty
        adjusted_speed = ai_player.speed * modifiers["max_velocity_mult"]
        reaction_delay = modifiers.get("reaction_delay", 0.0)

        if recalculate:
            # Determine Possession using distance
            dist_to_ball = (ai_player.pos - ball.pos).length()
            ai_has_ball = dist_to_ball <= 100 # Slightly larger detection for AI state
            user_has_ball = (opponent.pos - ball.pos).length() <= 80
            
            # Decision Gates
            if ai_has_ball:
                self.current_state = "ATTACK"
                
                # POSITIONAL LOGIC: Get behind the ball relative to the enemy goal
                # Calculate vector from ball to enemy goal
                ball_to_goal = (enemy_goal_pos - ball.pos).normalize()
                # Target point is slightly behind the ball
                behind_ball_pos = ball.pos - ball_to_goal * 40 
                
                dist_to_goal = (ai_player.pos - enemy_goal_pos).length()
                
                if (ai_player.pos - behind_ball_pos).length() > 30:
                    # Move to the "behind ball" position first
                    self.target_pos = behind_ball_pos
                elif dist_to_goal > 250:
                    self.target_pos = self.processHeatmap(ai_player.pos, opponent.pos, enemy_goal_pos)
                else:
                    self.target_pos = enemy_goal_pos
                    
                    # Shooting Logic
                    if dist_to_ball < 45:
                        if self.shoot_timer <= 0:
                            ai_player.is_charging = True
                            self.shoot_timer = 0.5 
                        else:
                            self.shoot_timer -= dt
                            if self.shoot_timer <= 0.1:
                                ai_player.is_charging = False
                
            elif user_has_ball:
                self.current_state = "DEFEND"
                ai_player.is_charging = False
                self.shoot_timer = 0
                
                # Midpoint of ball and goal
                base_target = (ball.pos + my_goal_pos) / 2 
                
                # Apply Defensive Bias if the Pattern Threshold is met
                if self.current_bias_data and self.current_bias_data["bias_active"]:
                    favored_sector = self.current_bias_data["favored_sector"]
                    
                    # Calculate the center coordinates of the user's favored sector
                    sector_w = self.pitch_bounds.width / 4
                    sector_h = self.pitch_bounds.height / 4
                    col = favored_sector % 4
                    row = favored_sector // 4
                    
                    bias_x = self.pitch_bounds.left + (col * sector_w) + (sector_w / 2)
                    bias_y = self.pitch_bounds.top + (row * sector_h) + (sector_h / 2)
                    bias_vector = pygame.Vector2(bias_x, bias_y)
                    
                    # Shift the defensive target 30% toward the user's favored zone
                    self.target_pos = base_target.lerp(bias_vector, 0.3)
                else:
                    self.target_pos = base_target
                
            else:
                self.current_state = "INTERCEPT"
                ai_player.is_charging = False
                self.shoot_timer = 0
                
                # POSITIONAL LOGIC: Intercept behind the ball
                raw_intercept = self.predictIntercept(ball.pos, ball.vel, ai_player.pos, adjusted_speed)
                ball_to_goal = (enemy_goal_pos - raw_intercept).normalize()
                self.target_pos = raw_intercept - ball_to_goal * 30

            # Set Reaction Delay for next decision cycle
            if reaction_delay > 0:
                self.reaction_timer = reaction_delay

        # MOVEMENT: Apply current target pos (calculated or cached)
        move_vector = pygame.Vector2(0, 0)
        distance_to_target = (self.target_pos - ai_player.pos).length()
        
        if distance_to_target > 10: # Lowered jitter threshold
            move_vector = (self.target_pos - ai_player.pos).normalize()

        ai_player.vel = move_vector
        ai_player.current_speed = adjusted_speed

        # Stamina Heuristic
        if distance_to_target > 150 and ai_player.stamina > 20.0:
            ai_player.is_sprinting = True
        else:
            ai_player.is_sprinting = False
    
    def processHeatmap(self, ai_pos, opponent_pos, enemy_goal_pos):
        # Finds the smartest open grid that the AI should run to
        
        # Divide the pitch into a 4x4 grid
        cols, rows = 4, 4
        sector_w = self.pitch_bounds.width / cols
        sector_h = self.pitch_bounds.height / rows
        
        heatmap = {}
        
        for c in range(cols):
            for r in range(rows):
                sector_id = (r * cols) + c
                
                # Find the center coordinates of the current cell
                cell_x = self.pitch_bounds.left + (c * sector_w) + (sector_w / 2)
                cell_y = self.pitch_bounds.top + (r * sector_h) + (sector_h / 2)
                cell_pos = pygame.Vector2(cell_x, cell_y)
                
                score = 0.0
                
                # Goal Proximity values
                # Cells closer to the enemy goal get a higher base score
                dist_to_goal = (cell_pos - enemy_goal_pos).length()
                score += max(0, 1000 - dist_to_goal) 
                
                # Apply Negative Weights
                # Heavily penalize cells that are too close to the human defender
                dist_to_opponent = (cell_pos - opponent_pos).length()
                if dist_to_opponent < 150: 
                    score -= 500
                    
                # Save the evaluated cell
                heatmap[sector_id] = {"score": score, "pos": cell_pos}
                
        # Attack Bias
        if self.current_bias_data and self.current_bias_data["bias_active"]:
            # Yes -> Apply Weight Bias
            favored_sector = self.current_bias_data["favored_sector"]
            if favored_sector in heatmap:
                heatmap[favored_sector]["score"] += 300 

        # Recalculation
        target_set = False
        p_target = pygame.Vector2(enemy_goal_pos) # Fallback target
        
        while not target_set and len(heatmap) > 0:
            # Identify Max Value Cell
            best_sector = max(heatmap, key=lambda k: heatmap[k]["score"])
            best_cell_pos = heatmap[best_sector]["pos"]
            
            # Is Cell Reachable? (can AI get there before user)
            ai_dist = (best_cell_pos - ai_pos).length()
            opp_dist = (best_cell_pos - opponent_pos).length()
            
            if ai_dist < opp_dist + 50: # +50 provides a slight leniency buffer
                # Yes -> Set target
                p_target = best_cell_pos
                target_set = True
            else:
                # Remove the unreachable cell and try the next highest scoring one
                del heatmap[best_sector]
                
        # Return P_target
        return p_target


class GameObject:
    # Base parent class for all entities ingame that instantiates common attributes
    def __init__(self, start_pos):
        self.pos = pygame.Vector2(start_pos)
        self.vel = pygame.Vector2(0, 0)


class Player(GameObject):
    # Child class that adds input/animation logic and inherits some attributes from the GameObject class
    def __init__(self, sound_manager, player_id, start_pos, controls, stats):
        super().__init__(start_pos) # Initialise the parent constructor

        # Identity variables
        self.player_id = player_id
        self.controls = controls
        self.sound_manager = sound_manager
        self.speed = stats.get("speed", 250)
        self.sprint_speed = stats.get("sprint_speed", 380)
        self.current_speed = self.speed
        self.radius = 20
        self.spin = stats.get("spin", 1.0)
        self.strength = stats.get("strength", 1.0)

        # Stamina variables
        self.max_stamina = stats.get("max_stamina", 100.0)
        self.stamina = self.max_stamina
        self.sprint_decay_rate = 25.0       # Depletes in 4s
        self.stamina_recharge_rate = 15.0   # Recharges in ~6.6s
        self.stamina_recharge_delay = 2.0   # Delay of 2s before recharging
        self.recharge_timer = 0.0
        self.is_sprinting = False

        # PowerShot Variables
        self.power_charge_level = 0.0
        self.MAX_CHARGE = 1.5  # Seconds to reach max power
        self.is_charging = False

        # Animation state variables
        self.anim_state = "IDLE"
        self.sfc = 0
        self.eta = 0.0
        self.frame_rate = 0.15
        self.current_angle = 0

        # Animation Math variables
        self.walk_timer = 0.0
        self.stride_speed = 15.0  
        self.stride_length = 12.0 
        self.stance_width = 14

        # We define the number of frames each state should display for
        self.frames_per_state = {
            "IDLE": 1,
            "WALK_UP": 4,
            "WALK_DOWN": 4,
            "WALK_LEFT": 4,
            "WALK_RIGHT": 4
        }

        # AFK + Input Buffer Variables
        self.input_buffer = []           # An Array that will use Queue logic to hold timestamps
        self.max_buffer_size = 10        # Memory constraint
        self.is_afk = False
        self.afk_threshold = 3.0
        self.last_input_time = pygame.time.get_ticks() / 1000.0

    def handleInput(self):
        # Reads keyboard interrupts and modifies velocity vector and encapsulates the player controls

        keys = pygame.key.get_pressed()
        self.vel.update(0, 0) # Resets velocity each frame so that it is not accelerated by mistake
        self.is_sprinting = False # Reset sprint state every frame
        self.is_charging = False # Reset charge state

        if self.controls == "WASD":
            if keys[pygame.K_w]: self.vel.y = -1
            if keys[pygame.K_s]: self.vel.y = 1
            if keys[pygame.K_a]: self.vel.x = -1
            if keys[pygame.K_d]: self.vel.x = 1
            if keys[pygame.K_LSHIFT]: self.is_sprinting = True
            if keys[pygame.K_SPACE]: self.is_charging = True
        elif self.controls == "ARROWS":
            if keys[pygame.K_UP]: self.vel.y = -1
            if keys[pygame.K_DOWN]: self.vel.y = 1
            if keys[pygame.K_LEFT]: self.vel.x = -1
            if keys[pygame.K_RIGHT]: self.vel.x = 1
            if keys[pygame.K_RSHIFT]: self.is_sprinting = True
            if keys[pygame.K_RETURN]: self.is_charging = True

        # Update Input Buffer + State 
        current_time = pygame.time.get_ticks() / 1000.0
        input_detected = (self.vel.length() > 0) or self.is_sprinting or self.is_charging

        if input_detected:
            self.last_input_time = current_time
            self.input_buffer.append(current_time)
            
            # Capacity Limit
            if len(self.input_buffer) > self.max_buffer_size:
                self.input_buffer.pop(0) # Dequeue oldest input
            
            self.is_afk = False
        
        # Makes sure that players don't move faster if 2 keys are pressed at the same time.
        if self.vel.length() > 0:
            self.vel = self.vel.normalize()
        else:
            self.is_sprinting = False # no sprinting when standing still
    

    def checkAFK(self):
        # Determines if control should be given to AI
        current_time = pygame.time.get_ticks() / 1000.0
        
        # Get data from the Queue
        if len(self.input_buffer) > 0:
            most_recent_input = self.input_buffer[-1]
        else:
            most_recent_input = self.last_input_time # Fallback to game start
            
        idle_delta = current_time - most_recent_input
        
        # Ensure the threshold is met
        if idle_delta > self.afk_threshold:
            if not self.is_afk:
                print(f"DEBUG: Player {self.player_id} is AFK. Bot taking over.")
            self.is_afk = True


    def updatePosition(self, dt):
        # Updates player coordinates and decides which animation state/frame should be active

        # Update Stamina
        self.updateStamina(dt)

        # PowerShot Charging
        if self.is_charging and self.stamina > 5.0: # minimum stamina
            self.power_charge_level += dt
            if self.power_charge_level > self.MAX_CHARGE:
                self.power_charge_level = self.MAX_CHARGE
        else:
            # Decay the charge if button is released before hitting the ball
            if self.power_charge_level > 0:
                self.power_charge_level -= dt * 3
                if self.power_charge_level < 0:
                    self.power_charge_level = 0.0
        
        # Updates Movement
        self.pos += self.vel * self.current_speed * dt

        # Determines Animation State
        new_state = "IDLE"
        if self.vel.length() > 0:
            if abs(self.vel.x) > abs(self.vel.y):
                new_state = "WALK_RIGHT" if self.vel.x > 0 else "WALK_LEFT"
            else:
                new_state = "WALK_DOWN" if self.vel.y > 0 else "WALK_UP"
            
            self.walk_timer += dt * self.stride_speed
        else:
            self.walk_timer = 0.0

        self.anim_state = new_state
        
        # Transitions between States
        if new_state != self.anim_state:
            self.anim_state = new_state
            self.sfc = 0
            self.eta = 0.0
        
        # Moving the frames
        self.eta += dt
        if self.eta >= self.frame_rate:
            self.eta = 0.0
            self.sfc += 1
            # makes sure sfc doesn't exceed available frames
            max_frames = self.frames_per_state.get(self.anim_state, 1)
            if self.sfc >= max_frames:
                self.sfc = 0
    
    def updateStamina(self, dt):
        # Decreases stamina when sprinting and recharges when standing/walking
        if self.is_sprinting and self.stamina > 0:
            self.stamina -= self.sprint_decay_rate * dt
            self.recharge_timer = self.stamina_recharge_delay
            self.current_speed = self.sprint_speed
            
            # Prevent negative stamina
            if self.stamina <= 0:
                self.stamina = 0
                self.current_speed = self.speed # Force walking if exhausted
        else:
            self.current_speed = self.speed
            
            # Wait for delay, then recharge
            if self.recharge_timer > 0:
                self.recharge_timer -= dt
            elif self.stamina < self.max_stamina:
                self.stamina += self.stamina_recharge_rate * dt
                if self.stamina > self.max_stamina:
                    self.stamina = self.max_stamina
    
    def applyStaminaCost(self, cost):
        # Subtracts stamina for certain actions
        if self.stamina >= cost:
            self.stamina -= cost
            self.recharge_timer = self.stamina_recharge_delay
            return True
        return False

    def drawAnimated(self, screen, graphics_manager):
        # Requests and renders correct frames in the correct order
        
        # Requests specfic player's images
        foot_img = graphics_manager.get_image(f"{self.player_id}_foot") 
        body_img = graphics_manager.get_image(f"{self.player_id}_body")
        
        # Update current angle based on movement state
        if self.anim_state == "WALK_UP": self.current_angle = 90
        elif self.anim_state == "WALK_DOWN": self.current_angle = 270
        elif self.anim_state == "WALK_LEFT": self.current_angle = 180
        elif self.anim_state == "WALK_RIGHT": self.current_angle = 0

        # Play sound when the sine wave is at maximum displacement
        if self.anim_state != "IDLE":
            if abs(math.sin(self.walk_timer)) > 0.98:
                # Lower volume for walking vs sprinting
                vol = 0.3 if not self.is_sprinting else 0.5
                self.sound_manager.play_sfx("walk", vol)

        # Rotate images 
        body_rotated = pygame.transform.rotate(body_img, self.current_angle)
        foot_rotated = pygame.transform.rotate(foot_img, self.current_angle)

        # Math for walking
        center_x, center_y = int(self.pos.x), int(self.pos.y)
        stride_offset = math.sin(self.walk_timer) * self.stride_length
        body_bob = abs(math.sin(self.walk_timer)) * 3

        # Draw feet
        if self.current_angle in [90, 270]:
            # Vertical
            screen.blit(foot_rotated, foot_rotated.get_rect(center=(center_x - self.stance_width, center_y + stride_offset)))
            screen.blit(foot_rotated, foot_rotated.get_rect(center=(center_x + self.stance_width, center_y - stride_offset)))
        else:
            # Horizontal
            screen.blit(foot_rotated, foot_rotated.get_rect(center=(center_x + stride_offset, center_y - self.stance_width)))
            screen.blit(foot_rotated, foot_rotated.get_rect(center=(center_x - stride_offset, center_y + self.stance_width)))
        
        # Draw body on top
        screen.blit(body_rotated, body_rotated.get_rect(center=(center_x, center_y - body_bob)))

        # Render stamina bar above body
        bar_width = 40
        fill_width = int((self.stamina / self.max_stamina) * bar_width)
        pygame.draw.rect(screen, "black", (center_x - 20, center_y - 35, bar_width, 5))
        pygame.draw.rect(screen, "yellow", (center_x - 20, center_y - 35, fill_width, 5))

        # Render Charge Bar
        if self.power_charge_level > 0:
            charge_width = int((self.power_charge_level / self.MAX_CHARGE) * bar_width)
            pygame.draw.rect(screen, "orange", (center_x - 20, center_y - 42, charge_width, 4))


class Ball(GameObject):
    # Child class representing the football. Inherits pos and vel from GameObject, adds friction and the rolling animation
    def __init__(self, start_pos):
        super().__init__(start_pos)

        # Constants for physics maths
        self.radius = 20
        self.friction = 0.98
        self.stop_threshold = 5.0

        # Animation Variables
        self.sfc = 0
        self.eta = 0.0
        self.frame_rate = 0.1
        self.total_frames = 4

        # Possession Variables
        self.last_touched_by = None
        
        # Spin & Rotation Variables
        self.active_spin = 0.0
        self.target_offset = 0.0 
        self.rotation_angle = 0.0
    
    def applyPhysics(self, dt):
        #Updates the ball's position and simulates friction.
        # Apply Movement
        self.pos += self.vel * dt

        # Apply Friction
        self.vel *= self.friction

        # Update Rotation based on movement
        speed = self.vel.length()
        if speed > self.stop_threshold:
            # Distance moved = r * theta -> theta = d / r
            self.rotation_angle -= (speed * dt * 2.0)
            if self.rotation_angle < 0:
                self.rotation_angle += 360

        # Stop the ball completely if it's moving extremely slowly
        if self.vel.length() < self.stop_threshold:
            self.vel.update(0, 0)

        # Calculate Rolling Animation Speed
        self._updateAnimation(dt)

    def _updateAnimation(self, dt):
        # Private method to handle variable ball animation.
        speed = self.vel.length()
        
        if speed > 0:
            # use max() to prevent zero division or negative time errors
            dynamic_frame_rate = max(0.02, self.frame_rate - (speed * 0.0001))
            
            self.eta += dt
            if self.eta >= dynamic_frame_rate:
                self.eta = 0.0
                self.sfc += 1
                
                # Loop the rotation animation
                if self.sfc >= self.total_frames:
                    self.sfc = 0

    def draw(self, screen, graphics_manager):
        # Renders the ball
        ball_img = graphics_manager.get_image("ball")
        if ball_img:
            rotated_ball = pygame.transform.rotate(ball_img, self.rotation_angle)
            rect = rotated_ball.get_rect(center=(int(self.pos.x), int(self.pos.y)))
            screen.blit(rotated_ball, rect)
        else:
            pygame.draw.circle(screen, "white", (int(self.pos.x), int(self.pos.y)), self.radius)


class SoundManager:
    def __init__(self, audio_path="assets/audio"):
        base_path = os.path.dirname(os.path.abspath(__file__))
        self.path = os.path.join(base_path, audio_path)
        self.sounds = {}
        self.impacts = []
        self.chants = []
        
        # Initialize mixer
        if not pygame.mixer.get_init():
            pygame.mixer.init()

        self.load_assets()    
        # Channel for the chants
        self.crowd_channel = pygame.mixer.Channel(0)

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
        if not self.crowd_channel.get_busy() and self.chants:
            next_chant = pygame.mixer.Sound(random.choice(self.chants))
            self.crowd_channel.set_volume(0.4) # Background level
            self.crowd_channel.play(next_chant)


class AnimationManager:
    # Loads, slices, and returns animated sprites. Uses Singleton-like pattern
    
    def __init__(self,asset_dir):
        base_path = os.path.dirname(os.path.abspath(__file__))
        self.asset_dir = os.path.join(base_path, asset_dir)
        self.images = {} # one dictionary holds everything

        self._loadAllAssets()
    
    def _loadAllAssets(self):
        # Loads the specific files needed for Player 1, Player 2, and the Pitch
        # Player 1 (red)
        self.images["p1_body"] = self._loadImage("players/red/red_body.png")
        self.images["p1_foot"] = self._loadImage("players/red/red_foot.png")
        
        # Player 2 (blue)
        self.images["p2_body"] = self._loadImage("players/blue/blue_body.png")
        self.images["p2_foot"] = self._loadImage("players/blue/blue_foot.png")
        
        # Pitch and ball
        self.images["grass"] = self._loadImage("pitch/grass.png")
        self.images["ball"] = self._loadImage("pitch/ball.png")
        
    def _loadImage(self, filename):
        # loads a single image and handles missing files
        filepath = os.path.join(self.asset_dir, filename)
        try:
            return pygame.image.load(filepath).convert_alpha()
        except FileNotFoundError:
            print(f"WARNING: Could not find {filepath}")
            # Fallback square so the game doesn't crash
            fallback = pygame.Surface((40, 40), pygame.SRCALPHA)
            pygame.draw.rect(fallback, "magenta", (0, 0, 40, 40))
            return fallback
        
    def get_image(self, image_id):
        #Fetches an image by its simple string ID.
        return self.images.get(image_id)


class StatsTracker:
    def __init__(self):
        # Dictionary that separates player stats
        self.stats = {
            "p1": {"goals": 0, "shots": 0, "possession_time": 0.0},
            "p2": {"goals": 0, "shots": 0, "possession_time": 0.0}
        }

    # Logs player statistics in the dict
    def log_possession(self, player_id, dt):
        if player_id in self.stats:
            self.stats[player_id]["possession_time"] += dt

    def log_shot(self, player_id):
        if player_id in self.stats:
            self.stats[player_id]["shots"] += 1

    def log_goal(self, player_id):
        if player_id in self.stats:
            self.stats[player_id]["goals"] += 1

    def get_possession_percentages(self):
        # Calculates and returns integer percentages for GameEnd UI
        p1_time = self.stats["p1"]["possession_time"]
        p2_time = self.stats["p2"]["possession_time"]
        total = p1_time + p2_time
        
        if total == 0:
            return 50, 50 # If no one touched the ball
            
        p1_percent = int((p1_time / total) * 100)
        p2_percent = 100 - p1_percent # Ensures it always equals 100%
        return p1_percent, p2_percent


class PatternAnalyser:
    # Adds AI Adaptation methods by tracking where the user hits the balls the most
    def __init__(self, pitch_bounds):
        self.pitch_bounds = pitch_bounds
        
        # Maps Sector IDs (0-15) to hit frequencies.
        self.SectorHistory = {i: 0 for i in range(16)} 
        
        self.PatternThreshold = 5 
        self.history_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_history.json")
        self.loadHistory()

    def loadHistory(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                    # Convert string keys back to int
                    self.SectorHistory = {int(k): v for k, v in data.items()}
                    print("AI History Loaded Successfully.")
            except Exception as e:
                print(f"Warning: AI History Load Failed: {e}")

    def saveHistory(self):
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.SectorHistory, f, indent=4)
                print("AI History Saved Successfully.")
        except Exception as e:
            print(f"Error: AI History Save Failed: {e}")

    def analyseUserPattern(self, ball_pos, player_pos):
        # Analyses the places where the user shoots from the most

        # Prevents KeyError crashes if the ball is struck outside the pitch bounds
        if not self.pitch_bounds.collidepoint(ball_pos.x, ball_pos.y):
            return None 
            
        # Divide the pitch into 4 columns and 4 rows
        sector_w = self.pitch_bounds.width / 4
        sector_h = self.pitch_bounds.height / 4
        
        # Map coordinates to Pitch Sector ID
        col = int((ball_pos.x - self.pitch_bounds.left) // sector_w)
        row = int((ball_pos.y - self.pitch_bounds.top) // sector_h)
        
        # Clamp values to ensure they remain between 0 and 3
        col = max(0, min(col, 3))
        row = max(0, min(row, 3))
        
        sector_id = (row * 4) + col
        
        # Increment hit count in SectorHistory map
        self.SectorHistory[sector_id] += 1
        
        attack_bias = None
        
        # If hits > Pattern
        if self.SectorHistory[sector_id] > self.PatternThreshold:
            # Calculate New Attack Bias
            attack_bias = sector_id
            
        # Finds the user's most favored sector overall
        favored_sector = max(self.SectorHistory, key=self.SectorHistory.get)
        
        bias_data = {
            "latest_sector": sector_id,
            "favored_sector": favored_sector,
            "bias_active": attack_bias is not None
        }
        
        # Return Bias Data to AIManager
        return bias_data


class ParticleSystem:
    # Manages a collection of particles for visual feedback (VFX)
    def __init__(self):
        self.particles = []

    def spawn_explosion(self, x, y, color, count=20, speed_range=(50, 200)):
        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(speed_range[0], speed_range[1])
            vel = pygame.Vector2(math.cos(angle) * speed, math.sin(angle) * speed)
            lifetime = random.uniform(0.5, 1.2)
            size = random.randint(2, 6)
            self.particles.append({
                "pos": pygame.Vector2(x, y),
                "vel": vel,
                "color": color,
                "life": lifetime,
                "max_life": lifetime,
                "size": size
            })

    def update(self, dt):
        for p in self.particles[:]:
            p["pos"] += p["vel"] * dt
            p["life"] -= dt
            if p["life"] <= 0:
                self.particles.remove(p)

    def draw(self, screen):
        for p in self.particles:
            alpha = int((p["life"] / p["max_life"]) * 255)
            # Create a surface for transparency
            s = pygame.Surface((p["size"]*2, p["size"]*2), pygame.SRCALPHA)
            color = list(p["color"]) + [alpha]
            pygame.draw.circle(s, color, (p["size"], p["size"]), p["size"])
            screen.blit(s, (int(p["pos"].x - p["size"]), int(p["pos"].y - p["size"])))


class PhysicsEngine:
    # Dedicated module for spatial validation and collision resolution
    def __init__(self, pitch_rect, sound_manager, stats_tracker, ai_manager, particle_system):
        self.pitch_bounds = pitch_rect
        self.sound_manager = sound_manager
        self.stats_tracker = stats_tracker
        self.ai_manager = ai_manager
        self.particle_system = particle_system
    
    def resolveBoundaryCollision(self, entity):
        # Prevents sprites from leaving the pitch

        # Goal zone logic
        mid_y = self.pitch_bounds.top + (self.pitch_bounds.height // 2) 
        in_goal_y = (entity.pos.y > mid_y - 60 + entity.radius) and (entity.pos.y < mid_y + 60 - entity.radius)
        is_ball = hasattr(entity, 'friction')
        can_score = in_goal_y and is_ball
        
        # x-axis Boundaries
        if entity.pos.x - entity.radius < self.pitch_bounds.left:
            if not can_score: # Only bounce if it's not entering the goal
                entity.pos.x = self.pitch_bounds.left + entity.radius
                if is_ball: 
                    entity.vel.x *= -1 
                    self.sound_manager.play_impact()
                
        elif entity.pos.x + entity.radius > self.pitch_bounds.right:
            if not can_score: # Only bounce if it's not entering the goal
                entity.pos.x = self.pitch_bounds.right - entity.radius
                if is_ball:
                    entity.vel.x *= -1
                    self.sound_manager.play_impact()

        # y-axis Boundaries
        if entity.pos.y - entity.radius < self.pitch_bounds.top:
            entity.pos.y = self.pitch_bounds.top + entity.radius
            if is_ball:
                entity.vel.y *= -1
                self.sound_manager.play_impact()
                
        elif entity.pos.y + entity.radius > self.pitch_bounds.bottom:
            entity.pos.y = self.pitch_bounds.bottom - entity.radius
            if is_ball:
                entity.vel.y *= -1
                self.sound_manager.play_impact()
    
    def checkPvPCollision(self, player1, player2):
        # Resolves overlap between two players.
        # Calculate the vector between the two centers
        distance_vector = player1.pos - player2.pos
        distance = distance_vector.length()
        
        # Check if distance is less than their combined radii
        min_distance = player1.radius + player2.radius
        
        if distance < min_distance:
            # Prevent division by zero
            if distance == 0:
                distance_vector = pygame.Vector2(1, 0)
                distance = 1

            # Calculate depth of overlap
            overlap = min_distance - distance
            
            # Push them apart
            push_vector = distance_vector.normalize() * (overlap / 2)
            p1_target = player1.pos + push_vector
            p2_target = player2.pos - push_vector

            # Player 1 is pushed toward p1_target, resisting based on Player 1's strength
            self.applyDisplacement(
                physics_body=player1, 
                target_pos=p1_target, 
                current_pos=player1.pos, 
                displacement_weight=player1.strength, 
                max_velocity=player1.sprint_speed
            )
            
            # Player 2 is pushed toward p2_target, resisting based on Player 2's strength
            self.applyDisplacement(
                physics_body=player2, 
                target_pos=p2_target, 
                current_pos=player2.pos, 
                displacement_weight=player2.strength, 
                max_velocity=player2.sprint_speed
            )
        
    
    def checkPvBCollision(self, player, ball):
        # Handles the kick logic
        distance_vector = ball.pos - player.pos
        distance = distance_vector.length()
        
        min_distance = player.radius + ball.radius
        
        if distance < min_distance:
            if distance == 0:
                distance_vector = pygame.Vector2(1, 0)
                distance = 1

            # Separate them so the ball doesn't get stuck inside the player
            overlap = min_distance - distance
            push_vector = distance_vector.normalize() * overlap
            ball.pos += push_vector
            
            # Calculate the Kick
            kick_direction = distance_vector.normalize()
            
            # Add base kick power, plus extra power if the player was running
            base_power = 400
            momentum = player.vel.length() * 0.5

            # Kick Sound
            self.sound_manager.play_sfx("kick")

            # Update Possession
            ball.last_touched_by = player.player_id

            # Powershot Logic
            multiplier = 1.0
            if player.power_charge_level > 0.1:
                # Calculate cost based on charge
                shot_cost = (player.power_charge_level / player.MAX_CHARGE) * 30.0
                
                # Apply the stamina cost
                if player.applyStaminaCost(shot_cost):
                    # Increase multiplier based on charge
                    multiplier = 1.0 + (player.power_charge_level * 1.5)
                    
                    # Reset charge if successful
                    player.power_charge_level = 0.0

                    # Logs shot
                    self.stats_tracker.log_shot(player.player_id)
                    
                    # Spawn charged particles
                    color = (255, 200, 50) if player.player_id == "p1" else (50, 200, 255)
                    self.particle_system.spawn_explosion(ball.pos.x, ball.pos.y, color, count=15, speed_range=(100, 300))
            else:
                # Spawn regular sparks
                self.particle_system.spawn_explosion(ball.pos.x, ball.pos.y, (255, 255, 255), count=5, speed_range=(20, 80))

            # Final Velocity
            ball.vel = kick_direction * (base_power + momentum) * multiplier

            # Add Curve 
            ball.active_spin = player.spin
            
            # Determine curve direction (target_offset) based on player's lateral movement
            cross_product = kick_direction.x * player.vel.y - kick_direction.y * player.vel.x
            
            if cross_product > 0.1:
                ball.target_offset = 1.0  
            elif cross_product < -0.1:
                ball.target_offset = -1.0  
            else:
                ball.target_offset = 0.0  
            
            # Only track the user patterns not the AI
            if not player.is_afk:
                # Trigger the analysis and send bias data to AIManager
                bias_data = self.ai_manager.pattern_analyser.analyseUserPattern(ball.pos, player.pos)
                if bias_data:
                    self.ai_manager.current_bias_data = bias_data


    def calculateCurve(self, velocity, spin_attribute, target_offset):
        # Adds a curve effect to the ball when kicked
        if velocity.length() == 0:
            return velocity
            
        # Calculate Perpendicular Magnus Force vector (swap x and y to -y and x for perpendicular vector)
        perp_vector = pygame.Vector2(-velocity.y, velocity.x).normalize()
        
        # Apply Spin Attribute multiplier to Curvature Intensity
        curvature_intensity = spin_attribute * target_offset
        magnus_force = perp_vector * curvature_intensity
        
        # Is Spin > Aerodynamic Threshold
        aerodynamic_threshold = 0.5
        MAX_CURVE = 8.0
        
        if abs(spin_attribute) > aerodynamic_threshold:
            # Calculate Trajectory Deviation
            deviation = magnus_force
            
            # Magnitude must be lower than a MAX_CURVE constant
            if deviation.length() > MAX_CURVE:
                deviation = deviation.normalize() * MAX_CURVE
                
            # Apply calculated Offset to Ball Velocity components
            updated_velocity = velocity + deviation
        else:
            # Maintain Linear Path
            updated_velocity = pygame.Vector2(velocity)
            
        # Return Updated Velocity Vector
        return updated_velocity
    
    def applyDisplacement(self, physics_body, target_pos, current_pos, displacement_weight, max_velocity):
        # Applies push force against the 2 sprites when in contact
        
        # Calculate Displacement Vector
        d = target_pos - current_pos
        
        # Scale Vector by DisplacementWeight
        d *= displacement_weight
        
        # Normalize and Clamp to MaxVelocity
        if d.length() > max_velocity:
            d = d.normalize() * max_velocity
            
        # Apply resulting Vector to Sprite Physics Body
        physics_body.vel = pygame.Vector2(d)
        physics_body.pos += d
        
        return physics_body.vel, physics_body.pos


class PitchRenderer:
    # Handles the static background rendering
    def __init__(self, screen_width, screen_height):
        self.width = screen_width
        self.height = screen_height
        
        # Styling
        self.line_color = (240, 255, 240)
        self.line_thickness = 4
    
    def drawBackground(self, screen, asset_manager):
        # Tiles the grass and draws the lines.
        self._tileGrass(screen, asset_manager)
        self.drawPitchMarkings(screen)

    def _tileGrass(self, screen, asset_manager):
        # Fills in the screen with a single small texture
        grass_tile = asset_manager.get_image("grass")
        tile_width, tile_height = grass_tile.get_size()

        # Loop across the x and y axes
        for x in range(0, self.width, tile_width):
            for y in range(0, self.height, tile_height):
                screen.blit(grass_tile, (x, y))
    
    def drawPitchMarkings(self,screen):
        # Draws the lines of a football pitch
        mid_x = self.width // 2
        mid_y = self.height // 2

        # Outer Boundary
        pygame.draw.rect(screen, self.line_color, (50, 50, self.width - 100, self.height - 100), self.line_thickness)

        # Halfway Line & Center Circle
        pygame.draw.line(screen, self.line_color, (mid_x, 50), (mid_x, self.height - 50), self.line_thickness)
        pygame.draw.circle(screen, self.line_color, (mid_x, mid_y), 70, self.line_thickness)
        pygame.draw.circle(screen, self.line_color, (mid_x, mid_y), 6) # Center kick-off dot

        # Penalty Boxes 
        # Left
        pygame.draw.rect(screen, self.line_color, (50, mid_y - 120, 150, 240), self.line_thickness)
        # Right
        pygame.draw.rect(screen, self.line_color, (self.width - 200, mid_y - 120, 150, 240), self.line_thickness)

        # Physical Goals
        goal_color = (200, 200, 200)
        pygame.draw.rect(screen, goal_color, (10, mid_y - 60, 40, 120)) # Left Goal
        pygame.draw.rect(screen, goal_color, (self.width - 50, mid_y - 60, 40, 120)) # Right Goal


if __name__ == "__main__":
    # Initialise backend
    launcher_backend = GameLauncher()
    # Initialise menu
    menu_system = MenuSystem(launcher_backend)
    
    while True:
        # Reset launch signal
        should_launch_match = False
        
        while not should_launch_match:
            menu_system.clock.tick(60)
            # Continuously monitor mouse and keyboard events
            signal = menu_system.processEvents()
            
            # Intercept launch match state
            if signal == "LAUNCH_MATCH":
                should_launch_match = True
                break
                
            # Draw active menu screen
            menu_system.renderDisplay()
            
        if should_launch_match:
            game = MatchController()
            game.runMatchLoop()
            # After runMatchLoop finishes (e.g. via EXIT_TO_MENU), it loops back to menu_system.processEvents()
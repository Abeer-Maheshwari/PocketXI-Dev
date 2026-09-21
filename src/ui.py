# src/ui.py
import math
import sys
import pygame
from src.theme import THEME, get_font

IS_WASM = sys.platform in ("emscripten", "wasi")

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False


class Button:
    # Clickable UI button with hover effects
    def __init__(self, x, y, width, height, text, font_size=24, base_color=None, hover_color=None, text_color=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.original_rect = self.rect.copy()
        self.text = text
        self.base_color = pygame.Color(*(base_color or THEME["card_bg"]))
        self.hover_color = pygame.Color(*(hover_color or THEME["primary"]))
        self.current_color = pygame.Color(self.base_color)
        self.text_color = text_color or THEME["text_primary"]
        self.font = get_font(font_size)
        self.scale = 1.0

    def draw(self, screen):
        mouse_pos = pygame.mouse.get_pos()
        is_hovered = self.original_rect.collidepoint(mouse_pos)

        target_color = self.hover_color if is_hovered else self.base_color
        target_scale = 1.03 if is_hovered else 1.0

        for i in range(3):
            self.current_color[i] = int(self.current_color[i] + (target_color[i] - self.current_color[i]) * 0.18)
        self.scale += (target_scale - self.scale) * 0.18

        scaled_width = int(self.original_rect.width * self.scale)
        scaled_height = int(self.original_rect.height * self.scale)
        self.rect = pygame.Rect(0, 0, scaled_width, scaled_height)
        self.rect.center = self.original_rect.center

        pygame.draw.rect(screen, (8, 6, 6), self.rect.move(0, 3), border_radius=8)
        pygame.draw.rect(screen, self.current_color, self.rect, border_radius=8)
        border = THEME["primary"] if is_hovered else THEME["border"]
        pygame.draw.rect(screen, border, self.rect, 2, border_radius=8)

        text_surf = self.font.render(self.text, True, self.text_color, self.current_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def is_clicked(self, mouse_pos):
        return self.original_rect.collidepoint(mouse_pos)


class Slider:
    # Horizontal slider for volume and difficulty settings
    def __init__(self, x, y, width, height, min_val, max_val, initial_val, label, font_size=14):
        self.rect = pygame.Rect(x, y, width, height)
        self.min_val = min_val
        self.max_val = max_val
        self.val = initial_val
        self.label = label
        self.active = False
        self.handle_radius = height // 2 + 5
        self.font = get_font(font_size)
        self.update_handle_pos()

    def update_handle_pos(self):
        ratio = (self.val - self.min_val) / (self.max_val - self.min_val)
        self.handle_x = self.rect.x + int(ratio * self.rect.width)

    def draw(self, screen):
        val_str = f"{int(self.val) if self.max_val > 1 else round(self.val, 2)}"
        lbl_surf = self.font.render(f"{self.label}: {val_str}", True, THEME["text_primary"], THEME["card_bg"])
        screen.blit(lbl_surf, (self.rect.x, self.rect.y - int(self.font.get_height() * 1.5)))

        pygame.draw.rect(screen, THEME["input_bg"], self.rect, border_radius=self.rect.height // 2)
        pygame.draw.rect(screen, THEME["card_border"], self.rect, 2, border_radius=self.rect.height // 2)

        fill_rect = pygame.Rect(self.rect.x, self.rect.y, self.handle_x - self.rect.x, self.rect.height)
        pygame.draw.rect(screen, THEME["primary"], fill_rect, border_radius=self.rect.height // 2)

        knob_color = THEME["text_primary"] if self.active else THEME["secondary"]
        pygame.draw.circle(screen, knob_color, (self.handle_x, self.rect.centery), self.handle_radius)
        pygame.draw.circle(screen, THEME["border"], (self.handle_x, self.rect.centery), self.handle_radius, 2)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = event.pos if hasattr(event, "pos") else pygame.mouse.get_pos()
            handle_rect = pygame.Rect(
                self.handle_x - self.handle_radius,
                self.rect.y - self.handle_radius,
                self.handle_radius * 2,
                self.rect.height + self.handle_radius * 2,
            )
            if handle_rect.collidepoint(mouse_pos) or self.rect.collidepoint(mouse_pos):
                self.active = True
                self.update_value(mouse_pos[0])
        elif event.type == pygame.MOUSEBUTTONUP:
            self.active = False
        elif event.type == pygame.MOUSEMOTION and self.active:
            mouse_pos = event.pos if hasattr(event, "pos") else pygame.mouse.get_pos()
            self.update_value(mouse_pos[0])

    def update_value(self, mouse_x):
        clamped_x = max(self.rect.x, min(mouse_x, self.rect.x + self.rect.width))
        ratio = (clamped_x - self.rect.x) / self.rect.width
        self.val = self.min_val + ratio * (self.max_val - self.min_val)
        self.handle_x = clamped_x


class MenuSystem:
    # Handles menu screens, inputs, and account login/registration

    def __init__(self, game_launcher, network_client=None):
        pygame.init()

        self.width = 1280
        self.height = 720
        self.scale = 1.0

        if IS_WASM:
            self.screen = pygame.display.set_mode((1280, 720))
        else:
            self.screen = pygame.display.set_mode((1280, 720), pygame.DOUBLEBUF, vsync=1)

        pygame.display.set_caption("Pocket XI - Main Menu")
        self.clock = pygame.time.Clock()

        def s(v):
            return int(v)
        self.s = s

        self.font_hero = get_font(s(60))
        self.font_title = get_font(s(36))
        self.font_button = get_font(s(24))
        self.font_body = get_font(s(14))
        self.font_sub = get_font(s(9))

        self.game_launcher = game_launcher
        self.network_client = network_client

        self.current_state = "LOGIN_SCREEN"
        self.username_buffer = ""
        self.password_buffer = ""
        self.active_field = "username"
        self.notification_text = ""
        self.notification_color = THEME["text_primary"]

        self.join_code_buffer = ""
        self.lobby_status = "Not connected"
        self.lobby_status_color = THEME["text_muted"]

        # Layout geometry
        margin_x = s(45)
        col_w = (self.width - (margin_x * 2) - s(25)) // 2
        self.rect_header = pygame.Rect(margin_x, s(25), self.width - (margin_x * 2), s(70))
        self.rect_mode_1 = pygame.Rect(margin_x, s(115), col_w, s(205))
        self.rect_mode_2 = pygame.Rect(margin_x, s(335), col_w, s(205))
        self.rect_stats = pygame.Rect(margin_x + col_w + s(25), s(115), col_w, s(425))

        btn_w = s(190)
        btn_h = s(52)
        self.rect_settings = pygame.Rect(self.width - margin_x - (btn_w * 2) - s(15), s(560), btn_w, btn_h)
        self.rect_logout = pygame.Rect(self.width - margin_x - btn_w, s(560), btn_w, btn_h)

        self.rect_back = pygame.Rect(self.width // 2 - s(130), s(602), s(260), s(48))

        auth_w = s(520)
        self.rect_username = pygame.Rect(self.width // 2 - auth_w // 2, s(210), auth_w, s(48))
        self.rect_password = pygame.Rect(self.width // 2 - auth_w // 2, s(275), auth_w, s(48))
        self.rect_submit = pygame.Rect(self.width // 2 - s(215), s(345), s(205), s(48))
        self.rect_auth_toggle = pygame.Rect(self.width // 2 + s(10), s(345), s(205), s(48))

        self.vol_slider = Slider(s(90), s(230), s(420), s(14), 0.0, 1.0, self.game_launcher.master_volume, "Master Volume", font_size=s(14))
        self.diff_slider = Slider(s(90), s(320), s(420), s(14), 1, 5, self.game_launcher.base_difficulty_tier, "AI Difficulty", font_size=s(14))
        self.rect_p1_toggle = pygame.Rect(s(90), s(400), s(420), s(44))
        self.rect_p2_toggle = pygame.Rect(s(90), s(455), s(420), s(44))

        self.rect_host_room = pygame.Rect(self.width // 2 - s(250), s(210), s(500), s(56))
        self.rect_join_box = pygame.Rect(self.width // 2 - s(250), s(295), s(330), s(56))
        self.rect_join_btn = pygame.Rect(self.width // 2 + s(95), s(295), s(155), s(56))

        self.temp_saved_profile = None
        self.hub_button_hover = {}
        self.auth_button_hover = {"submit": 0.0, "toggle": 0.0}

    def _draw_keybind_row(self, surface, action_label, key_text, left_x, right_x, center_y):
        # Draw keybind action and keycap pill
        lbl = self.font_body.render(action_label, True, THEME["text_muted"], THEME["card_bg"])
        surface.blit(lbl, (left_x, center_y - lbl.get_height() // 2))

        key_surf = self.font_sub.render(key_text, True, THEME["primary"], THEME["input_bg"])
        kw, kh = key_surf.get_size()
        pill = pygame.Rect(0, 0, kw + self.s(18), kh + self.s(8))
        pill.right = right_x
        pill.centery = center_y

        pygame.draw.rect(surface, THEME["input_bg"], pill, border_radius=6)
        pygame.draw.rect(surface, THEME["border"], pill, 1, border_radius=6)
        surface.blit(key_surf, key_surf.get_rect(center=pill.center))

    def _draw_toggle_button(self, rect, player_label, is_ai):
        # Toggle button for Human vs AI control
        mouse_pos = pygame.mouse.get_pos()
        hovered = rect.collidepoint(mouse_pos)
        fill_col = THEME["card_bg"]
        border_col = THEME["primary"] if hovered else THEME["card_border"]

        pygame.draw.rect(self.screen, (8, 6, 6), rect.move(0, 3), border_radius=8)
        pygame.draw.rect(self.screen, fill_col, rect, border_radius=8)
        pygame.draw.rect(self.screen, border_col, rect, 2, border_radius=8)

        lbl = self.font_body.render(player_label, True, THEME["text_primary"], fill_col)
        self.screen.blit(lbl, (rect.x + self.s(16), rect.centery - lbl.get_height() // 2))

        badge_text = "AI BOT" if is_ai else "HUMAN"
        badge_bg = THEME["primary"] if is_ai else THEME["input_bg"]
        badge_border = THEME["border_highlight"] if is_ai else THEME["border"]

        badge_surf = self.font_sub.render(badge_text, True, THEME["text_primary"], badge_bg)
        bw, bh = badge_surf.get_size()
        pill = pygame.Rect(0, 0, bw + self.s(20), rect.height - self.s(12))
        pill.right = rect.right - self.s(12)
        pill.centery = rect.centery

        pygame.draw.rect(self.screen, badge_bg, pill, border_radius=6)
        pygame.draw.rect(self.screen, badge_border, pill, 1, border_radius=6)
        self.screen.blit(badge_surf, badge_surf.get_rect(center=pill.center))

    def drawLoginScreen(self):
        # Login / registration screen
        title_text = "LOGIN" if self.current_state == "LOGIN_SCREEN" else "REGISTRATION"
        panel = pygame.Rect(self.width // 2 - self.s(310), self.s(125), self.s(620), self.s(370))

        pygame.draw.rect(self.screen, (8, 6, 6), panel.move(0, 6), border_radius=14)
        pygame.draw.rect(self.screen, THEME["card_bg"], panel, border_radius=14)
        pygame.draw.rect(self.screen, THEME["border"], panel, 2, border_radius=14)

        title_surf = self.font_title.render(title_text, True, THEME["text_primary"], THEME["card_bg"])
        self.screen.blit(title_surf, title_surf.get_rect(center=(self.width // 2, self.s(165))))

        self._draw_auth_field(self.rect_username, "username")
        self._draw_auth_field(self.rect_password, "password")

        u_txt = self.font_body.render(
            f"Username: {self.username_buffer} {'|' if self.active_field == 'username' else ''}",
            True, THEME["text_primary"], THEME["card_bg"] if self.active_field == "username" else THEME["input_bg"]
        )
        p_txt = self.font_body.render(
            f"Password: {'*' * len(self.password_buffer)} {'|' if self.active_field == 'password' else ''}",
            True, THEME["text_primary"], THEME["card_bg"] if self.active_field == "password" else THEME["input_bg"]
        )

        self.screen.blit(u_txt, (self.rect_username.x + self.s(16), self.rect_username.centery - u_txt.get_height() // 2))
        self.screen.blit(p_txt, (self.rect_password.x + self.s(16), self.rect_password.centery - p_txt.get_height() // 2))

        toggle_text = "CREATE ACCOUNT" if self.current_state == "LOGIN_SCREEN" else "BACK TO LOGIN"
        self._draw_auth_button(self.rect_submit, "SUBMIT", is_primary=True, key="submit")
        self._draw_auth_button(self.rect_auth_toggle, toggle_text, is_primary=False, key="toggle")

        hint = self.font_sub.render("PRESS [TAB] TO SWITCH FIELDS  |  PRESS [ENTER] TO SUBMIT", True, THEME["text_muted"], THEME["card_bg"])
        self.screen.blit(hint, hint.get_rect(center=(self.width // 2, self.s(455))))

    def _draw_auth_field(self, rect, field_name):
        # Draw input field with active border highlight
        active = self.active_field == field_name
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        fill = THEME["card_bg"] if active else THEME["input_bg"]
        border = THEME["primary"] if active else (THEME["border"] if hovered else THEME["card_border"])

        pygame.draw.rect(self.screen, (8, 6, 6), rect.move(0, 3), border_radius=8)
        pygame.draw.rect(self.screen, fill, rect, border_radius=8)
        pygame.draw.rect(self.screen, border, rect, 2, border_radius=8)

    def _draw_auth_button(self, rect, label, is_primary, key):
        # Draw submit/toggle button with hover animation
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        progress = self.auth_button_hover[key]
        progress += ((1.0 if hovered else 0.0) - progress) * 0.2
        self.auth_button_hover[key] = progress

        scale = 1.0 + progress * 0.03
        draw_rect = pygame.Rect(0, 0, int(rect.width * scale), int(rect.height * scale))
        draw_rect.center = rect.center

        base_col = pygame.Color(*THEME["primary"]) if is_primary else pygame.Color(*THEME["card_bg"])
        border_col = THEME["text_primary"] if (hovered and is_primary) else (THEME["primary"] if hovered else THEME["border"])

        pygame.draw.rect(self.screen, (8, 6, 6), draw_rect.move(0, int(5 - progress * 2)), border_radius=8)
        pygame.draw.rect(self.screen, base_col, draw_rect, border_radius=8)
        pygame.draw.rect(self.screen, border_col, draw_rect, 2, border_radius=8)

        text = self.font_body.render(label, True, THEME["text_primary"], base_col)
        self.screen.blit(text, text.get_rect(center=draw_rect.center))

    def drawMainHub(self):
        # Main menu hub
        user_name = (self.game_launcher.active_user_session or "PLAYER").upper()
        user_surf = self.font_body.render(user_name, True, THEME["text_muted"], THEME["bg_dark"])
        self.screen.blit(user_surf, user_surf.get_rect(topright=(self.width - self.s(45), self.s(25))))

        title_surf = self.font_title.render("POCKET XI", True, THEME["text_primary"], THEME["bg_dark"])
        self.screen.blit(title_surf, title_surf.get_rect(center=(self.width // 2, self.s(60))))

        pygame.draw.line(self.screen, THEME["border"], (self.width // 2 - self.s(80), self.s(85)), (self.width // 2 + self.s(80), self.s(85)), 2)

        buttons = [
            (self.rect_mode_1, "QUICK MATCH"),
            (self.rect_mode_2, "PLAY WITH A FRIEND"),
            (self.rect_stats, "CAREER STATS"),
            (self.rect_settings, "SETTINGS"),
            (self.rect_logout, "LOG OUT"),
        ]
        for rect, label in buttons:
            self._draw_hub_button(rect, label)

    def _draw_hub_button(self, rect, label):
        # Draw interactive menu tile
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        progress = self.hub_button_hover.get(label, 0.0)
        progress += ((1.0 if hovered else 0.0) - progress) * 0.22
        self.hub_button_hover[label] = progress

        scale = 1.0 + progress * 0.025
        draw_rect = pygame.Rect(0, 0, int(rect.width * scale), int(rect.height * scale))
        draw_rect.center = rect.center

        fill_colour = pygame.Color(*THEME["card_bg"]).lerp(pygame.Color(*THEME["primary"]), progress * 0.25)
        border_colour = THEME["primary"] if hovered else THEME["border"]

        pygame.draw.rect(self.screen, (8, 6, 6), draw_rect.move(0, int(5 - progress * 2)), border_radius=10)
        pygame.draw.rect(self.screen, fill_colour, draw_rect, border_radius=10)
        pygame.draw.rect(self.screen, border_colour, draw_rect, 2, border_radius=10)

        label_surface = self.font_button.render(label, True, THEME["text_primary"], fill_colour)
        self.screen.blit(label_surface, label_surface.get_rect(center=draw_rect.center))

    def drawOnlineLobby(self):
        # Multiplayer lobby screen
        self.screen.fill(THEME["bg_dark"])
        title_surf = self.font_title.render("LOBBY", True, THEME["text_primary"], THEME["bg_dark"])
        self.screen.blit(title_surf, title_surf.get_rect(center=(self.width // 2, self.s(85))))

        status_surf = self.font_body.render(self.lobby_status.upper(), True, self.lobby_status_color, THEME["bg_dark"])
        self.screen.blit(status_surf, status_surf.get_rect(center=(self.width // 2, self.s(140))))

        hover_host = self.rect_host_room.collidepoint(pygame.mouse.get_pos())
        host_bg = pygame.Color(*THEME["card_bg"]).lerp(pygame.Color(*THEME["primary"]), 0.25 if hover_host else 0.0)
        pygame.draw.rect(self.screen, host_bg, self.rect_host_room, border_radius=10)
        pygame.draw.rect(self.screen, THEME["primary"] if hover_host else THEME["border"], self.rect_host_room, 2, border_radius=10)

        if self.network_client and self.network_client.room_code and self.network_client.player_role == "p1":
            host_text = f"ROOM CODE: {self.network_client.room_code} (WAITING...)"
        else:
            host_text = "CREATE ROOM"
        h_surf = self.font_button.render(host_text, True, THEME["text_primary"], host_bg)
        self.screen.blit(h_surf, h_surf.get_rect(center=self.rect_host_room.center))

        pygame.draw.rect(self.screen, THEME["input_bg"], self.rect_join_box, border_radius=10)
        pygame.draw.rect(self.screen, THEME["border"], self.rect_join_box, 2, border_radius=10)
        join_display = f"CODE: {self.join_code_buffer}|" if self.join_code_buffer else "ENTER 4-LETTER CODE"
        j_surf = self.font_body.render(join_display, True, THEME["text_primary"] if self.join_code_buffer else THEME["text_muted"], THEME["input_bg"])
        self.screen.blit(j_surf, (self.rect_join_box.x + self.s(20), self.rect_join_box.centery - j_surf.get_height() // 2))

        hover_join = self.rect_join_btn.collidepoint(pygame.mouse.get_pos())
        join_bg = THEME["primary"] if hover_join else pygame.Color(*THEME["card_bg"]).lerp(pygame.Color(*THEME["primary"]), 0.4)
        pygame.draw.rect(self.screen, join_bg, self.rect_join_btn, border_radius=10)
        pygame.draw.rect(self.screen, THEME["border"], self.rect_join_btn, 2, border_radius=10)
        j_btn_surf = self.font_body.render("JOIN", True, THEME["text_primary"], join_bg)
        self.screen.blit(j_btn_surf, j_btn_surf.get_rect(center=self.rect_join_btn.center))

        self._draw_back_button()

    def drawSettingsMenu(self):
        # Settings menu (sliders, controls, keybinds)
        self.screen.fill(THEME["bg_dark"])

        title_surf = self.font_title.render("SETTINGS", True, THEME["text_primary"], THEME["bg_dark"])
        self.screen.blit(title_surf, title_surf.get_rect(center=(self.width // 2, self.s(55))))

        card_w = self.s(560)
        card_h = self.s(475)
        top_y = self.s(100)

        # Left panel: sliders and toggles
        left_card = pygame.Rect(self.s(50), top_y, card_w, card_h)
        pygame.draw.rect(self.screen, (8, 6, 6), left_card.move(0, 6), border_radius=12)
        pygame.draw.rect(self.screen, THEME["card_bg"], left_card, border_radius=12)
        pygame.draw.rect(self.screen, THEME["border"], left_card, 2, border_radius=12)

        sec1_title = self.font_button.render("AUDIO & DIFFICULTY", True, THEME["text_primary"], THEME["card_bg"])
        self.screen.blit(sec1_title, (left_card.x + self.s(30), left_card.y + self.s(25)))

        self.vol_slider.draw(self.screen)
        self.diff_slider.draw(self.screen)

        self._draw_toggle_button(self.rect_p1_toggle, "Player 1 Control", self.game_launcher.p1_is_ai)
        self._draw_toggle_button(self.rect_p2_toggle, "Player 2 Control", self.game_launcher.p2_is_ai)

        self.game_launcher.base_difficulty_tier = int(self.diff_slider.val)
        self.game_launcher.master_volume = round(self.vol_slider.val, 2)

        # Right panel: keybind reference list
        right_card = pygame.Rect(self.s(670), top_y, card_w, card_h)
        pygame.draw.rect(self.screen, (8, 6, 6), right_card.move(0, 6), border_radius=12)
        pygame.draw.rect(self.screen, THEME["card_bg"], right_card, border_radius=12)
        pygame.draw.rect(self.screen, THEME["border"], right_card, 2, border_radius=12)

        sec2_title = self.font_button.render("CONTROLS", True, THEME["text_primary"], THEME["card_bg"])
        self.screen.blit(sec2_title, (right_card.x + self.s(30), right_card.y + self.s(25)))

        match_cat = self.font_sub.render("GAMEPLAY", True, THEME["primary"], THEME["card_bg"])
        self.screen.blit(match_cat, (right_card.x + self.s(30), right_card.y + self.s(70)))

        all_binds = [
            ("Movement", "WASD (P1) / ARROWS (P2)", self.s(105)),
            ("Sprint / Boost", "L-SHIFT (P1) / R-SHIFT (P2)", self.s(145)),
            ("Shoot / Clearance", "SPACE (P1) / ENTER (P2)", self.s(185)),
            ("Pause Match", "ESC / P", self.s(225)),
        ]
        for label, key_text, row_y in all_binds:
            self._draw_keybind_row(self.screen, label, key_text, right_card.x + self.s(30), right_card.right - self.s(30), right_card.y + row_y)

        menu_cat = self.font_sub.render("MENUS", True, THEME["primary"], THEME["card_bg"])
        self.screen.blit(menu_cat, (right_card.x + self.s(30), right_card.y + self.s(275)))

        menu_binds = [
            ("Switch Input Boxes", "TAB", self.s(310)),
            ("Submit / Select", "ENTER", self.s(350)),
            ("Back / Cancel", "ESC", self.s(390)),
        ]
        for label, key_text, row_y in menu_binds:
            self._draw_keybind_row(self.screen, label, key_text, right_card.x + self.s(30), right_card.right - self.s(30), right_card.y + row_y)

        self._draw_back_button()

    def drawStatsDashboard(self):
        # Career stats screen
        self.screen.fill(THEME["bg_dark"])

        title_surf = self.font_title.render("STATS", True, THEME["text_primary"], THEME["bg_dark"])
        self.screen.blit(title_surf, title_surf.get_rect(center=(self.width // 2, self.s(65))))

        card_w = self.s(680)
        card_h = self.s(360)
        card = pygame.Rect(self.width // 2 - card_w // 2, self.s(125), card_w, card_h)

        pygame.draw.rect(self.screen, (8, 6, 6), card.move(0, 6), border_radius=12)
        pygame.draw.rect(self.screen, THEME["card_bg"], card, border_radius=12)
        pygame.draw.rect(self.screen, THEME["border"], card, 2, border_radius=12)

        profile = self.temp_saved_profile if isinstance(self.temp_saved_profile, dict) else {}
        goals = profile.get("goals", 0)
        shots = profile.get("shots", 0)
        poss_time = profile.get("possession_time", 0.0)

        total_sec = int(poss_time)
        mins = total_sec // 60
        secs = total_sec % 60
        poss_str = f"{mins}m {secs:02d}s" if mins > 0 else f"{secs}s"
        accuracy_str = f"{round((goals / shots * 100), 1)}%" if shots > 0 else "0.0%"

        stat_rows = [
            ("GOALS", str(goals)),
            ("SHOTS", str(shots)),
            ("ACCURACY", accuracy_str),
            ("POSSESSION TIME", poss_str),
        ]

        start_y = card.top + self.s(78)
        row_gap = self.s(68)

        for i, (label, val) in enumerate(stat_rows):
            cy = start_y + (i * row_gap)

            if i > 0:
                pygame.draw.line(
                    self.screen,
                    THEME["card_border"],
                    (card.left + self.s(35), cy - self.s(34)),
                    (card.right - self.s(35), cy - self.s(34)),
                    1
                )

            lbl_surf = self.font_body.render(label, True, THEME["text_muted"], THEME["card_bg"])
            self.screen.blit(lbl_surf, (card.left + self.s(40), cy - lbl_surf.get_height() // 2))

            val_surf = self.font_button.render(val, True, THEME["text_primary"], THEME["card_bg"])
            self.screen.blit(val_surf, (card.right - self.s(40) - val_surf.get_width(), cy - val_surf.get_height() // 2))

        self._draw_back_button()

    def _draw_back_button(self):
        # Back to menu button
        mouse_pos = pygame.mouse.get_pos()
        hovered = self.rect_back.collidepoint(mouse_pos)
        progress = self.hub_button_hover.get("back", 0.0)
        progress += ((1.0 if hovered else 0.0) - progress) * 0.22
        self.hub_button_hover["back"] = progress

        scale = 1.0 + progress * 0.03
        draw_rect = pygame.Rect(0, 0, int(self.rect_back.width * scale), int(self.rect_back.height * scale))
        draw_rect.center = self.rect_back.center

        bg_col = pygame.Color(*THEME["card_bg"]).lerp(pygame.Color(*THEME["primary"]), progress * 0.4)
        border = THEME["primary"] if hovered else THEME["border"]

        pygame.draw.rect(self.screen, (8, 6, 6), draw_rect.move(0, 4), border_radius=8)
        pygame.draw.rect(self.screen, bg_col, draw_rect, border_radius=8)
        pygame.draw.rect(self.screen, border, draw_rect, 2, border_radius=8)

        label = self.font_body.render("RETURN TO MENU", True, THEME["text_primary"], bg_col)

        arrow_len = self.s(14)
        head_size = self.s(5)
        spacing = self.s(10)
        total_content_w = arrow_len + spacing + label.get_width()

        start_x = draw_rect.centerx - (total_content_w // 2)
        cy = draw_rect.centery
        line_w = max(2, self.s(2))

        pygame.draw.line(self.screen, THEME["text_primary"], (start_x, cy), (start_x + arrow_len, cy), line_w)
        head_pts = [
            (start_x + head_size, cy - head_size),
            (start_x, cy),
            (start_x + head_size, cy + head_size),
        ]
        pygame.draw.lines(self.screen, THEME["text_primary"], False, head_pts, line_w)

        text_x = start_x + arrow_len + spacing
        text_y = cy - (label.get_height() // 2)
        self.screen.blit(label, (text_x, text_y))

    async def executeSubmitAction(self):
        # Submit login or registration to server
        if not self.username_buffer.strip() or not self.password_buffer.strip():
            self.notification_text = "Please enter username and password."
            self.notification_color = THEME["danger"]
            return

        if self.current_state == "LOGIN_SCREEN":
            self.notification_text = "Authenticating..."
            self.notification_color = THEME["secondary"]
            self.renderDisplay()

            if self.network_client:
                resp = await self.network_client.auth_login(self.username_buffer, self.password_buffer)
                if resp.get("status") == "login_success":
                    self.temp_saved_profile = resp.get("profile", {"goals": 0, "shots": 0, "possession_time": 0.0})
                    if self.game_launcher:
                        self.game_launcher.active_user_session = self.username_buffer.strip().replace(" ", "")
                        self.game_launcher.temp_saved_profile = self.temp_saved_profile.copy()
                    self.notification_text = f"Welcome back, {self.username_buffer}!"
                    self.notification_color = THEME["notification"]
                    self.current_state = "MAIN_HUB"
                else:
                    self.notification_text = resp.get("message", "Login failed.")
                    self.notification_color = THEME["danger"]
            else:
                res = self.game_launcher.login(self.username_buffer, self.password_buffer)
                if res is True:
                    self.temp_saved_profile = self.game_launcher.temp_saved_profile
                    self.notification_text = "Login Successful."
                    self.notification_color = THEME["notification"]
                    self.current_state = "MAIN_HUB"
                else:
                    self.notification_text = self.game_launcher.status_message
                    self.notification_color = THEME["danger"]
        else:
            self.notification_text = "Creating account..."
            self.notification_color = THEME["secondary"]
            self.renderDisplay()

            if self.network_client:
                resp = await self.network_client.auth_register(self.username_buffer, self.password_buffer)
                if resp.get("status") == "register_success":
                    self.notification_text = "Account created! Please log in."
                    self.notification_color = THEME["notification"]
                    self.current_state = "LOGIN_SCREEN"
                    self.password_buffer = ""
                else:
                    self.notification_text = resp.get("message", "Registration failed.")
                    self.notification_color = THEME["danger"]
            else:
                status = self.game_launcher.register(self.username_buffer, self.password_buffer)
                if status is True:
                    self.notification_text = "Registration successful. Please log in."
                    self.notification_color = THEME["notification"]
                    self.current_state = "LOGIN_SCREEN"
                    self.password_buffer = ""
                else:
                    self.notification_text = self.game_launcher.status_message
                    self.notification_color = THEME["danger"]

    def executeLogoutAction(self):
        # Log out and clear current user session
        self.game_launcher.active_user_session = None
        self.temp_saved_profile = None
        self.username_buffer = ""
        self.password_buffer = ""
        self.notification_text = "Session signed out."
        self.notification_color = THEME["text_muted"]
        self.current_state = "LOGIN_SCREEN"

    async def processEvents(self):
        # Handle input events and menu navigation
        if self.network_client and self.current_state == "ONLINE_LOBBY":
            self.network_client.pop_messages()

            if self.network_client.room_code and self.network_client.player_role == "p1":
                self.lobby_status = f"ROOM CREATED: {self.network_client.room_code} (WAITING FOR OPPONENT)"
                self.lobby_status_color = THEME["notification"]
            elif self.network_client.room_code and self.network_client.player_role == "p2":
                self.lobby_status = f"JOINED ROOM: {self.network_client.room_code} (WAITING FOR HOST)"
                self.lobby_status_color = THEME["notification"]

            if self.network_client.match_started:
                return "LAUNCH_ONLINE_MATCH"
            if self.network_client.error_message:
                self.lobby_status = self.network_client.error_message
                self.lobby_status_color = THEME["danger"]

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if self.current_state == "SETTINGS_MENU":
                was_active = self.vol_slider.active or self.diff_slider.active

                self.vol_slider.handle_event(event)
                self.diff_slider.handle_event(event)

                if pygame.mixer.get_init():
                    pygame.mixer.music.set_volume(self.vol_slider.val)

                if event.type == pygame.MOUSEBUTTONUP and was_active:
                    self.game_launcher.save_settings()

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_pos = event.pos if hasattr(event, "pos") else pygame.mouse.get_pos()
                    if self.rect_p1_toggle.collidepoint(mouse_pos):
                        self.game_launcher.p1_is_ai = not self.game_launcher.p1_is_ai
                        self.game_launcher.save_settings()
                    elif self.rect_p2_toggle.collidepoint(mouse_pos):
                        self.game_launcher.p2_is_ai = not self.game_launcher.p2_is_ai
                        self.game_launcher.save_settings()

            mouse_pos = event.pos if hasattr(event, "pos") else pygame.mouse.get_pos()

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.current_state in ["LOGIN_SCREEN", "REGISTER_SCREEN"]:
                    if self.rect_username.collidepoint(mouse_pos):
                        self.active_field = "username"
                    elif self.rect_password.collidepoint(mouse_pos):
                        self.active_field = "password"
                    elif self.rect_submit.collidepoint(mouse_pos):
                        await self.executeSubmitAction()
                    elif self.rect_auth_toggle.collidepoint(mouse_pos):
                        self.current_state = "REGISTER_SCREEN" if self.current_state == "LOGIN_SCREEN" else "LOGIN_SCREEN"
                        self.notification_text = ""

                elif self.current_state == "MAIN_HUB":
                    if self.rect_mode_1.collidepoint(mouse_pos):
                        return "LAUNCH_MATCH"
                    elif self.rect_mode_2.collidepoint(mouse_pos):
                        self.current_state = "ONLINE_LOBBY"
                        self.lobby_status = "Connecting to relay..."
                        self.lobby_status_color = THEME["secondary"]
                        if self.network_client:
                            connected = await self.network_client.connect()
                            if connected:
                                self.lobby_status = "Connected. Ready to play."
                                self.lobby_status_color = THEME["notification"]
                            else:
                                self.lobby_status = self.network_client.error_message or "Connection failed"
                                self.lobby_status_color = THEME["danger"]
                    elif self.rect_stats.collidepoint(mouse_pos):
                        self.current_state = "STATS_DASHBOARD"
                    elif self.rect_settings.collidepoint(mouse_pos):
                        self.current_state = "SETTINGS_MENU"
                    elif self.rect_logout.collidepoint(mouse_pos):
                        self.executeLogoutAction()

                elif self.current_state == "ONLINE_LOBBY":
                    if self.rect_host_room.collidepoint(mouse_pos) and self.network_client:
                        self.lobby_status = "Generating Room..."
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

            if event.type == pygame.KEYDOWN:
                if self.current_state in ["LOGIN_SCREEN", "REGISTER_SCREEN"]:
                    if event.key == pygame.K_TAB:
                        self.active_field = "password" if self.active_field == "username" else "username"
                    elif event.key == pygame.K_ESCAPE:
                        self.current_state = "REGISTER_SCREEN" if self.current_state == "LOGIN_SCREEN" else "LOGIN_SCREEN"
                        self.notification_text = ""
                    elif event.key == pygame.K_RETURN:
                        await self.executeSubmitAction()
                    elif event.key == pygame.K_BACKSPACE:
                        if self.active_field == "username":
                            self.username_buffer = self.username_buffer[:-1]
                        else:
                            self.password_buffer = self.password_buffer[:-1]
                    else:
                        if event.unicode.isalnum() or event.unicode in ["@", ".", "_"]:
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

                elif self.current_state in ["SETTINGS_MENU", "STATS_DASHBOARD"]:
                    if event.key in [pygame.K_BACKSPACE, pygame.K_ESCAPE]:
                        self.current_state = "MAIN_HUB"

        return "KEEP_RUNNING"

    def renderDisplay(self, execute_flip=True):
        # Render current menu state
        self.screen.fill(THEME["bg_dark"])

        if self.notification_text:
            msg = self.font_body.render(self.notification_text.upper(), True, self.notification_color, THEME["bg_dark"])
            self.screen.blit(msg, (self.s(50), self.s(20)))

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

        if execute_flip:
            pygame.display.flip()
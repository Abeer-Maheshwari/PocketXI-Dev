# src/match.py
import asyncio
import base64
import hashlib
import json
import sys
import pygame
from src.ai import AIManager
from src.animation import AnimationManager
from src.encryption import EncryptionEngine
from src.entities import Ball, ParticleSystem, Player
from src.physics import PhysicsEngine
from src.renderer import PitchRenderer
from src.sound import SoundManager
from src.stats import StatsTracker
from src.team import TeamLoader
from src.theme import THEME, get_font, get_hud_font
from src.transition import TransitionManager

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False


class MatchController:
    """Manages active match gameplay loop, physics, scoring, HUD, and pause menu."""

    def __init__(self, launcher_backend=None, menu_system=None, network_client=None, is_online=False):
        surface = pygame.display.get_surface()
        if surface:
            self.screen_width, self.screen_height = surface.get_size()
        elif HAS_PYAUTOGUI:
            try:
                screen_w, screen_h = pyautogui.size()
                target_h = int(screen_h * 0.82)
                self.screen_height = max(720, min(target_h, 1080))
                self.screen_width = int(self.screen_height * (16 / 9))
            except Exception:
                self.screen_width = 1280
                self.screen_height = 720
        else:
            self.screen_width = 1280
            self.screen_height = 720

        # Scaling factor based on 720p base height
        self.scale = self.screen_height / 720.0

        def s(v):
            return int(v * self.scale)
        self.s = s

        self.screen = surface
        self.fps = 60
        self.clock = None
        self.dt = 0.0

        self.launcher_backend = launcher_backend
        self.menu_system = menu_system
        self.network_client = network_client
        self.is_online = is_online

        # Match clock: 300 real seconds maps to a 90:00 simulated match
        self.MATCH_DURATION = 300.0
        self.match_time_elapsed = 0.0

        self.p1_score = 0
        self.p2_score = 0
        self.MAX_GOALS = 10
        self.is_game_over = False
        self.is_paused = False

        # Fonts
        self.font_hero = get_font(s(60))
        self.font_title = get_font(s(36))
        self.font_button = get_font(s(24))
        self.font_body = get_font(s(14))
        self.font_sub = get_font(s(9))

        self.font_hud_score = get_hud_font(s(26))
        self.font_hud_clock = get_hud_font(s(24))
        self.font_hud_title = get_hud_font(s(38))
        self.font_hud_stat = get_hud_font(s(24))

        # Pause menu buttons
        cx = self.screen_width // 2
        cy = self.screen_height // 2
        self.rect_resume = pygame.Rect(cx - s(365), cy - s(20), s(290), s(50))
        self.rect_exit_match = pygame.Rect(cx - s(365), cy + s(55), s(290), s(50))
        self.pause_button_hover = {"resume": 0.0, "exit": 0.0}

        # Game state references
        self.player1 = None
        self.player2 = None
        self.ball = None
        self.physics_engine = None
        self.pitch_renderer = None
        self.sound_manager = None
        self.particle_system = None
        self.stats_tracker = None
        self.ai_manager = None
        self.asset_manager = None
        self.team_loader = None
        self.saved_profile = {}
        self.transition = None

    def initialiseGame(self):
        """Initializes game window, physics boundaries, audio, players, and ball."""
        if not pygame.get_init():
            pygame.init()

        if not self.screen:
            self.screen = pygame.display.set_mode((self.screen_width, self.screen_height), pygame.DOUBLEBUF, vsync=1)
        else:
            self.screen_width, self.screen_height = self.screen.get_size()
            self.scale = self.screen_height / 720.0

        pygame.display.set_caption("Pocket XI")
        self.clock = pygame.time.Clock()
        self.transition = TransitionManager(self.screen)

        cx = self.screen_width // 2
        cy = self.screen_height // 2
        self.rect_resume = pygame.Rect(cx - self.s(365), cy - self.s(20), self.s(290), self.s(50))
        self.rect_exit_match = pygame.Rect(cx - self.s(365), cy + self.s(55), self.s(290), self.s(50))

        self.team_loader = TeamLoader()
        p1_stats = self.team_loader.get_team_stats("red_team")
        p2_stats = self.team_loader.get_team_stats("blue_team")

        pitch_rect = pygame.Rect(self.s(50), self.s(50), self.screen_width - self.s(100), self.screen_height - self.s(100))
        self.ai_manager = AIManager(pitch_rect)

        self.asset_manager = AnimationManager("assets")
        volume = self.launcher_backend.master_volume if self.launcher_backend else 1.0
        self.sound_manager = SoundManager("assets/audio", master_volume=volume)
        self.stats_tracker = StatsTracker()

        self.saved_profile = {}
        if self.launcher_backend and self.menu_system:
            profile = self.menu_system.temp_saved_profile
            if isinstance(profile, dict):
                self.saved_profile = profile.copy()

        self.pitch_renderer = PitchRenderer(self.screen_width, self.screen_height)
        self.particle_system = ParticleSystem()
        self.physics_engine = PhysicsEngine(
            pitch_rect,
            self.sound_manager,
            self.stats_tracker,
            self.ai_manager,
            self.particle_system,
        )
        self.sound_manager.play_sfx("whistle")

        p1_spawn_x = int(self.screen_width * 0.3125)
        p2_spawn_x = int(self.screen_width * 0.6875)
        spawn_y = self.screen_height // 2

        self.player1 = Player(
            self.sound_manager,
            player_id="p1",
            start_pos=(p1_spawn_x, spawn_y),
            controls="WASD",
            stats=p1_stats,
        )
        self.player2 = Player(
            self.sound_manager,
            player_id="p2",
            start_pos=(p2_spawn_x, spawn_y),
            controls="ARROWS",
            stats=p2_stats,
        )
        self.ball = Ball(start_pos=(self.screen_width // 2, self.screen_height // 2))

        self.p1_goal_pos = pygame.Vector2(self.s(10), self.screen_height // 2)
        self.p2_goal_pos = pygame.Vector2(self.screen_width - self.s(50), self.screen_height // 2)

    def handleMainEvents(self):
        """Handles keyboard and mouse clicks during matches and in pause/end screens."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.terminateGame()

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.is_paused and not self.is_game_over:
                    if self.rect_resume.collidepoint(event.pos):
                        self._set_pause_state(False)
                    elif self.rect_exit_match.collidepoint(event.pos):
                        return "EXIT_TO_MENU"

            if event.type == pygame.KEYDOWN:
                if self.is_game_over:
                    if event.key == pygame.K_r:
                        return "RESTART_MATCH"
                    elif event.key == pygame.K_ESCAPE:
                        return "EXIT_TO_MENU"
                else:
                    if event.key == pygame.K_ESCAPE or event.key == pygame.K_p:
                        self._set_pause_state(not self.is_paused)

        return "KEEP_RUNNING"

    def _set_pause_state(self, paused):
        """Sets pause state and toggles match audio playback."""
        if paused == self.is_paused:
            return
        self.is_paused = paused
        if self.sound_manager:
            self.sound_manager.set_paused(paused)

    def _hardResetMatch(self):
        """Resets scores, timer, entities, and whistles for kickoff."""
        self.p1_score = 0
        self.p2_score = 0
        self.match_time_elapsed = 0.0
        self.is_game_over = False
        self._set_pause_state(False)
        self._resetPositions()
        if self.sound_manager:
            self.sound_manager.play_sfx("whistle")

    def updateTimer(self):
        """Advances the match clock until the duration limit is reached."""
        if self.match_time_elapsed < self.MATCH_DURATION:
            self.match_time_elapsed += self.dt
            if self.match_time_elapsed > self.MATCH_DURATION:
                self.match_time_elapsed = self.MATCH_DURATION

    def heuristicAdapt(self, ai_score, user_score, match_time):
        """Adjusts AI movement speed and reaction latency based on score difference."""
        G = ai_score - user_score
        speed_modifier = 1.0
        reaction_delay = 0.0

        if G < -2:
            speed_modifier = 1.35
            reaction_delay = 0.0
        elif G > 3:
            speed_modifier = 0.80
            reaction_delay = 0.5

        if self.launcher_backend:
            tier = max(1, min(int(self.launcher_backend.base_difficulty_tier), 5))
            speed_modifier *= 0.8 + (tier - 1) * 0.1
            reaction_delay += (5 - tier) * 0.075

        return {
            "max_velocity_mult": speed_modifier,
            "reaction_delay": reaction_delay,
        }

    async def updateMatchState(self):
        """Updates physics, inputs, AI state machines, and goal detection each frame."""
        if self.is_game_over or self.is_paused:
            return

        self.updateTimer()
        self.particle_system.update(self.dt)
        self.sound_manager.update_ambient_chants()

        # Online network sync
        if self.is_online and self.network_client:
            is_host = self.network_client.player_role == "p1"

            for msg in self.network_client.pop_messages():
                if msg.get("status") == "relay":
                    payload = msg.get("payload", {})
                    p_type = payload.get("type")

                    if is_host and p_type == "GUEST_INPUT":
                        self.player2.vel = pygame.Vector2(payload["vel"][0], payload["vel"][1])
                        self.player2.is_sprinting = payload.get("sprint", False)
                        self.player2.is_charging = payload.get("charge", False)
                    elif not is_host and p_type == "HOST_STATE":
                        self.ball.pos = pygame.Vector2(payload["ball_pos"][0], payload["ball_pos"][1])
                        self.ball.vel = pygame.Vector2(payload["ball_vel"][0], payload["ball_vel"][1])
                        self.player1.pos = pygame.Vector2(payload["p1_pos"][0], payload["p1_pos"][1])
                        self.player1.vel = pygame.Vector2(payload["p1_vel"][0], payload["p1_vel"][1])
                        self.p1_score = payload["scores"][0]
                        self.p2_score = payload["scores"][1]
                        self.match_time_elapsed = payload["time"]

            if is_host:
                self.player1.handleInput()
                self.player1.updatePosition(self.dt)
                self.player2.updatePosition(self.dt)

                if self.ball.vel.length() > 0:
                    self.ball.vel = self.physics_engine.calculateCurve(
                        self.ball.vel, self.ball.active_spin, self.ball.target_offset
                    )
                self.ball.applyPhysics(self.dt)

                await self.network_client.send_relay({
                    "type": "HOST_STATE",
                    "ball_pos": [self.ball.pos.x, self.ball.pos.y],
                    "ball_vel": [self.ball.vel.x, self.ball.vel.y],
                    "p1_pos": [self.player1.pos.x, self.player1.pos.y],
                    "p1_vel": [self.player1.vel.x, self.player1.vel.y],
                    "scores": [self.p1_score, self.p2_score],
                    "time": self.match_time_elapsed,
                })
            else:
                self.player2.handleInput()
                self.player2.updatePosition(self.dt)
                self.player1.updatePosition(self.dt)

                await self.network_client.send_relay({
                    "type": "GUEST_INPUT",
                    "vel": [self.player2.vel.x, self.player2.vel.y],
                    "sprint": self.player2.is_sprinting,
                    "charge": self.player2.is_charging,
                })

        # Local match logic with AI toggle support
        else:
            p1_is_ai = getattr(self.launcher_backend, "p1_is_ai", False) if self.launcher_backend else False
            p2_is_ai = getattr(self.launcher_backend, "p2_is_ai", True) if self.launcher_backend else True

            # Player 1: Route to AI or keyboard input
            if p1_is_ai:
                self.player1.is_afk = True
                p1_mod = self.heuristicAdapt(self.p1_score, self.p2_score, self.match_time_elapsed)
                self.ai_manager.updateFSM(
                    self.player1, self.player2, self.ball, self.p1_goal_pos, self.p2_goal_pos, p1_mod
                )
            else:
                self.player1.is_afk = False
                self.player1.handleInput()
            self.player1.updatePosition(self.dt)

            # Player 2: Route to AI or keyboard input
            if p2_is_ai:
                self.player2.is_afk = True
                p2_mod = self.heuristicAdapt(self.p2_score, self.p1_score, self.match_time_elapsed)
                self.ai_manager.updateFSM(
                    self.player2, self.player1, self.ball, self.p2_goal_pos, self.p1_goal_pos, p2_mod
                )
            else:
                self.player2.is_afk = False
                self.player2.handleInput()
            self.player2.updatePosition(self.dt)

            # Ball spin and velocity
            if self.ball.vel.length() > 0:
                self.ball.vel = self.physics_engine.calculateCurve(
                    self.ball.vel, self.ball.active_spin, self.ball.target_offset
                )
            self.ball.applyPhysics(self.dt)

            # Possession tracking
            if self.ball.last_touched_by:
                active_player = self.player1 if self.ball.last_touched_by == "p1" else self.player2
                if (active_player.pos - self.ball.pos).length() <= self.s(80):
                    self.stats_tracker.log_possession(active_player.player_id, self.dt)

            # Boundary and entity collisions
            self.physics_engine.resolveBoundaryCollision(self.player1)
            self.physics_engine.resolveBoundaryCollision(self.player2)
            self.physics_engine.resolveBoundaryCollision(self.ball)

            self.physics_engine.checkPvPCollision(self.player1, self.player2)
            self.physics_engine.checkPvBCollision(self.player1, self.ball)
            self.physics_engine.checkPvBCollision(self.player2, self.ball)

            if not self.is_online or (self.network_client and self.network_client.player_role == "p1"):
                self._checkGoalConditions()

    def _checkGoalConditions(self):
        """Detects ball crossing goal line, updates score, and triggers particle effects."""
        goal_scored = False
        in_goal_mouth = self.physics_engine.is_in_goal_mouth(self.ball)

        if in_goal_mouth and self.ball.pos.x < self.physics_engine.pitch_bounds.left:
            self.p2_score += 1
            goal_scored = True
            self.stats_tracker.log_goal("p2")
            self.particle_system.spawn_explosion(self.ball.pos.x, self.ball.pos.y, THEME["team_away"], count=50)

        elif in_goal_mouth and self.ball.pos.x > self.physics_engine.pitch_bounds.right:
            self.p1_score += 1
            goal_scored = True
            self.stats_tracker.log_goal("p1")
            self.particle_system.spawn_explosion(self.ball.pos.x, self.ball.pos.y, THEME["team_home"], count=50)

        if goal_scored:
            self.sound_manager.play_sfx("whistle")
            self._resetPositions()

        # Check win or full-time condition
        if self.p1_score >= self.MAX_GOALS or self.p2_score >= self.MAX_GOALS or self.match_time_elapsed >= self.MATCH_DURATION:
            self.is_game_over = True
            self.sound_manager.play_sfx("whistle")

    def _resetPositions(self):
        """Resets ball and player positions back to kickoff spots."""
        self.ball.pos = pygame.Vector2(self.screen_width // 2, self.screen_height // 2)
        self.ball.vel = pygame.Vector2(0, 0)

        self.player1.pos = pygame.Vector2(int(self.screen_width * 0.3125), self.screen_height // 2)
        self.player1.vel = pygame.Vector2(0, 0)
        self.player1.power_charge_level = 0.0

        self.player2.pos = pygame.Vector2(int(self.screen_width * 0.6875), self.screen_height // 2)
        self.player2.vel = pygame.Vector2(0, 0)
        self.player2.power_charge_level = 0.0

    def renderScene(self):
        """Renders pitch, players, ball, scoreboard HUD, and active overlays."""
        screen = getattr(self, "screen", None) or pygame.display.get_surface()
        if not getattr(self, "pitch_renderer", None):
            if screen:
                screen.fill(THEME["bg_dark"])
            return

        self.pitch_renderer.drawBackground(self.screen, self.asset_manager)
        self.ball.draw(self.screen, self.asset_manager)
        self.player1.drawAnimated(self.screen, self.asset_manager)
        self.player2.drawAnimated(self.screen, self.asset_manager)
        self.particle_system.draw(self.screen)

        self._drawScoreBoard()

        if self.is_game_over:
            self._drawGameOverScreen()

        if self.is_paused:
            self._drawPauseMenu()

        pygame.display.flip()

    def _drawScoreBoard(self):
        """Renders top scoreboard bar showing P1 score, match clock, and P2 score."""
        cx = self.screen_width // 2
        bar_w, bar_h = self.s(440), self.s(52)
        bar_rect = pygame.Rect(cx - bar_w // 2, self.s(14), bar_w, bar_h)

        pygame.draw.rect(self.screen, (8, 6, 6), bar_rect.move(0, 4), border_radius=10)
        pygame.draw.rect(self.screen, THEME["card_bg"], bar_rect, border_radius=10)
        pygame.draw.rect(self.screen, THEME["border"], bar_rect, 2, border_radius=10)

        p1_surf = self.font_hud_score.render(f"P1  {self.p1_score}", True, THEME["team_home"], THEME["card_bg"])
        self.screen.blit(p1_surf, (bar_rect.left + self.s(24), bar_rect.centery - p1_surf.get_height() // 2))

        # Simulated 90-minute time display
        simulated_total_sec = (self.match_time_elapsed / self.MATCH_DURATION) * 5400
        sim_minutes = min(90, int(simulated_total_sec // 60))
        sim_seconds = int(simulated_total_sec % 60) if sim_minutes < 90 else 0
        time_str = f"{sim_minutes:02d}:{sim_seconds:02d}"

        time_surf = self.font_hud_clock.render(time_str, True, THEME["text_primary"], THEME["card_bg"])
        self.screen.blit(time_surf, time_surf.get_rect(center=(cx, bar_rect.centery)))

        p2_surf = self.font_hud_score.render(f"{self.p2_score}  P2", True, THEME["team_away"], THEME["card_bg"])
        self.screen.blit(p2_surf, (bar_rect.right - self.s(24) - p2_surf.get_width(), bar_rect.centery - p2_surf.get_height() // 2))

    def _draw_keybind_row(self, label, p1_text, p2_text, left_x, right_x, center_y):
        """Renders action label alongside keycaps for P1 and P2."""
        lbl = self.font_body.render(label, True, THEME["text_muted"], THEME["card_bg"])
        self.screen.blit(lbl, (left_x, center_y - lbl.get_height() // 2))

        if p2_text is not None:
            p2_surf = self.font_sub.render(f"P2: {p2_text}", True, THEME["team_away"], THEME["input_bg"])
            p2_w, p2_h = p2_surf.get_size()
            pill_p2 = pygame.Rect(0, 0, p2_w + self.s(14), p2_h + self.s(8))
            pill_p2.right = right_x
            pill_p2.centery = center_y
            pygame.draw.rect(self.screen, THEME["input_bg"], pill_p2, border_radius=6)
            pygame.draw.rect(self.screen, THEME["border"], pill_p2, 1, border_radius=6)
            self.screen.blit(p2_surf, p2_surf.get_rect(center=pill_p2.center))

            p1_surf = self.font_sub.render(f"P1: {p1_text}", True, THEME["team_home"], THEME["input_bg"])
            p1_w, p1_h = p1_surf.get_size()
            pill_p1 = pygame.Rect(0, 0, p1_w + self.s(14), p1_h + self.s(8))
            pill_p1.right = pill_p2.left - self.s(8)
            pill_p1.centery = center_y
            pygame.draw.rect(self.screen, THEME["input_bg"], pill_p1, border_radius=6)
            pygame.draw.rect(self.screen, THEME["border"], pill_p1, 1, border_radius=6)
            self.screen.blit(p1_surf, p1_surf.get_rect(center=pill_p1.center))
        else:
            key_surf = self.font_sub.render(p1_text, True, THEME["primary"], THEME["input_bg"])
            kw, kh = key_surf.get_size()
            pill = pygame.Rect(0, 0, kw + self.s(18), kh + self.s(8))
            pill.right = right_x
            pill.centery = center_y
            pygame.draw.rect(self.screen, THEME["input_bg"], pill, border_radius=6)
            pygame.draw.rect(self.screen, THEME["border"], pill, 1, border_radius=6)
            self.screen.blit(key_surf, key_surf.get_rect(center=pill.center))

    def _drawPauseMenu(self):
        """Renders pause menu overlay with keybindings and resume/exit buttons."""
        cx = self.screen_width // 2
        cy = self.screen_height // 2

        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((8, 6, 6, 185))
        self.screen.blit(overlay, (0, 0))

        card_w, card_h = self.s(820), self.s(460)
        card = pygame.Rect(cx - card_w // 2, cy - card_h // 2, card_w, card_h)
        pygame.draw.rect(self.screen, (8, 6, 6), card.move(0, 8), border_radius=14)
        pygame.draw.rect(self.screen, THEME["card_bg"], card, border_radius=14)
        pygame.draw.rect(self.screen, THEME["border"], card, 2, border_radius=14)

        title_surf = self.font_title.render("MATCH PAUSED", True, THEME["text_primary"], THEME["card_bg"])
        self.screen.blit(title_surf, title_surf.get_rect(center=(cx, card.top + self.s(45))))

        sub_surf = self.font_body.render("Take a breather. The match will wait for you.", True, THEME["text_muted"], THEME["card_bg"])
        self.screen.blit(sub_surf, sub_surf.get_rect(center=(cx, card.top + self.s(80))))

        pygame.draw.line(self.screen, THEME["border"], (cx - self.s(30), card.top + self.s(115)), (cx - self.s(30), card.bottom - self.s(35)), 1)

        self._draw_pause_button(self.rect_resume, "RESUME MATCH", "resume", is_primary=True)
        self._draw_pause_button(self.rect_exit_match, "RETURN TO MENU", "exit", is_primary=False)

        right_left_x = cx + self.s(15)
        right_end_x = card.right - self.s(25)
        ctrl_title = self.font_button.render("MATCH CONTROLS", True, THEME["text_primary"], THEME["card_bg"])
        self.screen.blit(ctrl_title, (right_left_x, card.top + self.s(130)))

        gameplay_binds = [
            ("Movement", "WASD", "ARROWS", self.s(190)),
            ("Sprint / Boost", "L-SHIFT", "R-SHIFT", self.s(250)),
            ("Shoot / Clearance", "SPACE", "ENTER", self.s(310)),
            ("Resume / Pause", "ESC / P", None, self.s(370)),
        ]
        for action, p1_key, p2_key, offset_y in gameplay_binds:
            self._draw_keybind_row(action, p1_key, p2_key, right_left_x, right_end_x, card.top + offset_y)

    def _draw_pause_button(self, rect, label, key, is_primary=False):
        """Draws pause menu buttons with hover animation."""
        mouse_pos = pygame.mouse.get_pos()
        hovered = rect.collidepoint(mouse_pos)
        progress = self.pause_button_hover[key]
        progress += ((1.0 if hovered else 0.0) - progress) * 0.22
        self.pause_button_hover[key] = progress

        scale = 1.0 + progress * 0.03
        draw_rect = pygame.Rect(0, 0, int(rect.width * scale), int(rect.height * scale))
        draw_rect.center = rect.center

        base_col = pygame.Color(*THEME["primary"]) if is_primary else pygame.Color(*THEME["card_bg"])
        border_col = THEME["text_primary"] if (hovered and is_primary) else (THEME["primary"] if hovered else THEME["border"])

        pygame.draw.rect(self.screen, (8, 6, 6), draw_rect.move(0, 4), border_radius=8)
        pygame.draw.rect(self.screen, base_col, draw_rect, border_radius=8)
        pygame.draw.rect(self.screen, border_col, draw_rect, 2, border_radius=8)

        text_surf = self.font_body.render(label, True, THEME["text_primary"], base_col)
        self.screen.blit(text_surf, text_surf.get_rect(center=draw_rect.center))

    def _drawGameOverScreen(self):
        """Renders end-of-match stats summary and rematch prompts."""
        cx = self.screen_width // 2
        cy = self.screen_height // 2

        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((8, 6, 6, 205))
        self.screen.blit(overlay, (0, 0))

        card_w, card_h = self.s(720), self.s(520)
        card = pygame.Rect(cx - card_w // 2, cy - card_h // 2, card_w, card_h)
        pygame.draw.rect(self.screen, (8, 6, 6), card.move(0, 8), border_radius=14)
        pygame.draw.rect(self.screen, THEME["card_bg"], card, border_radius=14)
        pygame.draw.rect(self.screen, THEME["border"], card, 2, border_radius=14)

        if self.p1_score > self.p2_score:
            win_msg = "PLAYER 1 WINS!"
            win_color = THEME["team_home"]
        elif self.p2_score > self.p1_score:
            win_msg = "PLAYER 2 WINS!"
            win_color = THEME["team_away"]
        else:
            win_msg = "HONOURS EVEN (DRAW)"
            win_color = THEME["text_primary"]

        title_surf = self.font_hud_title.render(win_msg, True, win_color, THEME["card_bg"])
        self.screen.blit(title_surf, title_surf.get_rect(center=(cx, card.top + self.s(55))))

        p1_poss, p2_poss = self.stats_tracker.get_possession_percentages()
        p1_shots = self.stats_tracker.stats["p1"]["shots"]
        p2_shots = self.stats_tracker.stats["p2"]["shots"]

        stats_data = [
            ("GOALS", str(self.p1_score), str(self.p2_score)),
            ("SHOTS LOGGED", str(p1_shots), str(p2_shots)),
            ("POSSESSION", f"{p1_poss}%", f"{p2_poss}%"),
        ]

        start_y = card.top + self.s(150)
        for i, (label, p1_val, p2_val) in enumerate(stats_data):
            row_y = start_y + (i * self.s(68))
            pygame.draw.line(self.screen, THEME["card_border"], (card.left + self.s(50), row_y + self.s(34)), (card.right - self.s(50), row_y + self.s(34)), 1)

            p1_surf = self.font_hud_stat.render(p1_val, True, THEME["team_home"], THEME["card_bg"])
            self.screen.blit(p1_surf, p1_surf.get_rect(center=(cx - self.s(190), row_y)))

            lbl_surf = self.font_body.render(label, True, THEME["text_muted"], THEME["card_bg"])
            self.screen.blit(lbl_surf, lbl_surf.get_rect(center=(cx, row_y)))

            p2_surf = self.font_hud_stat.render(p2_val, True, THEME["team_away"], THEME["card_bg"])
            self.screen.blit(p2_surf, p2_surf.get_rect(center=(cx + self.s(190), row_y)))

        sub_surf = self.font_sub.render("PRESS [R] TO PLAY AGAIN", True, THEME["text_primary"], THEME["card_bg"])
        self.screen.blit(sub_surf, sub_surf.get_rect(center=(cx, card.bottom - self.s(60))))

        exit_surf = self.font_sub.render("PRESS [ESC] TO SAVE & RETURN TO MAIN MENU", True, THEME["text_muted"], THEME["card_bg"])
        self.screen.blit(exit_surf, exit_surf.get_rect(center=(cx, card.bottom - self.s(32))))

    async def runMatchLoop(self):
        """Main game loop managing ticking, event processing, transitions, and rendering."""
        self.initialiseGame()
        running = True

        while running:
            self.dt = self.clock.tick(self.fps) / 1000.0
            signal = self.handleMainEvents()

            if signal == "EXIT_TO_MENU":
                self.sound_manager.stop_all()
                self.saveStatsAndHistory()
                if self.is_online and self.network_client:
                    await self.network_client.disconnect()
                running = False
                continue

            elif signal == "RESTART_MATCH":
                self.sound_manager.stop_all()
                if not self.transition:
                    self.transition = TransitionManager(self.screen)

                await self.transition.fade_out(duration=0.25)
                self._hardResetMatch()
                await self.transition.show_loading(
                    title="RESTARTING MATCH...",
                    subtitle="Resetting pitch and player formations",
                    min_duration=0.45,
                )
                continue

            await self.updateMatchState()
            self.renderScene()
            await asyncio.sleep(0)

    def saveStatsAndHistory(self):
        """Encrypts updated match statistics and commits them to userdata.json."""
        if self.launcher_backend and self.menu_system:
            user_id = self.launcher_backend.active_user_session
            if user_id:
                match_stats = self.stats_tracker.stats.get("p1", {})
                final_stats = {
                    key: self.saved_profile.get(key, 0) + match_stats.get(key, 0)
                    for key in ("goals", "shots", "possession_time")
                }
                derived_key = hashlib.sha256(
                    self.menu_system.password_buffer.strip().replace(" ", "").encode("utf-8")
                ).digest()
                fernet_key = base64.urlsafe_b64encode(derived_key)

                encrypted_data = EncryptionEngine.encryptData(final_stats, fernet_key)
                if encrypted_data:
                    with open(self.launcher_backend.userdata_path, "r", encoding="utf-8") as f:
                        user_db = json.load(f)
                    user_db[user_id] = encrypted_data
                    with open(self.launcher_backend.userdata_path, "w", encoding="utf-8") as f:
                        json.dump(user_db, f, indent=4)
                    self.saved_profile = final_stats
                    self.menu_system.temp_saved_profile = final_stats.copy()
                    self.launcher_backend.temp_saved_profile = final_stats.copy()

        if hasattr(self, "ai_manager") and hasattr(self.ai_manager, "pattern_analyser"):
            self.ai_manager.pattern_analyser.saveHistory()

    def terminateGame(self):
        """Saves current state and terminates application."""
        self.saveStatsAndHistory()
        pygame.quit()
        sys.exit()

    def _resetMatch(self):
        self.p1_score = 0
        self.p2_score = 0
        self.is_game_over = False
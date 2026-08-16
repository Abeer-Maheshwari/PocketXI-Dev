import sys
import json
import pygame
import hashlib
import base64
import asyncio
from src.team import TeamLoader
from src.ai import AIManager
from src.animation import AnimationManager
from src.sound import SoundManager
from src.stats import StatsTracker
from src.renderer import PitchRenderer
from src.entities import ParticleSystem, Player, Ball
from src.physics import PhysicsEngine
from src.encryption import EncryptionEngine

class MatchController:
    # manages the game loop, state transitions, and assigns tasks to other engines / modules
    def __init__(self, launcher_backend=None, menu_system=None, network_client=None, is_online=False):
        # core variables
        self.screen_width = 1280
        self.screen_height = 720
        self.fps = 60
        self.screen = None
        self.clock = None
        self.dt = 0.0

        # launcher references
        self.launcher_backend = launcher_backend
        self.menu_system = menu_system
        self.network_client = network_client
        self.is_online = is_online

        # game state variables
        self.p1_score = 0
        self.p2_score = 0
        self.MAX_GOALS = 10
        self.is_game_over = False
        self.is_paused = False
        self.match_time_remaining = 300.0
        self.rect_resume = pygame.Rect(self.screen_width // 2 - 180, 380, 360, 62)
        self.rect_exit_match = pygame.Rect(self.screen_width // 2 - 180, 460, 360, 62)
        self.pause_button_hover = {"resume": 0.0, "exit": 0.0}

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
        volume = self.launcher_backend.master_volume if self.launcher_backend else 1.0
        self.sound_manager = SoundManager("assets/audio", master_volume=volume)
        self.stats_tracker = StatsTracker()

        # Keep persisted profile data separate from the per-match p1/p2 statistics.
        self.saved_profile = {}
        if self.launcher_backend and self.menu_system:
            profile = self.menu_system.temp_saved_profile
            if isinstance(profile, dict):
                self.saved_profile = profile.copy()

        self.pitch_renderer = PitchRenderer(self.screen_width, self.screen_height)
        self.particle_system = ParticleSystem()
        self.physics_engine = PhysicsEngine(pygame.Rect(50, 50, self.screen_width - 100, self.screen_height - 100), self.sound_manager, self.stats_tracker, self.ai_manager, self.particle_system)
        self.sound_manager.play_sfx("whistle") # Kickoff whistle

        # Online controls 
        p1_controls = "WASD" if (not self.is_online or self.network_client.player_role == "p1") else "NETWORK"
        p2_controls = "ARROWS" if (not self.is_online) else ("WASD" if self.network_client.player_role == "p2" else "NETWORK")

        self.player1 = Player(self.sound_manager, player_id="p1", start_pos=(400, 360), controls="WASD", stats=p1_stats)
        self.player2 = Player(self.sound_manager, player_id="p2", start_pos=(880, 360), controls="ARROWS", stats=p2_stats)
        self.ball = Ball(start_pos=(self.screen_width // 2, self.screen_height // 2))
        
        # Goal positions for FSM reference
        self.p1_goal_pos = pygame.Vector2(10, self.screen_height // 2)
        self.p2_goal_pos = pygame.Vector2(self.screen_width - 50, self.screen_height // 2)

        print("Game Initialised Successfully.")

    def handleMainEvents(self):
        # Processes system-level events. All pause state changes go through
        # _set_pause_state so the simulation and mixer remain in sync.
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.terminateGame()

            if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                    and self.is_paused and not self.is_game_over):
                if self.rect_resume.collidepoint(event.pos):
                    self._set_pause_state(False)
                elif self.rect_exit_match.collidepoint(event.pos):
                    return "EXIT_TO_MENU"
            
            if event.type == pygame.KEYDOWN:
                if self.is_game_over:
                    if event.key == pygame.K_r:
                        self._hardResetMatch()
                    elif event.key == pygame.K_ESCAPE:
                        return "EXIT_TO_MENU"
                else:
                    if event.key == pygame.K_ESCAPE or event.key == pygame.K_p:
                        self._set_pause_state(not self.is_paused)
        return "KEEP_RUNNING"

    def _set_pause_state(self, paused):
        """Change pause state and keep audio aligned with the match state."""
        if paused == self.is_paused:
            return

        self.is_paused = paused
        if self.sound_manager:
            self.sound_manager.set_paused(paused)

    def _hardResetMatch(self):
        # Full reset of the match state
        self.p1_score = 0
        self.p2_score = 0
        self.match_time_remaining = 300.0
        self.is_game_over = False
        self._set_pause_state(False)
        self._resetPositions()
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

        # Apply the user-selected difficulty tier (1--5) on top of the
        # score-based balancing.  Settings previously changed a value that
        # the match never consumed.
        if self.launcher_backend:
            tier = max(1, min(int(self.launcher_backend.base_difficulty_tier), 5))
            speed_modifier *= 0.8 + (tier - 1) * 0.1
            reaction_delay += (5 - tier) * 0.075
            
        # Compile in one dictionary
        modifiers = {
            "max_velocity_mult": speed_modifier,
            "reaction_delay": reaction_delay
        }
        
        return modifiers
    
    async def updateMatchState(self):
        # Coordinates physics and movement updates while match is running
        if self.is_game_over or self.is_paused:
            return
        
        # Decrement Match Timer
        self.updateTimer()

        # Update VFX
        self.particle_system.update(self.dt)

        # Play ambient sound
        self.sound_manager.update_ambient_chants()

        # ONLINE vs OFFLINE
        if self.is_online and self.network_client:
            is_host = (self.network_client.player_role == "p1")

            # 1. Process incoming packets
            for msg in self.network_client.pop_messages():
                if msg.get("status") == "relay":
                    payload = msg.get("payload", {})
                    p_type = payload.get("type")

                    # Host receives inputs from Guest
                    if is_host and p_type == "GUEST_INPUT":
                        self.player2.vel = pygame.Vector2(payload["vel"][0], payload["vel"][1])
                        self.player2.is_sprinting = payload.get("sprint", False)
                        self.player2.is_charging = payload.get("charge", False)

                    # Guest receives authoritative state from Host
                    elif not is_host and p_type == "HOST_STATE":
                        self.ball.pos = pygame.Vector2(payload["ball_pos"][0], payload["ball_pos"][1])
                        self.ball.vel = pygame.Vector2(payload["ball_vel"][0], payload["ball_vel"][1])
                        self.player1.pos = pygame.Vector2(payload["p1_pos"][0], payload["p1_pos"][1])
                        self.player1.vel = pygame.Vector2(payload["p1_vel"][0], payload["p1_vel"][1])
                        self.p1_score = payload["scores"][0]
                        self.p2_score = payload["scores"][1]
                        self.match_time_remaining = payload["time"]

            # 2. Local input & transmission
            if is_host:
                self.player1.handleInput()
                self.player1.updatePosition(self.dt)
                self.player2.updatePosition(self.dt)
                
                # Apply physics & send snapshot to guest
                if self.ball.vel.length() > 0:
                    self.ball.vel = self.physics_engine.calculateCurve(self.ball.vel, self.ball.active_spin, self.ball.target_offset)
                self.ball.applyPhysics(self.dt)

                await self.network_client.send_relay({
                    "type": "HOST_STATE",
                    "ball_pos": [self.ball.pos.x, self.ball.pos.y],
                    "ball_vel": [self.ball.vel.x, self.ball.vel.y],
                    "p1_pos": [self.player1.pos.x, self.player1.pos.y],
                    "p1_vel": [self.player1.vel.x, self.player1.vel.y],
                    "scores": [self.p1_score, self.p2_score],
                    "time": self.match_time_remaining
                })
            else:
                self.player2.handleInput()
                self.player2.updatePosition(self.dt)
                self.player1.updatePosition(self.dt)

                await self.network_client.send_relay({
                    "type": "GUEST_INPUT",
                    "vel": [self.player2.vel.x, self.player2.vel.y],
                    "sprint": self.player2.is_sprinting,
                    "charge": self.player2.is_charging
                })

        else:
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
            if not self.is_online or (self.network_client and self.network_client.player_role == "p1"):
                self.physics_engine.resolveBoundaryCollision(self.player1)
                self.physics_engine.resolveBoundaryCollision(self.player2)
                self.physics_engine.resolveBoundaryCollision(self.ball)
                self.physics_engine.checkPvPCollision(self.player1, self.player2)
                self.physics_engine.checkPvBCollision(self.player1, self.ball)
                self.physics_engine.checkPvBCollision(self.player2, self.ball)
                self._checkGoalConditions()
    
    def _checkGoalConditions(self):
        # A goal requires two conditions: crossing a goal line and passing
        # through the same goal mouth that boundary collision leaves open.
        goal_scored = False
        in_goal_mouth = self.physics_engine.is_in_goal_mouth(self.ball)

        # Check Player 2 Scores (left goal)
        if in_goal_mouth and self.ball.pos.x < self.physics_engine.pitch_bounds.left:
            self.p2_score += 1
            goal_scored = True
            self.stats_tracker.log_goal("p2")
            self.particle_system.spawn_explosion(self.ball.pos.x, self.ball.pos.y, (100, 100, 255), count=50)
            print("Goal for Player 2!")

        # Check Player 1 (right goal)
        elif in_goal_mouth and self.ball.pos.x > self.physics_engine.pitch_bounds.right:
            self.p1_score += 1
            goal_scored = True
            self.stats_tracker.log_goal("p1")
            self.particle_system.spawn_explosion(self.ball.pos.x, self.ball.pos.y, (255, 100, 100), count=50)
            print("Goal for Player 1!")

        # Blows whistle and resets pitch if goal scored
        if goal_scored:
            self.sound_manager.play_sfx("whistle")
            self._resetPositions()
        
        # A match ends when a player reaches the target score or time expires.
        if (self.p1_score >= self.MAX_GOALS or self.p2_score >= self.MAX_GOALS
                or self.match_time_remaining <= 0):
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
        # Render a card-style overlay consistent with the main menu.
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((3, 10, 22, 185))
        self.screen.blit(overlay, (0, 0))

        panel = pygame.Rect(self.screen_width // 2 - 260, 170, 520, 390)
        pygame.draw.rect(self.screen, (8, 14, 27), panel.move(0, 9), border_radius=18)
        pygame.draw.rect(self.screen, (30, 41, 59), panel, border_radius=18)
        pygame.draw.rect(self.screen, (115, 186, 255), panel, 2, border_radius=18)

        title_font = pygame.font.SysFont("Arial", 52, bold=True)
        title_surf = title_font.render("PAUSED", True, "white")
        self.screen.blit(title_surf, title_surf.get_rect(center=(self.screen_width // 2, 250)))

        sub_font = pygame.font.SysFont("Arial", 20)
        sub_surf = sub_font.render("Take a breather. The match will wait for you.", True, (200, 215, 235))
        self.screen.blit(sub_surf, sub_surf.get_rect(center=(self.screen_width // 2, 300)))

        self._draw_pause_button(self.rect_resume, "RESUME MATCH", "ESC  /  P", (30, 120, 70), "resume")
        self._draw_pause_button(self.rect_exit_match, "SAVE & RETURN TO MENU", "", (155, 65, 70), "exit")

    def _draw_pause_button(self, rect, label, shortcut, accent, key):
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        progress = self.pause_button_hover[key]
        progress += ((1.0 if hovered else 0.0) - progress) * 0.2
        self.pause_button_hover[key] = progress

        scale = 1.0 + progress * 0.025
        draw_rect = pygame.Rect(0, 0, int(rect.width * scale), int(rect.height * scale))
        draw_rect.center = rect.center
        colour = pygame.Color(30, 41, 59).lerp(pygame.Color(accent), 0.35 + progress * 0.45)

        pygame.draw.rect(self.screen, (8, 14, 27), draw_rect.move(0, int(6 - progress * 3)), border_radius=10)
        pygame.draw.rect(self.screen, colour, draw_rect, border_radius=10)
        pygame.draw.rect(self.screen, accent, draw_rect, 3 if hovered else 1, border_radius=10)

        label_font = pygame.font.SysFont("Arial", 20, bold=True)
        label_surface = label_font.render(label, True, "white")
        label_y = draw_rect.centery - 9 if shortcut else draw_rect.centery
        self.screen.blit(label_surface, label_surface.get_rect(center=(draw_rect.centerx, label_y)))
        if shortcut:
            shortcut_surface = pygame.font.SysFont("Arial", 14).render(shortcut, True, (220, 235, 245))
            self.screen.blit(shortcut_surface, shortcut_surface.get_rect(center=(draw_rect.centerx, draw_rect.centery + 15)))

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

    async def runMatchLoop(self):
        self.initialiseGame()
        running = True
        
        while running:
            self.dt = self.clock.tick(self.fps) / 1000.0
            signal = self.handleMainEvents()
            
            if signal == "EXIT_TO_MENU":
                # Do not leave a paused global mixer behind for the next match.
                self.sound_manager.stop_all()
                self.saveStatsAndHistory()
                if self.is_online and self.network_client:
                    await self.network_client.disconnect()
                running = False
                continue
                
            await self.updateMatchState()
            self.renderScene()
            
            # Yield control back to browser / Pyodide event loop
            await asyncio.sleep(0)

    def saveStatsAndHistory(self):
        # Dedicated method to save data without quitting
        if self.launcher_backend and self.menu_system:
            user_id = self.launcher_backend.active_user_session
            if user_id:
                match_stats = self.stats_tracker.stats.get("p1", {})
                final_stats = {
                    key: self.saved_profile.get(key, 0) + match_stats.get(key, 0)
                    for key in ("goals", "shots", "possession_time")
                }
                # Derive the key from the password (still stored in buffer)
                derived_key = hashlib.sha256(self.menu_system.password_buffer.strip().replace(" ", "").encode('utf-8')).digest()
                fernet_key = base64.urlsafe_b64encode(derived_key)
                
                encrypted_data = EncryptionEngine.encryptData(final_stats, fernet_key)
                if encrypted_data:
                    with open(self.launcher_backend.userdata_path, 'r', encoding='utf-8') as f:
                        user_db = json.load(f)
                    user_db[user_id] = encrypted_data
                    with open(self.launcher_backend.userdata_path, 'w', encoding='utf-8') as f:
                        json.dump(user_db, f, indent=4)
                    self.saved_profile = final_stats
                    self.menu_system.temp_saved_profile = final_stats.copy()
                    self.launcher_backend.temp_saved_profile = final_stats.copy()
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

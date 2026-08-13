import math
import random
import pygame

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
            
            # Calculate Idle Delta
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
        # Updates the ball's position and simulates friction.
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

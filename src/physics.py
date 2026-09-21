import math
import random
import pygame


class PhysicsEngine:
    # Goal mouth vertical half-height for goal detection
    GOAL_HALF_HEIGHT = 60

    def __init__(self, pitch_rect, sound_manager, stats_tracker, ai_manager, particle_system):
        self.pitch_bounds = pitch_rect
        self.sound_manager = sound_manager
        self.stats_tracker = stats_tracker
        self.ai_manager = ai_manager
        self.particle_system = particle_system
    
    def resolveBoundaryCollision(self, entity):
        # Keep players on pitch; let the ball pass through if entering goal mouth
        is_ball = hasattr(entity, 'friction')
        can_score = is_ball and self.is_in_goal_mouth(entity)
        
        # Left / Right boundaries
        if entity.pos.x - entity.radius < self.pitch_bounds.left:
            if not can_score:
                entity.pos.x = self.pitch_bounds.left + entity.radius
                if is_ball: 
                    entity.vel.x *= -1 
                    self.sound_manager.play_impact()
                
        elif entity.pos.x + entity.radius > self.pitch_bounds.right:
            if not can_score:
                entity.pos.x = self.pitch_bounds.right - entity.radius
                if is_ball:
                    entity.vel.x *= -1
                    self.sound_manager.play_impact()

        # Top / Bottom boundaries
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

    def is_in_goal_mouth(self, ball):
        # Check if ball is vertically aligned with the goal opening
        pitch_mid_y = self.pitch_bounds.centery
        clearance = self.GOAL_HALF_HEIGHT - ball.radius
        return abs(ball.pos.y - pitch_mid_y) < clearance
    
    def checkPvPCollision(self, player1, player2):
        # Push colliding players apart based on their strength stats
        distance_vector = player1.pos - player2.pos
        distance = distance_vector.length()
        min_distance = player1.radius + player2.radius
        
        if distance < min_distance:
            if distance == 0:
                distance_vector = pygame.Vector2(1, 0)
                distance = 1

            overlap = min_distance - distance
            push_vector = distance_vector.normalize() * (overlap / 2)

            total_strength = max(player1.strength + player2.strength, 0.001)
            player1.pos += push_vector * (2 * player2.strength / total_strength)
            player2.pos -= push_vector * (2 * player1.strength / total_strength)
        
    def checkPvBCollision(self, player, ball):
        # Handle player kicking the ball
        distance_vector = ball.pos - player.pos
        distance = distance_vector.length()
        min_distance = player.radius + ball.radius
        
        if distance < min_distance:
            if distance == 0:
                distance_vector = pygame.Vector2(1, 0)
                distance = 1

            # Prevent ball sticking inside player body
            overlap = min_distance - distance
            push_vector = distance_vector.normalize() * overlap
            ball.pos += push_vector
            
            kick_direction = distance_vector.normalize()
            base_power = 400
            momentum = player.vel.length() * 0.5

            self.sound_manager.play_sfx("kick")
            ball.last_touched_by = player.player_id

            # Apply charged power shot if active
            multiplier = 1.0
            if player.power_charge_level > 0.1:
                shot_cost = (player.power_charge_level / player.MAX_CHARGE) * 30.0
                
                if player.applyStaminaCost(shot_cost):
                    multiplier = 1.0 + (player.power_charge_level * 1.5)
                    player.power_charge_level = 0.0
                    self.stats_tracker.log_shot(player.player_id)
                    
                    color = (255, 200, 50) if player.player_id == "p1" else (50, 200, 255)
                    self.particle_system.spawn_explosion(ball.pos.x, ball.pos.y, color, count=15, speed_range=(100, 300))
            else:
                self.particle_system.spawn_explosion(ball.pos.x, ball.pos.y, (255, 255, 255), count=5, speed_range=(20, 80))

            ball.vel = kick_direction * (base_power + momentum) * multiplier
            ball.active_spin = player.spin
            
            # Determine curve direction based on player's running angle relative to kick
            cross_product = kick_direction.x * player.vel.y - kick_direction.y * player.vel.x
            if cross_product > 0.1:
                ball.target_offset = 1.0  
            elif cross_product < -0.1:
                ball.target_offset = -1.0  
            else:
                ball.target_offset = 0.0  
            
            # Let AI learn shooting tendencies from human player
            if not player.is_afk:
                bias_data = self.ai_manager.pattern_analyser.analyseUserPattern(ball.pos, player.pos)
                if bias_data:
                    self.ai_manager.current_bias_data = bias_data

    def calculateCurve(self, velocity, spin_attribute, target_offset):
        # Apply Magnus effect curve to the ball
        if velocity.length() == 0:
            return velocity
            
        perp_vector = pygame.Vector2(-velocity.y, velocity.x).normalize()
        curvature_intensity = spin_attribute * target_offset
        magnus_force = perp_vector * curvature_intensity
        
        aerodynamic_threshold = 0.5
        MAX_CURVE = 8.0
        
        if abs(spin_attribute) > aerodynamic_threshold:
            deviation = magnus_force
            if deviation.length() > MAX_CURVE:
                deviation = deviation.normalize() * MAX_CURVE
            return velocity + deviation
        else:
            return pygame.Vector2(velocity)
    
    def applyDisplacement(self, physics_body, target_pos, current_pos, displacement_weight, max_velocity):
        # Smooth displacement helper
        d = (target_pos - current_pos) * displacement_weight
        if d.length() > max_velocity:
            d = d.normalize() * max_velocity
            
        physics_body.vel = pygame.Vector2(d)
        physics_body.pos += d
        return physics_body.vel, physics_body.pos


import math
import random
import pygame

class PhysicsEngine:
    # The goal mouth is centered on the pitch and is deliberately narrower
    # than the touchline. A ball must fit wholly inside this opening to score.
    GOAL_HALF_HEIGHT = 60

    # Dedicated module for spatial validation and collision resolution.
    def __init__(self, pitch_rect, sound_manager, stats_tracker, ai_manager, particle_system):
        self.pitch_bounds = pitch_rect
        self.sound_manager = sound_manager
        self.stats_tracker = stats_tracker
        self.ai_manager = ai_manager
        self.particle_system = particle_system
    
    def resolveBoundaryCollision(self, entity):
        """Keep entities in the pitch, except for balls travelling through a goal."""
        is_ball = hasattr(entity, 'friction')
        can_score = is_ball and self.is_in_goal_mouth(entity)

        # Players always bounce off side lines. Only a ball in the goal mouth
        # may cross a side line, after which MatchController awards the goal.
        
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

    def is_in_goal_mouth(self, ball):
        """Return whether the entire ball fits inside the vertical goal opening.

        This predicate is shared by boundary resolution and score detection so
        an out-of-bounds ball can never be mistaken for a goal.
        """
        pitch_mid_y = self.pitch_bounds.centery
        clearance = self.GOAL_HALF_HEIGHT - ball.radius
        return abs(ball.pos.y - pitch_mid_y) < clearance
    
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

            # Resolve the overlap directly.  Feeding a position displacement into
            # ``vel`` makes the next frame multiply it by player speed.
            total_strength = max(player1.strength + player2.strength, 0.001)
            player1.pos += push_vector * (2 * player2.strength / total_strength)
            player2.pos -= push_vector * (2 * player1.strength / total_strength)
        
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

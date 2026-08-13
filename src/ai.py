import math
import pygame
from src.stats import PatternAnalyser

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
            return # Manual Control

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
                ball_to_goal = enemy_goal_pos - ball.pos
                if ball_to_goal.length_squared() == 0:
                    ball_to_goal = pygame.Vector2(1, 0)
                else:
                    ball_to_goal = ball_to_goal.normalize()
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
                ball_to_goal = enemy_goal_pos - raw_intercept
                if ball_to_goal.length_squared() == 0:
                    ball_to_goal = pygame.Vector2(1, 0)
                else:
                    ball_to_goal = ball_to_goal.normalize()
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

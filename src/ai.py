import math
import pygame
from src.stats import PatternAnalyser


class AIManager:
    # State machine for AI bot decision making (Attack, Defend, Intercept)
    def __init__(self, pitch_bounds):
        self.pitch_bounds = pitch_bounds
        self.current_state = "INTERCEPT"
        self.target_pos = pygame.Vector2(0, 0)
        self.pattern_analyser = PatternAnalyser(pitch_bounds)
        self.current_bias_data = None
        
        # Reaction and shooting timers
        self.reaction_timer = 0.0
        self.shoot_timer = 0.0

    def predictIntercept(self, P_b, V_b, P_ai, S_ai):
        # Predict where the ball is heading based on speed and friction
        friction = 0.98
        
        direction_vector = P_b - P_ai
        D = direction_vector.length()
        
        # Estimate time to intercept
        if S_ai > 0:
            delta_t = D / S_ai
        else:
            delta_t = 0.0
            
        # Account for ball deceleration over time
        decay = (1.0 - math.pow(friction, delta_t * 60)) / (1.0 - friction) / 60.0
        P_target = P_b + (V_b * decay)
        
        # Keep predicted target inside pitch boundaries
        P_target.x = max(self.pitch_bounds.left, min(P_target.x, self.pitch_bounds.right))
        P_target.y = max(self.pitch_bounds.top, min(P_target.y, self.pitch_bounds.bottom))
        
        return P_target

    def updateFSM(self, ai_player, opponent, ball, my_goal_pos, enemy_goal_pos, modifiers):
        # Main AI update step - evaluate situation and pick target position
        if not ai_player.is_afk:
            return  # Manual player control

        dt = 1 / 60.0 
        
        # Check if we should re-evaluate decisions or wait out reaction timer
        recalculate = True
        if self.reaction_timer > 0:
            self.reaction_timer -= dt
            recalculate = False

        # Apply difficulty modifiers
        adjusted_speed = ai_player.speed * modifiers["max_velocity_mult"]
        reaction_delay = modifiers.get("reaction_delay", 0.0)

        if recalculate:
            # Check ball possession based on distance
            dist_to_ball = (ai_player.pos - ball.pos).length()
            ai_has_ball = dist_to_ball <= 100
            user_has_ball = (opponent.pos - ball.pos).length() <= 80
            
            if ai_has_ball:
                self.current_state = "ATTACK"
                
                # Try getting behind the ball facing the opponent's goal
                ball_to_goal = enemy_goal_pos - ball.pos
                if ball_to_goal.length_squared() == 0:
                    ball_to_goal = pygame.Vector2(1, 0)
                else:
                    ball_to_goal = ball_to_goal.normalize()
                
                behind_ball_pos = ball.pos - ball_to_goal * 40 
                dist_to_goal = (ai_player.pos - enemy_goal_pos).length()
                
                if (ai_player.pos - behind_ball_pos).length() > 30:
                    # Move behind the ball first
                    self.target_pos = behind_ball_pos
                elif dist_to_goal > 250:
                    # Find open space toward the goal
                    self.target_pos = self.processHeatmap(ai_player.pos, opponent.pos, enemy_goal_pos)
                else:
                    # Close enough to shoot
                    self.target_pos = enemy_goal_pos
                    
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
                
                # Position between ball and our own goal
                base_target = (ball.pos + my_goal_pos) / 2 
                
                # Shift positioning if we've learned the player's shooting habits
                if self.current_bias_data and self.current_bias_data["bias_active"]:
                    favored_sector = self.current_bias_data["favored_sector"]
                    
                    sector_w = self.pitch_bounds.width / 4
                    sector_h = self.pitch_bounds.height / 4
                    col = favored_sector % 4
                    row = favored_sector // 4
                    
                    bias_x = self.pitch_bounds.left + (col * sector_w) + (sector_w / 2)
                    bias_y = self.pitch_bounds.top + (row * sector_h) + (sector_h / 2)
                    bias_vector = pygame.Vector2(bias_x, bias_y)
                    
                    # Shift defensive stance 30% toward player's favored zone
                    self.target_pos = base_target.lerp(bias_vector, 0.3)
                else:
                    self.target_pos = base_target
                
            else:
                self.current_state = "INTERCEPT"
                ai_player.is_charging = False
                self.shoot_timer = 0
                
                # Intercept ball while keeping goal direction in mind
                raw_intercept = self.predictIntercept(ball.pos, ball.vel, ai_player.pos, adjusted_speed)
                ball_to_goal = enemy_goal_pos - raw_intercept
                if ball_to_goal.length_squared() == 0:
                    ball_to_goal = pygame.Vector2(1, 0)
                else:
                    ball_to_goal = ball_to_goal.normalize()
                self.target_pos = raw_intercept - ball_to_goal * 30

            if reaction_delay > 0:
                self.reaction_timer = reaction_delay

        # Calculate movement vector towards current target
        move_vector = pygame.Vector2(0, 0)
        distance_to_target = (self.target_pos - ai_player.pos).length()
        
        if distance_to_target > 10:
            move_vector = (self.target_pos - ai_player.pos).normalize()

        ai_player.vel = move_vector
        ai_player.current_speed = adjusted_speed

        # Sprint if target is far away and stamina allows
        if distance_to_target > 150 and ai_player.stamina > 20.0:
            ai_player.is_sprinting = True
        else:
            ai_player.is_sprinting = False
    
    def processHeatmap(self, ai_pos, opponent_pos, enemy_goal_pos):
        # Score 4x4 pitch sectors to find good open space to run into
        cols, rows = 4, 4
        sector_w = self.pitch_bounds.width / cols
        sector_h = self.pitch_bounds.height / rows
        
        heatmap = {}
        
        for c in range(cols):
            for r in range(rows):
                sector_id = (r * cols) + c
                cell_x = self.pitch_bounds.left + (c * sector_w) + (sector_w / 2)
                cell_y = self.pitch_bounds.top + (r * sector_h) + (sector_h / 2)
                cell_pos = pygame.Vector2(cell_x, cell_y)
                
                score = 0.0
                
                # Reward sectors closer to the opponent's goal
                dist_to_goal = (cell_pos - enemy_goal_pos).length()
                score += max(0, 1000 - dist_to_goal) 
                
                # Penalize sectors close to the opponent defender
                dist_to_opponent = (cell_pos - opponent_pos).length()
                if dist_to_opponent < 150: 
                    score -= 500
                    
                heatmap[sector_id] = {"score": score, "pos": cell_pos}
                
        # Boost score of player's commonly attacked sector if we have learned data
        if self.current_bias_data and self.current_bias_data["bias_active"]:
            favored_sector = self.current_bias_data["favored_sector"]
            if favored_sector in heatmap:
                heatmap[favored_sector]["score"] += 300 

        # Pick the highest scoring reachable cell
        target_set = False
        p_target = pygame.Vector2(enemy_goal_pos)
        
        while not target_set and len(heatmap) > 0:
            best_sector = max(heatmap, key=lambda k: heatmap[k]["score"])
            best_cell_pos = heatmap[best_sector]["pos"]
            
            ai_dist = (best_cell_pos - ai_pos).length()
            opp_dist = (best_cell_pos - opponent_pos).length()
            
            # Can the AI reach it before the opponent?
            if ai_dist < opp_dist + 50:
                p_target = best_cell_pos
                target_set = True
            else:
                del heatmap[best_sector]
                
        return p_target

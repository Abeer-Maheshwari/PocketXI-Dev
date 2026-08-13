import os
import json

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
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_path = os.path.join(base_path, "data")
        os.makedirs(data_path, exist_ok=True)
        self.history_file = os.path.join(data_path, "ai_history.json")
        self.loadHistory()

    def loadHistory(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                    # Convert string keys back to int
                    loaded_history = {int(k): int(v) for k, v in data.items()}
                    self.SectorHistory = {i: max(0, loaded_history.get(i, 0)) for i in range(16)}
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
        self.SectorHistory[sector_id] = self.SectorHistory.get(sector_id, 0) + 1
        
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

import os
import json

class TeamLoader:
    # Parses JSON data to player attributes 
    def __init__(self, filepath="assets/teams.json"):
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.filepath = os.path.join(base_path, filepath)
        self.teams_data = {}
        self._loadAllTeams()

    def _loadAllTeams(self):
        # Load attributes from teams.json file
        try:
            with open(self.filepath, 'r') as file:
                self.teams_data = json.load(file)
                print(f"Loaded team data from {self.filepath}")
        except (OSError, json.JSONDecodeError) as e:
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
        default_stats = {
            "speed": 250, "sprint_speed": 380, "max_stamina": 100.0,
            "spin": 1.0, "strength": 1.0,
        }
        stats = self.teams_data.get(team_name, self.teams_data.get("default", default_stats))
        return stats.copy() if isinstance(stats, dict) else default_stats

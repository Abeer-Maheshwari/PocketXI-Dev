import os
import json


class TeamLoader:
    # Loads team stats from assets/teams.json
    def __init__(self, filepath="assets/teams.json"):
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.filepath = os.path.join(base_path, filepath)
        self.teams_data = {}
        self._loadAllTeams()

    def _loadAllTeams(self):
        try:
            with open(self.filepath, 'r') as file:
                self.teams_data = json.load(file)
        except (OSError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load team data ({e}). Using defaults.")
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
        default_stats = {
            "speed": 250, "sprint_speed": 380, "max_stamina": 100.0,
            "spin": 1.0, "strength": 1.0,
        }
        stats = self.teams_data.get(team_name, self.teams_data.get("default", default_stats))
        return stats.copy() if isinstance(stats, dict) else default_stats


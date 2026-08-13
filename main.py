import pygame
from src.launcher import GameLauncher
from src.ui import MenuSystem
from src.match import MatchController

if __name__ == "__main__":
    # Initialise backend
    launcher_backend = GameLauncher()
    # Initialise menu
    menu_system = MenuSystem(launcher_backend)
    
    while True:
        # Reset launch signal
        should_launch_match = False
        
        while not should_launch_match:
            menu_system.clock.tick(60)
            # Continuously monitor mouse and keyboard events
            signal = menu_system.processEvents()
            
            # Intercept launch match state
            if signal == "LAUNCH_MATCH":
                should_launch_match = True
                break
                
            # Draw active menu screen
            menu_system.renderDisplay()
            
        if should_launch_match:
            # Pass backend and menu system instances to prevent reliance on global state lookup
            game = MatchController(launcher_backend=launcher_backend, menu_system=menu_system)
            game.runMatchLoop()
            # After runMatchLoop finishes (e.g. via EXIT_TO_MENU), it loops back to menu_system.processEvents()
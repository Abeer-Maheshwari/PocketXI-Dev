import asyncio
import pygame
from src.launcher import GameLauncher
from src.ui import MenuSystem
from src.match import MatchController

async def main():
    launcher_backend = GameLauncher()
    menu_system = MenuSystem(launcher_backend)
    
    while True:
        should_launch_match = False
        
        # Menu Loop
        while not should_launch_match:
            menu_system.clock.tick(60)
            signal = menu_system.processEvents()
            
            if signal == "LAUNCH_MATCH":
                should_launch_match = True
                break
                
            menu_system.renderDisplay()
            await asyncio.sleep(0)  # Yield execution to Pyodide/browser
            
        if should_launch_match:
            game = MatchController(launcher_backend=launcher_backend, menu_system=menu_system)
            await game.runMatchLoop()  # Await the asynchronous match loop
            await asyncio.sleep(0)

if __name__ == "__main__":
    asyncio.run(main())
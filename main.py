import asyncio
import pygame
from src.launcher import GameLauncher
from src.ui import MenuSystem
from src.match import MatchController
from src.network import NetworkClient

# Configure the mixer before either the launcher or menu calls pygame.init().
# A larger buffer and the same 24 kHz stereo format as the web assets give SDL's
# WebAudio backend enough headroom on slower browsers.
pygame.mixer.pre_init(frequency=24000, size=-16, channels=2, buffer=2048)

async def main():
    launcher_backend = GameLauncher()
    network_client = NetworkClient("ws://152.67.155.250:8765")
    menu_system = MenuSystem(launcher_backend, network_client=network_client)   
    
    while True:
        launch_mode = None
        
        # Menu Loop
        while not launch_mode:
            menu_system.clock.tick(60)
            signal = await menu_system.processEvents()
            
            if signal == "LAUNCH_MATCH":
                launch_mode = "OFFLINE"
                break
            elif signal == "LAUNCH_ONLINE_MATCH":
                launch_mode = "ONLINE"
                break
                
            menu_system.renderDisplay()
            await asyncio.sleep(0)
            
        # Launch Match
        if launch_mode == "OFFLINE":
            game = MatchController(
                launcher_backend=launcher_backend, 
                menu_system=menu_system,
                is_online=False
            )
            await game.runMatchLoop()
        elif launch_mode == "ONLINE":
            game = MatchController(
                launcher_backend=launcher_backend, 
                menu_system=menu_system,
                network_client=network_client,
                is_online=True
            )
            await game.runMatchLoop()
            
        await asyncio.sleep(0)

if __name__ == "__main__":
    asyncio.run(main())

# main.py
import asyncio
import os
import sys
import pygame
from src.launcher import GameLauncher
from src.match import MatchController
from src.network import NetworkClient
from src.transition import TransitionManager
from src.ui import MenuSystem

IS_WASM = sys.platform in ("emscripten", "wasi")

pygame.mixer.pre_init(frequency=24000, size=-16, channels=2, buffer=2048)
os.environ["SDL_VIDEO_HIGHDPI_DISABLED"] = "0"


async def main():
    """Application entry point handling menu navigation and match launches."""
    launcher_backend = GameLauncher()
    network_client = NetworkClient("wss://photographs-river-various-observed.trycloudflare.com")
    menu_system = MenuSystem(launcher_backend, network_client=network_client)

    transition = TransitionManager(menu_system.screen)

    # Initial menu draw
    menu_system.renderDisplay()
    previous_menu_state = menu_system.current_state

    while True:
        launch_mode = None

        # Menu event loop
        while not launch_mode:
            if not IS_WASM:
                menu_system.clock.tick(60)

            signal = await menu_system.processEvents()

            if signal == "LAUNCH_MATCH":
                launch_mode = "OFFLINE"
                break
            elif signal == "LAUNCH_ONLINE_MATCH":
                launch_mode = "ONLINE"
                break

            # Crossfade transition between menu sub-screens
            if menu_system.current_state != previous_menu_state:
                snapshot_before = menu_system.screen.copy()

                # Render next state off-screen to snapshot target surface
                real_flip = pygame.display.flip
                real_update = pygame.display.update
                pygame.display.flip = lambda: None
                pygame.display.update = lambda *args, **kwargs: None
                try:
                    menu_system.renderDisplay()
                    snapshot_after = menu_system.screen.copy()
                finally:
                    pygame.display.flip = real_flip
                    pygame.display.update = real_update

                await transition.fade_between_surfaces(
                    snapshot_before,
                    snapshot_after,
                    duration=0.55,
                )
                previous_menu_state = menu_system.current_state
            else:
                menu_system.renderDisplay()

            await asyncio.sleep(0)

        # Fade out menu before entering match
        await transition.fade_out(duration=0.35)

        # Initialize and launch match
        if launch_mode == "ONLINE":
            await transition.show_loading(
                title="JOINING STADIUM...",
                subtitle=f"Room: {network_client.room_code or 'Public'} | Connecting relay",
                min_duration=0.7,
            )
            game = MatchController(
                launcher_backend=launcher_backend,
                menu_system=menu_system,
                network_client=network_client,
                is_online=True,
            )
        else:
            await transition.show_loading(
                title="LOADING MATCH...",
                subtitle="Initializing heuristic AI engine",
                min_duration=0.5,
            )
            game = MatchController(
                launcher_backend=launcher_backend,
                menu_system=menu_system,
                is_online=False,
            )

        # Run match until completion or return
        await game.runMatchLoop()

        # Fade out match upon exit
        await transition.fade_out(duration=0.35)

        # Reset menu state
        menu_system.current_state = "MAIN_HUB"
        previous_menu_state = "MAIN_HUB"
        if network_client:
            network_client.match_started = False
            network_client.room_code = None

        menu_system.renderDisplay()
        await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())
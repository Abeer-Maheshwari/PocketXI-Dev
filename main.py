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


async def main():
    # Main application loop connecting menus and matches
    launcher_backend = GameLauncher()
    network_client = NetworkClient("ws://152.67.155.250:8765")
    asyncio.create_task(network_client.connect())
    menu_system = MenuSystem(launcher_backend, network_client=network_client)

    transition = TransitionManager(menu_system.screen)

    menu_system.renderDisplay()
    previous_menu_state = menu_system.current_state

    while True:
        launch_mode = None

        # Menu navigation loop
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

            # Handle smooth fade transition between menu pages
            if previous_menu_state != menu_system.current_state:
                outgoing_state = previous_menu_state
                incoming_state = menu_system.current_state

                def draw_outgoing(execute_flip=False):
                    saved_state = menu_system.current_state
                    menu_system.current_state = outgoing_state
                    menu_system.renderDisplay(execute_flip=execute_flip)
                    menu_system.current_state = saved_state

                def draw_incoming(execute_flip=False):
                    menu_system.renderDisplay(execute_flip=execute_flip)

                await transition.fade_transition(draw_outgoing, draw_incoming, duration=0.2)
                previous_menu_state = menu_system.current_state

            menu_system.renderDisplay()
            await asyncio.sleep(0)

        # Transition into match
        await transition.fade_out(draw_current_fn=menu_system.renderDisplay, duration=0.2)

        if launch_mode == "ONLINE":
            await transition.show_loading(
                title="CONNECTING TO MATCH...",
                subtitle="Synchronizing with server",
                min_duration=0.4,
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
                subtitle="Setting up pitch and AI",
                min_duration=0.4,
            )
            game = MatchController(
                launcher_backend=launcher_backend,
                menu_system=menu_system,
                is_online=False,
            )

        # Run gameplay loop
        await game.runMatchLoop()

        # Fade out to return to menu
        await transition.fade_out(draw_current_fn=game.renderScene, duration=0.2)

        # Reset back to hub
        menu_system.current_state = "MAIN_HUB"
        previous_menu_state = "MAIN_HUB"
        if network_client:
            network_client.match_started = False
            network_client.room_code = None

        menu_system.renderDisplay()
        await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())
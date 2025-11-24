import os
import sys
import socket
import threading
import random
import tkinter as tk
from tkinter import messagebox
import ursina
from network import Network

from floor import Floor
from map import Map
from player import Player
from enemy import Enemy
from bullet import Bullet
from ursina import Button


def restart_game():
    # Relaunch the current script with the same interpreter.
    os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)])


def prompt_connection_details(default_username="player", default_ip="127.0.0.1", default_port="8000", error_text=""):
    """Tkinter modal to collect username, IP, and port with defaults."""
    result = {}
    root = tk.Tk()
    root.title("Ursina FPS - Connect")
    root.resizable(False, False)

    tk.Label(root, text="Username").grid(row=0, column=0, padx=10, pady=(10, 2), sticky="w")
    username_var = tk.StringVar(value=default_username)
    tk.Entry(root, textvariable=username_var, width=24).grid(row=0, column=1, padx=10, pady=(10, 2))

    tk.Label(root, text="Server IP").grid(row=1, column=0, padx=10, pady=2, sticky="w")
    ip_var = tk.StringVar(value=default_ip)
    tk.Entry(root, textvariable=ip_var, width=24).grid(row=1, column=1, padx=10, pady=2)

    tk.Label(root, text="Port").grid(row=2, column=0, padx=10, pady=2, sticky="w")
    port_var = tk.StringVar(value=default_port)
    tk.Entry(root, textvariable=port_var, width=24).grid(row=2, column=1, padx=10, pady=2)

    mode_var = tk.StringVar(value="join")
    tk.Label(root, text="Mode").grid(row=3, column=0, padx=10, pady=(4, 2), sticky="w")
    mode_frame = tk.Frame(root)
    mode_frame.grid(row=3, column=1, padx=10, pady=(4, 2), sticky="w")
    tk.Radiobutton(mode_frame, text="Join", variable=mode_var, value="join").pack(side="left")
    tk.Radiobutton(mode_frame, text="Host", variable=mode_var, value="host").pack(side="left")

    error_label = tk.Label(root, text=error_text, fg="red")
    if error_text:
        error_label.grid(row=3, column=0, columnspan=2, padx=10, pady=(4, 2))

    def submit():
        username = username_var.get().strip() or default_username
        ip = ip_var.get().strip() or default_ip
        port_str = port_var.get().strip() or default_port
        try:
            port_num = int(port_str)
        except ValueError:
            error_label.config(text="Port must be a number.")
            error_label.grid(row=3, column=0, columnspan=2, padx=10, pady=(4, 2))
            return
        result["username"] = username
        result["ip"] = ip
        result["port"] = port_num
        result["mode"] = mode_var.get()
        root.destroy()

    def cancel():
        root.destroy()
        sys.exit(0)

    tk.Button(root, text="Connect", command=submit, width=12).grid(row=4, column=0, padx=10, pady=10, sticky="e")
    tk.Button(root, text="Quit", command=cancel, width=12).grid(row=4, column=1, padx=10, pady=10, sticky="w")
    root.bind("<Return>", lambda event: submit())
    root.protocol("WM_DELETE_WINDOW", cancel)

    # Center the window
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"{w}x{h}+{x}+{y}")

    root.mainloop()
    return result


def get_network():
    username = "player"
    server_addr = "127.0.0.1"
    server_port = 8000
    while True:
        details = prompt_connection_details(username, server_addr, str(server_port))
        username = details.get("username", username)
        server_addr = details.get("ip", server_addr)
        server_port = details.get("port", server_port)
        mode = details.get("mode", "join")

        n = Network(server_addr, server_port, username)
        n.settimeout(5)
        error_message = ""

        try:
            n.connect()
        except ConnectionRefusedError:
            error_message = "Connection refused. Is the server running?"
        except socket.timeout:
            error_message = "Server timed out. Try again."
        except socket.gaierror:
            error_message = "Invalid IP address."
        finally:
            n.settimeout(None)

        if not error_message:
            return n, username

        # Show error and retry via GUI
        messagebox.showerror("Connection error", error_message)


n, username = get_network()

app = ursina.Ursina()
ursina.window.borderless = False
ursina.window.title = "Ursina FPS"
ursina.window.exit_button.visible = False
ursina.window.vsync = False

floor = Floor()
map = Map()
sky = ursina.Entity(
    model="sphere",
    texture=os.path.join("assets", "sky.png"),
    scale=9999,
    double_sided=True
)
spawn_pos = ursina.Vec3(random.randint(-30, 30), 1, random.randint(-30, 30))
player = Player(spawn_pos)
prev_pos = player.world_position
prev_dir = player.world_rotation_y
enemies = []
paused = False
pause_ui = None


def random_spawn(seed=None):
    rng = random.Random()
    if seed is not None:
        rng.seed(seed)
    return ursina.Vec3(rng.randint(-30, 30), 1, rng.randint(-30, 30))


def restart_round(seed=None, is_local=False):
    global paused, prev_pos, prev_dir

    if seed is None:
        seed = random.randint(1, 1_000_000)
    # Deterministic per-player spawn using seed and player id to reduce overlap.
    per_player_seed = f"{seed}-{n.id}"
    spawn = random_spawn(per_player_seed)

    player.respawn(spawn)
    prev_pos = player.world_position
    prev_dir = player.world_rotation_y

    for e in enemies:
        e.health = 100

    hide_pause()

    # Inform server/others when triggered locally.
    if is_local:
        n.send_restart(seed)
        n.send_player(player)


def receive():
    while True:
        try:
            info = n.receive_info()
        except Exception as e:
            print(e)
            continue

        if not info:
            print("Server has stopped! Exiting...")
            sys.exit()

        if info["object"] == "player":
            enemy_id = info["id"]

            if info["joined"]:
                new_enemy = Enemy(ursina.Vec3(*info["position"]), enemy_id, info["username"])
                new_enemy.health = info["health"]
                enemies.append(new_enemy)
                continue

            enemy = None

            for e in enemies:
                if e.id == enemy_id:
                    enemy = e
                    break

            if not enemy:
                continue

            if info["left"]:
                enemies.remove(enemy)
                ursina.destroy(enemy)
                continue

            enemy.world_position = ursina.Vec3(*info["position"])
            enemy.rotation_y = info["rotation"]

        elif info["object"] == "bullet":
            b_pos = ursina.Vec3(*info["position"])
            b_dir = info["direction"]
            b_x_dir = info["x_direction"]
            b_damage = info["damage"]
            new_bullet = Bullet(b_pos, b_dir, b_x_dir, n, b_damage, slave=True)

        elif info["object"] == "health_update":
            enemy_id = info["id"]

            enemy = None

            if enemy_id == n.id:
                enemy = player
            else:
                for e in enemies:
                    if e.id == enemy_id:
                        enemy = e
                        break

            if not enemy:
                continue

            enemy.health = info["health"]
        elif info["object"] == "restart":
            restart_round(seed=info.get("seed"), is_local=False)


def show_pause():
    global paused
    if hasattr(player, "set_aim"):
        player.set_aim(False)
    paused = True
    ursina.application.paused = True
    ursina.mouse.locked = False
    if pause_ui:
        pause_ui.enabled = True


def hide_pause():
    global paused
    paused = False
    ursina.application.paused = False
    ursina.mouse.locked = True
    if pause_ui:
        pause_ui.enabled = False


def toggle_pause():
    if paused:
        hide_pause()
    else:
        show_pause()


def update():
    if player.health > 0:
        global prev_pos, prev_dir

        if prev_pos != player.world_position or prev_dir != player.world_rotation_y:
            n.send_player(player)

        prev_pos = player.world_position
        prev_dir = player.world_rotation_y


def input(key):
    if key == "escape":
        toggle_pause()
        return

    if paused:
        return

    if key == "right mouse down" and player.health > 0:
        player.set_aim(True)
        return
    if key == "right mouse up":
        player.set_aim(False)
        return

    if key == "r":
        player.start_reload()
        return

    if key == "left mouse down" and player.can_fire():
        b_pos = player.position + ursina.Vec3(0, 2, 0)
        bullet = Bullet(b_pos, player.world_rotation_y, -player.camera_pivot.world_rotation_x, n)
        n.send_bullet(bullet)
        player.consume_ammo()
        player.play_shoot_sound()


def main():
    global pause_ui
    pause_ui = ursina.Entity(parent=ursina.camera.ui, enabled=False)

    overlay = ursina.Entity(
        parent=pause_ui,
        model="quad",
        scale=2,
        color=ursina.color.Color(0, 0, 0, 0.6)
    )

    panel = ursina.Entity(parent=pause_ui, model="quad", scale=ursina.Vec2(0.6, 0.4), color=ursina.color.Color(0.1, 0.1, 0.1, 0.9))
    ursina.Text(parent=panel, text="Paused", origin=(0, 0), y=0.12, scale=2)

    Button(parent=panel, text="Resume", scale=ursina.Vec2(0.4, 0.08), y=0.06, on_click=hide_pause)
    Button(parent=panel, text="Restart", scale=ursina.Vec2(0.4, 0.08), y=-0.02, color=ursina.color.Color(0.2, 0.4, 0.8, 1), on_click=lambda: restart_round(is_local=True))
    Button(parent=panel, text="Quit", scale=ursina.Vec2(0.4, 0.08), y=-0.10, color=ursina.color.Color(0.5, 0.1, 0.1, 1), on_click=ursina.application.quit)

    msg_thread = threading.Thread(target=receive, daemon=True)
    msg_thread.start()
    app.run()


if __name__ == "__main__":
    main()

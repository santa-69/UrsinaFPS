import os
import sys
import socket
import subprocess
import threading
import time
import random
import tkinter as tk
from tkinter import messagebox
import queue
import ursina
from network import Network

from floor import Floor
from map import Map
from player import Player
from enemy import Enemy
from bullet import Bullet
from ursina import Button, invoke


server_process = None
incoming_events = queue.SimpleQueue()
server_stopped = False
connected_players = set()
game_mode = "ffa"
tdm_kill_limit = 25
team_scores = {"red": 0, "blue": 0}
score_ui = None
tdm_victory_announced = False
victory_ui = None
player_team_choice = None
lobby_scroll_container = None


def restart_game():
    # Relaunch the current script with the same interpreter.
    os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)])


def ensure_server_running(port: int) -> bool:
    """Start the bundled server if it is not already running."""
    global server_process
    server_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server", "main.py"))
    server_cwd = os.path.dirname(server_script)

    if server_process and server_process.poll() is None:
        return True

    try:
        server_process = subprocess.Popen([sys.executable, server_script], cwd=server_cwd)
    except OSError as exc:
        messagebox.showerror("Server error", f"Could not start server: {exc}")
        server_process = None
        return False

    # Wait briefly for the server to bind its socket.
    deadline = time.time() + 3
    while time.time() < deadline:
        if server_process.poll() is not None:
            messagebox.showerror("Server error", "Server process exited unexpectedly.")
            server_process = None
            return False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except OSError:
            time.sleep(0.1)

    messagebox.showerror("Server error", "Timed out waiting for the server to start.")
    return False


def assign_team(player_id) -> str:
    """Deterministic team assignment based on player id for TDM."""
    try:
        pid = int(player_id)
    except Exception:
        pid = 0
    return "blue" if pid % 2 == 0 else "red"


def prompt_connection_details(default_username="player", default_ip="127.0.0.1", default_port="8000", error_text=""):
    """Tkinter modal to collect username, IP, and port with defaults."""
    result = {}

    def detect_host_ip(default="127.0.0.1"):
        """Find a likely LAN IP by opening a dummy socket."""
        try:
            tmp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            tmp.connect(("8.8.8.8", 80))
            ip = tmp.getsockname()[0]
        except Exception:
            ip = default
        finally:
            try:
                tmp.close()
            except Exception:
                pass
        return ip

    root = tk.Tk()
    root.title("Ursina FPS - Connect")
    root.geometry("360x200")
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

    host_ip_text = tk.StringVar(value="")
    host_ip_label = tk.Label(root, textvariable=host_ip_text, fg="blue")

    error_label = tk.Label(root, text=error_text, fg="red")
    if error_text:
        error_label.grid(row=3, column=0, columnspan=2, padx=10, pady=(4, 2))

    def update_host_hint():
        if mode_var.get() == "host":
            ip_to_share = detect_host_ip(default_ip)
            port_to_share = port_var.get().strip() or default_port
            host_ip_text.set(f"Share this IP: {ip_to_share}:{port_to_share}")
            host_ip_label.grid(row=4, column=0, columnspan=2, padx=10, pady=(2, 2))
        else:
            host_ip_text.set("")
            host_ip_label.grid_remove()

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

    tk.Button(root, text="Connect", command=submit, width=12).grid(row=5, column=0, padx=10, pady=10, sticky="e")
    tk.Button(root, text="Quit", command=cancel, width=12).grid(row=5, column=1, padx=10, pady=10, sticky="w")
    root.bind("<Return>", lambda event: submit())
    root.protocol("WM_DELETE_WINDOW", cancel)
    port_var.trace_add("write", lambda *args: update_host_hint())
    mode_var.trace_add("write", lambda *args: update_host_hint())
    update_host_hint()

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

        if mode == "host" and not ensure_server_running(server_port):
            continue

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
            return n, username, server_addr, server_port

        # Show error and retry via GUI
        messagebox.showerror("Connection error", error_message)


n, username, selected_server_addr, selected_server_port = get_network()
player_team_choice = assign_team(n.id)
connected_players.add(n.id)
player_team = player_team_choice

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
spawn_pos = ursina.Vec3(random.randint(-60, 60), 1, random.randint(-60, 60))
player = Player(spawn_pos)
try:
    player.set_team(player_team)
except Exception:
    player.team = player_team
prev_pos = player.world_position
prev_dir = player.world_rotation_y
enemies = []
paused = False
pause_ui = None
lobby_ui = None
lobby_player_count_text = None
in_lobby = True
score_ui = ursina.Text(parent=ursina.camera.ui, text="", origin=(0, 0), position=ursina.Vec2(0, 0.47), scale=1.2, color=ursina.color.white)
lobby_scroll_container = None


def random_spawn(seed=None):
    rng = random.Random()
    if seed is not None:
        rng.seed(seed)
    return ursina.Vec3(rng.randint(-60, 60), 1, rng.randint(-60, 60))

def restart_round(seed=None, is_local=False):
    global paused, prev_pos, prev_dir, team_scores

    if seed is None:
        seed = random.randint(1, 1_000_000)
    # Deterministic per-player spawn using seed and player id to reduce overlap.
    per_player_seed = f"{seed}-{n.id}"
    spawn = random_spawn(per_player_seed)

    player.respawn(spawn)
    try:
        player._scored_death = False
    except Exception:
        pass
    prev_pos = player.world_position
    prev_dir = player.world_rotation_y
    team_scores = {"red": 0, "blue": 0}
    update_score_ui()

    for e in enemies:
        e.health = 100
        try:
            e.reset_state()
            e.collider = "box"
            e.collision = True
        except Exception:
            # If reset_state not available or failed, fall back to enabling.
            e.enabled = True
            e.visible = True
            try:
                e.collider = "box"
                e.collision = True
            except Exception:
                pass

    hide_pause()

    # Inform server/others when triggered locally.
    if is_local:
        n.send_restart(seed)
        n.send_player(player)


def update_lobby_status_text():
    if lobby_player_count_text:
        lobby_player_count_text.text = f"Players connected: {len(connected_players)}"


def clear_victory_ui():
    global victory_ui
    if victory_ui:
        try:
            ursina.destroy(victory_ui)
        except Exception:
            pass
    victory_ui = None


def update_score_ui():
    if not score_ui:
        return
    if game_mode != "tdm":
        score_ui.text = ""
        return
    red = team_scores.get("red", 0)
    blue = team_scores.get("blue", 0)
    score_ui.text = f"Red {red}  -  {blue} Blue"


def set_player_team(team: str):
    global player_team_choice
    player_team_choice = team
    try:
        player.set_team(team)
    except Exception:
        player.team = team
    update_score_ui()


def check_tdm_victory():
    global tdm_victory_announced
    if tdm_victory_announced or game_mode != "tdm":
        return
    if team_scores.get("red", 0) >= tdm_kill_limit:
        tdm_victory_announced = True
        show_victory("red")
    elif team_scores.get("blue", 0) >= tdm_kill_limit:
        tdm_victory_announced = True
        show_victory("blue")


def show_victory(winning_team: str):
    """Display win/lose splash and return to lobby after a short delay."""
    global victory_ui
    clear_victory_ui()
    overlay = ursina.Entity(parent=ursina.camera.ui, model="quad", scale=2, color=ursina.color.Color(0, 0, 0, 0.7))
    message = "Match Over"
    color = ursina.color.white
    if hasattr(player, "team"):
        if player.team == winning_team:
            message = "You Win!"
            color = ursina.color.lime
        else:
            message = "You Lose"
            color = ursina.color.red
    text = ursina.Text(parent=overlay, text=message, origin=(0, 0), scale=3, color=color)
    victory_ui = overlay
    def finish():
        clear_victory_ui()
        team_scores["red"] = 0
        team_scores["blue"] = 0
        update_score_ui()
        show_lobby()
    invoke(finish, delay=3)


def receive():
    while True:
        try:
            info = n.receive_info()
        except Exception as e:
            print(e)
            continue

        if not info:
            incoming_events.put({"object": "server_stopped"})
            break

        incoming_events.put(info)


def handle_info(info):
    global server_stopped, tdm_victory_announced

    if info["object"] == "player":
        enemy_id = info["id"]

        if info["joined"]:
            new_enemy = Enemy(ursina.Vec3(*info["position"]), enemy_id, info["username"])
            new_enemy.health = info["health"]
            new_enemy.team = assign_team(enemy_id)
            enemies.append(new_enemy)
            connected_players.add(enemy_id)
            update_lobby_status_text()
            return

        enemy = None

        for e in enemies:
            if e.id == enemy_id:
                enemy = e
                break

        if not enemy:
            return

        if info["left"]:
            enemies.remove(enemy)
            ursina.destroy(enemy)
            if enemy_id in connected_players:
                connected_players.discard(enemy_id)
                update_lobby_status_text()
            return

        enemy.world_position = ursina.Vec3(*info["position"])
        enemy.rotation_y = info["rotation"]

    elif info["object"] == "bullet":
        b_pos = ursina.Vec3(*info["position"])
        b_dir = info["direction"]
        b_x_dir = info["x_direction"]
        b_damage = info["damage"]
        b_speed = info.get("speed", 80.0)
        Bullet(b_pos, b_dir, b_x_dir, n, b_damage, slave=True, speed=b_speed)
        try:
            player.play_shoot_sound_at(b_pos)
        except Exception:
            pass

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
            return

        was_dead = enemy.health <= 0
        enemy.health = info["health"]
        if enemy.health > 0 and was_dead:
            if hasattr(enemy, "reset_state"):
                enemy.reset_state()
            else:
                enemy.enabled = True
                enemy.visible = True
                try:
                    enemy.collider = "box"
                    enemy.collision = True
                except Exception:
                    pass
        elif enemy.health <= 0:
            if game_mode == "tdm" and getattr(enemy, "team", None):
                if enemy.team == "red":
                    team_scores["blue"] = team_scores.get("blue", 0) + 1
                elif enemy.team == "blue":
                    team_scores["red"] = team_scores.get("red", 0) + 1
                update_score_ui()
                check_tdm_victory()
            try:
                if hasattr(enemy, "die"):
                    enemy.die()
                elif hasattr(enemy, "death"):
                    enemy.death()
            except Exception:
                pass
    elif info["object"] == "restart":
        restart_round(seed=info.get("seed"), is_local=False)
    elif info["object"] == "server_stopped":
        server_stopped = True
        print("Server has stopped! Exiting...")
        ursina.application.quit()


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


def set_healthbar_visible(visible: bool):
    try:
        player.healthbar.enabled = visible
        player.healthbar_bg.enabled = visible
    except Exception:
        pass


def start_game():
    global in_lobby, prev_pos, prev_dir, game_mode, tdm_victory_announced
    if lobby_ui:
        lobby_ui.enabled = False
    in_lobby = False
    try:
        player.enabled = True
        prev_pos = player.world_position
        prev_dir = player.world_rotation_y
        n.send_player(player)
    except Exception:
        pass
    if game_mode == "tdm":
        team_scores["red"] = 0
        team_scores["blue"] = 0
    update_score_ui()
    tdm_victory_announced = False
    clear_victory_ui()
    ursina.mouse.locked = True
    set_healthbar_visible(True)


def show_lobby():
    """Return to lobby UI from pause menu."""
    global in_lobby, paused, tdm_victory_announced
    if lobby_ui:
        lobby_ui.enabled = True
    else:
        build_lobby_ui()
    in_lobby = True
    paused = False
    tdm_victory_announced = False
    ursina.application.paused = False
    try:
        if hasattr(player, "set_aim"):
            player.set_aim(False)
        player.trigger_held = False
        player.enabled = False
    except Exception:
        pass
    ursina.mouse.locked = False
    if pause_ui:
        pause_ui.enabled = False
    set_healthbar_visible(False)


def build_lobby_ui():
    global lobby_ui, lobby_player_count_text, connected_players, in_lobby, game_mode, tdm_kill_limit, lobby_scroll_container
    lobby_ui = ursina.Entity(parent=ursina.camera.ui, enabled=True)
    overlay = ursina.Entity(
        parent=lobby_ui,
        model="quad",
        scale=2,
        color=ursina.color.Color(0, 0, 0, 0.65)
    )
    panel = ursina.Entity(parent=lobby_ui, model="quad", scale=ursina.Vec2(1.05, 1.2), color=ursina.color.Color(0.1, 0.1, 0.1, 0.92))
    scroll_frame = ursina.Entity(parent=panel, model=None, position=ursina.Vec3(0, 0.0, -0.01))
    lobby_scroll_container = ursina.Entity(parent=scroll_frame, model=None, position=ursina.Vec3(0, -0.12, 0))
    ursina.Text(parent=lobby_scroll_container, text="Lobby", origin=(0, 0), y=0.42, scale=2)
    ursina.Text(parent=lobby_scroll_container, text=f"Server: {selected_server_addr}:{selected_server_port}", origin=(0, 0), y=0.30, scale=1.2)
    ursina.Text(parent=lobby_scroll_container, text=f"Username: {username}", origin=(0, 0), y=0.22, scale=1)
    lobby_player_count_text = ursina.Text(parent=lobby_scroll_container, text="Players connected: 1", origin=(0, 0), y=0.14, scale=1.1)
    Button(parent=lobby_scroll_container, text="Start Game", scale=ursina.Vec2(0.35, 0.09), y=0.04, color=ursina.color.Color(0.2, 0.6, 0.2, 1), on_click=start_game)
    ursina.Text(parent=lobby_scroll_container, text="Wait here until everyone joins, then start.", origin=(0, 0), y=-0.06, scale=0.9, color=ursina.color.light_gray)

    # Game mode selector
    mode_label = ursina.Text(parent=lobby_scroll_container, text=f"Mode: {'Team Deathmatch' if game_mode == 'tdm' else 'Free For All'}", origin=(0, 0), y=-0.14, scale=1.0)

    def set_mode(mode_key):
        nonlocal mode_label
        mode_label.text = f"Mode: {'Team Deathmatch' if mode_key == 'tdm' else 'Free For All'}"
        globals()["game_mode"] = mode_key
        if mode_key == "tdm":
            globals()["team_scores"] = {"red": 0, "blue": 0}
        update_score_ui()

    Button(parent=lobby_scroll_container, text="Free For All", scale=ursina.Vec2(0.22, 0.07), position=ursina.Vec2(-0.18, -0.20), on_click=lambda: set_mode("ffa"))
    Button(parent=lobby_scroll_container, text="Team Deathmatch", scale=ursina.Vec2(0.26, 0.07), position=ursina.Vec2(0.20, -0.20), on_click=lambda: set_mode("tdm"))

    # Team selection
    ursina.Text(parent=lobby_scroll_container, text="Choose Team (TDM)", origin=(0, 0), y=-0.30, scale=0.9)
    team_buttons = []

    def update_team_buttons(selected):
        for name, btn in team_buttons:
            if name == "red":
                btn.color = ursina.color.rgb(0.8, 0.1, 0.1) if selected == "red" else ursina.color.gray
            elif name == "blue":
                btn.color = ursina.color.rgb(0.1, 0.4, 0.9) if selected == "blue" else ursina.color.gray

    red_btn = Button(parent=lobby_scroll_container, text="Red", scale=ursina.Vec2(0.18, 0.07), position=ursina.Vec2(-0.12, -0.36), on_click=lambda: (set_player_team("red"), update_team_buttons("red")))
    blue_btn = Button(parent=lobby_scroll_container, text="Blue", scale=ursina.Vec2(0.18, 0.07), position=ursina.Vec2(0.12, -0.36), on_click=lambda: (set_player_team("blue"), update_team_buttons("blue")))
    team_buttons.append(("red", red_btn))
    team_buttons.append(("blue", blue_btn))
    update_team_buttons(player_team_choice or "red")

    # TDM options
    tdm_label = ursina.Text(parent=lobby_scroll_container, text=f"TDM Kill Limit: {tdm_kill_limit}", origin=(0, 0), y=-0.48, scale=0.9, color=ursina.color.azure)

    def adjust_kill_limit(delta):
        nonlocal tdm_label
        globals()["tdm_kill_limit"] = max(5, min(200, globals()["tdm_kill_limit"] + delta))
        tdm_label.text = f"TDM Kill Limit: {globals()['tdm_kill_limit']}"

    Button(parent=lobby_scroll_container, text="-", scale=ursina.Vec2(0.07, 0.07), position=ursina.Vec2(-0.18, -0.54), on_click=lambda: adjust_kill_limit(-5))
    Button(parent=lobby_scroll_container, text="+", scale=ursina.Vec2(0.07, 0.07), position=ursina.Vec2(-0.07, -0.54), on_click=lambda: adjust_kill_limit(5))

    # Spacer (bots removed)
    ursina.Text(parent=lobby_scroll_container, text="", origin=(0, 0), y=-0.62, scale=0.9, color=ursina.color.white)
    # Scroll handling
    def scroll_lobby(amount):
        lobby_scroll_container.y = max(-0.8, min(0.2, lobby_scroll_container.y + amount * 0.05))
    scroll_lobby(0)

    # Initialize mode state.
    set_mode(game_mode)
    set_healthbar_visible(False)
    clear_victory_ui()
    in_lobby = True
    try:
        player.enabled = False
    except Exception:
        pass
    ursina.mouse.locked = False
    update_lobby_status_text()
    update_score_ui()


def fire_player_bullet():
    if not player.can_fire():
        return
    try:
        b_pos = player.get_muzzle_world_position()
    except Exception:
        b_pos = player.position + ursina.Vec3(0, 2, 0)

    damage = player.get_bullet_damage()
    bullet_speed = getattr(player, "get_bullet_speed", lambda: 80.0)()
    shooter_team = player.get_team() if hasattr(player, "get_team") and game_mode == "tdm" else None
    bullet = Bullet(b_pos, player.world_rotation_y, -player.camera_pivot.world_rotation_x, n, damage=damage, speed=bullet_speed, shooter_team=shooter_team)
    n.send_bullet(bullet)
    player.record_shot()
    player.play_shoot_sound()
    if shooter_team and game_mode == "tdm":
        update_score_ui()
        check_tdm_victory()


def update():
    while not incoming_events.empty():
        try:
            info = incoming_events.get_nowait()
        except Exception:
            break
        handle_info(info)

    if in_lobby:
        return

    if player.health > 0:
        global prev_pos, prev_dir

        if not paused and player.trigger_held and getattr(player, "auto_fire", False) and player.can_fire():
            fire_player_bullet()

        if prev_pos != player.world_position or prev_dir != player.world_rotation_y:
            n.send_player(player)

        prev_pos = player.world_position
        prev_dir = player.world_rotation_y
    else:
        # Credit opposing team on local death in TDM once.
        if game_mode == "tdm" and hasattr(player, "team") and getattr(player, "_death_started", False) and not getattr(player, "_scored_death", False):
            if player.team == "red":
                team_scores["blue"] = team_scores.get("blue", 0) + 1
            elif player.team == "blue":
                team_scores["red"] = team_scores.get("red", 0) + 1
            player._scored_death = True
            update_score_ui()
            check_tdm_victory()


def input(key):
    if in_lobby:
        if key == "scroll up":
            try:
                lobby_scroll_container.y = max(-0.8, min(0.2, lobby_scroll_container.y + 0.05))
            except Exception:
                pass
        elif key == "scroll down":
            try:
                lobby_scroll_container.y = max(-0.8, min(0.2, lobby_scroll_container.y - 0.05))
            except Exception:
                pass
        return

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

    if key == "left mouse down":
        player.trigger_held = True
        fire_player_bullet()
        return
    if key == "left mouse up":
        player.trigger_held = False


def main():
    global pause_ui
    pause_ui = ursina.Entity(parent=ursina.camera.ui, enabled=False)

    overlay = ursina.Entity(
        parent=pause_ui,
        model="quad",
        scale=2,
        color=ursina.color.Color(0, 0, 0, 0.6)
    )

    panel = ursina.Entity(parent=pause_ui, model="quad", scale=ursina.Vec2(0.7, 0.55), color=ursina.color.Color(0.1, 0.1, 0.1, 0.9))
    ursina.Text(parent=panel, text="Paused", origin=(0, 0), y=0.18, scale=2)

    Button(parent=panel, text="Resume", scale=ursina.Vec2(0.4, 0.08), y=0.12, on_click=hide_pause)
    Button(parent=panel, text="Restart", scale=ursina.Vec2(0.4, 0.08), y=0.02, color=ursina.color.Color(0.2, 0.4, 0.8, 1), on_click=lambda: restart_round(is_local=True))
    Button(parent=panel, text="Lobby", scale=ursina.Vec2(0.4, 0.08), y=-0.08, color=ursina.color.Color(0.2, 0.5, 0.2, 1), on_click=show_lobby)
    Button(parent=panel, text="Quit", scale=ursina.Vec2(0.4, 0.08), y=-0.18, color=ursina.color.Color(0.5, 0.1, 0.1, 1), on_click=ursina.application.quit)

    # Weapon class selector
    ursina.Text(parent=panel, text="Weapon Class", origin=(0, 0), y=-0.16, scale=1.2)
    weapon_buttons = []

    def update_weapon_buttons(selected):
        for name, btn in weapon_buttons:
            btn.color = ursina.color.azure if name == selected else ursina.color.gray

    def select_weapon_class(name):
        try:
            player.apply_weapon_class(name)
        except Exception:
            return
        update_weapon_buttons(name)

    button_specs = [("pistol", "Pistol"), ("rifle", "Rifle"), ("sniper", "Sniper")]
    x_positions = (-0.22, 0, 0.22)
    for (key, label), x in zip(button_specs, x_positions):
        btn = Button(parent=panel, text=label, scale=ursina.Vec2(0.18, 0.07), position=ursina.Vec2(x, -0.26), on_click=lambda k=key: select_weapon_class(k))
        weapon_buttons.append((key, btn))

    update_weapon_buttons(player.weapon_class)
    build_lobby_ui()
    clear_victory_ui()

    msg_thread = threading.Thread(target=receive, daemon=True)
    msg_thread.start()
    app.run()


if __name__ == "__main__":
    main()

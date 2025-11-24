import ursina
from ursina.prefabs.first_person_controller import FirstPersonController


class Player(FirstPersonController):
    def __init__(self, position: ursina.Vec3):
        super().__init__(
            position=position,
            model="cube",
            jump_height=2.5,
            jump_duration=0.4,
            origin_y=-2,
            collider="box",
            speed=7
        )
        self.cursor.color = ursina.color.rgb(255, 0, 0, 122)
        self.base_speed = 7
        self.sprint_speed = 12
        self.speed = self.base_speed
        self.base_fov = ursina.camera.fov
        self.aim_fov = 70
        self.base_mouse_sensitivity = ursina.Vec2(self.mouse_sensitivity)
        self.aim_mouse_sensitivity = self.base_mouse_sensitivity * 0.6
        self.aiming = False
        self._aim_pos_anim = None
        self._aim_rot_anim = None
        self.reload_sound_path = "assets/pistolreload.wav"
        self.reload_volume = 0.5
        self.reload_sound = None
        self.shoot_sound_path = "assets/audiomass-output.wav"
        self.shoot_volume = 0.4
        self.shoot_sound = None
        self.run_sound_path = "assets/running.wav"
        self.run_volume = 0.3
        self.run_sound = None
        self.jump_sound_path = "assets/jump-land.wav"
        self.jump_volume = 0.4
        self.jump_sound = None
        self.mag_size = 12
        self.ammo = self.mag_size
        self.reload_time = 2.3
        self.reloading = False
        self._reload_timer = 0

        self.gun_default_pos = ursina.Vec2(0.6, -0.45)
        self.gun_aim_pos = ursina.Vec2(0.0, -0.3)
        self.gun_default_rot = ursina.Vec3(-20, -20, -5)
        self.gun_aim_rot = ursina.Vec3(-10, 0, 0)
        self.gun = self._create_gun()

        self.healthbar_pos = ursina.Vec2(0, 0.45)
        self.healthbar_size = ursina.Vec2(0.8, 0.04)
        self.healthbar_bg = ursina.Entity(
            parent=ursina.camera.ui,
            model="quad",
            color=ursina.color.rgb(255, 0, 0),
            # place background slightly behind the foreground bar (z offset)
            position=ursina.Vec3(self.healthbar_pos.x, self.healthbar_pos.y, 0),
            scale=self.healthbar_size
        )
        self.healthbar = ursina.Entity(
            parent=ursina.camera.ui,
            model="quad",
            color=ursina.color.rgb(0, 255, 0),
            # put the filling slightly in front (small negative z) to avoid z-fighting
            position=ursina.Vec3(self.healthbar_pos.x, self.healthbar_pos.y, -0.01),
            scale=self.healthbar_size
        )

        # Limit how close the player can get to outer walls to avoid sticking.
        self.move_bounds = 43
        self.health = 100
        self.death_message_shown = False
        self.ammo_text = ursina.Text(
            parent=ursina.camera.ui,
            text="",
            origin=ursina.Vec2(0.5, 0.5),
            position=ursina.Vec2(0.45, -0.45),
            scale=1.2
        )
        self._update_ammo_ui()

    def _gun_is_valid(self):
        return getattr(self, "gun", None) is not None and not getattr(self.gun, "is_destroyed", False)

    def set_aim(self, value: bool):
        self.aiming = value
        if not self._gun_is_valid():
            try:
                self.gun = self._create_gun()
            except Exception:
                return
        if value:
            ursina.camera.fov = self.aim_fov
            self.mouse_sensitivity = ursina.Vec2(self.aim_mouse_sensitivity)
            if self._aim_pos_anim and hasattr(self._aim_pos_anim, "kill"):
                self._aim_pos_anim.kill()
            if self._aim_rot_anim and hasattr(self._aim_rot_anim, "kill"):
                self._aim_rot_anim.kill()
            self._aim_pos_anim = self.gun.animate_position(self.gun_aim_pos, duration=0.1, curve=ursina.curve.linear)
            self._aim_rot_anim = self.gun.animate_rotation(self.gun_aim_rot, duration=0.1, curve=ursina.curve.linear)
        else:
            ursina.camera.fov = self.base_fov
            self.mouse_sensitivity = ursina.Vec2(self.base_mouse_sensitivity)
            if self._aim_pos_anim and hasattr(self._aim_pos_anim, "kill"):
                self._aim_pos_anim.kill()
            if self._aim_rot_anim and hasattr(self._aim_rot_anim, "kill"):
                self._aim_rot_anim.kill()
            self._aim_pos_anim = self.gun.animate_position(self.gun_default_pos, duration=0.1, curve=ursina.curve.linear)
            self._aim_rot_anim = self.gun.animate_rotation(self.gun_default_rot, duration=0.1, curve=ursina.curve.linear)

    def _create_gun(self):
        return ursina.Entity(
            parent=ursina.camera.ui,
            position=self.gun_default_pos,
            scale=ursina.Vec3(0.1, 0.2, 0.65),
            rotation=self.gun_default_rot,
            model="cube",
            texture="white_cube",
            color=ursina.color.hsv(0, 0, 0.4)
        )

    def _update_ammo_ui(self):
        status = "Reloading..." if self.reloading else f"{self.ammo}/{self.mag_size}"
        self.ammo_text.text = status
        self.ammo_text.color = ursina.color.orange if self.reloading else ursina.color.white

    def start_reload(self):
        if self.reloading or self.ammo == self.mag_size:
            return
        self.reloading = True
        self._reload_timer = self.reload_time
        try:
            if self.reload_sound:
                self.reload_sound.stop()
            self.reload_sound = ursina.Audio(self.reload_sound_path, autoplay=True, loop=False, volume=self.reload_volume)
        except Exception:
            pass
        self._update_ammo_ui()

    def play_run_sound(self):
        try:
            if self.run_sound and self.run_sound.playing:
                return
            self.run_sound = ursina.Audio(self.run_sound_path, autoplay=True, loop=True, volume=self.run_volume)
        except Exception:
            pass

    def stop_run_sound(self):
        try:
            if self.run_sound:
                self.run_sound.stop()
        except Exception:
            pass

    def consume_ammo(self):
        if self.reloading or self.ammo <= 0:
            return False
        self.ammo -= 1
        if self.ammo <= 0:
            self.start_reload()
        self._update_ammo_ui()
        return True

    def can_fire(self):
        return self.health > 0 and not self.reloading and self.ammo > 0

    def jump(self):
        # Play jump-land sound when initiating jump; let base handle movement.
        try:
            self.jump_sound = ursina.Audio(self.jump_sound_path, autoplay=True, loop=False, volume=self.jump_volume)
        except Exception:
            pass
        super().jump()

    def play_shoot_sound(self):
        try:
            sound = ursina.Audio(self.shoot_sound_path, autoplay=True, loop=False, volume=self.shoot_volume)
            # allow overlapping; clean up after a short delay
            ursina.destroy(sound, delay=2)
        except Exception:
            pass

    def play_shoot_sound_at(self, source_pos: ursina.Vec3):
        """Play gunshot with simple distance attenuation."""
        try:
            listener_pos = ursina.Vec3(self.world_position)
            distance = (listener_pos - source_pos).length()
            max_hear_distance = 60.0
            attenuation = max(0.0, 1.0 - distance / max_hear_distance)
            if attenuation <= 0:
                return
            volume = self.shoot_volume * attenuation
            # Keep a small floor to avoid going fully silent due to timing jitter.
            volume = max(0.05, volume)
            sound = ursina.Audio(self.shoot_sound_path, autoplay=True, loop=False, volume=volume)
            ursina.destroy(sound, delay=2)
        except Exception:
            pass

    def respawn(self, spawn_pos: ursina.Vec3):
        # Restore gun if it was destroyed on death.
        if not getattr(self, "gun", None) or getattr(self.gun, "is_destroyed", False):
            self.gun = self._create_gun()
        else:
            self.gun.enabled = True

        self.set_aim(False)
        self.health = 100
        self.death_message_shown = False
        self.rotation = 0
        self.camera_pivot.rotation_x = 0
        self.world_position = spawn_pos
        self.cursor.color = ursina.color.rgb(255, 0, 0, 122)
        self.ammo = self.mag_size
        self.reloading = False
        self._reload_timer = 0
        self._update_ammo_ui()
        self.stop_run_sound()
        # Clear any death text on respawn.
        for t in tuple(ursina.scene.entities):
            if isinstance(t, ursina.Text) and getattr(t, "text", "") == "You are dead!":
                ursina.destroy(t)

    def death(self):
        self.death_message_shown = True

        if self._gun_is_valid():
            self.gun.enabled = False
        self.stop_run_sound()
        self.rotation = 0
        self.camera_pivot.world_rotation_x = -45
        self.world_position = ursina.Vec3(0, 7, -35)
        self.cursor.color = ursina.color.rgb(0, 0, 0, a=0)

        ursina.Text(
            text="You are dead!",
            origin=ursina.Vec2(0, 0),
            scale=3
        )

    def update(self):
        # Calculate new width for the health fill (in UI units)
        new_width = (self.health / 100) * self.healthbar_size.x
        # Update scale.x for the filled bar
        self.healthbar.scale_x = new_width
        # Keep the left edge stationary by shifting the bar's center when its width changes.
        # When scaled from center, the center moves by half the difference; compensate for that.
        self.healthbar.position = ursina.Vec3(
            self.healthbar_pos.x - (self.healthbar_size.x - new_width) / 2,
            self.healthbar_pos.y,
            -0.01
        )

        if self.health <= 0:
            if self.aiming:
                self.set_aim(False)
            self.stop_run_sound()
            if not self.death_message_shown:
                self.death()
        else:
            # Hold shift to sprint.
            sprinting = bool(ursina.held_keys.get("shift") or ursina.held_keys.get("left shift"))
            self.speed = self.sprint_speed if sprinting else self.base_speed
            # play/stop running sound depending on movement
            moving = sprinting or any(ursina.held_keys.get(k, 0) for k in ("w", "a", "s", "d"))
            if moving:
                self.play_run_sound()
            else:
                self.stop_run_sound()
            if self.reloading:
                self._reload_timer -= ursina.time.dt
                if self._reload_timer <= 0:
                    self.reloading = False
                    self.ammo = self.mag_size
                self._update_ammo_ui()
            super().update()
            # Clamp position to stay off the walls a bit.
            self.x = max(-self.move_bounds, min(self.move_bounds, self.x))
            self.z = max(-self.move_bounds, min(self.move_bounds, self.z))

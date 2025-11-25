import ursina


class Enemy(ursina.Entity):
    def __init__(self, position: ursina.Vec3, identifier: str, username: str):
        super().__init__(
            position=position,
            model="capsule",
            origin_y=-0.9,
            texture="white_cube",
            color=ursina.color.red,
            scale=ursina.Vec3(1.0, 2.2, 1.0)
        )
        self.base_scale = ursina.Vec3(1.0, 2.2, 1.0)
        self.base_rotation = ursina.Vec3(self.rotation)
        self.gun_color = ursina.color.hsv(0, 0, 0.35)

        self.body_parts = []
        self._build_humanoid()

        self.name_tag = ursina.Text(
            parent=self,
            text=username,
            position=ursina.Vec3(0, 1.3, 0),
            scale=ursina.Vec2(5, 3),
            billboard=True,
            origin=ursina.Vec2(0, 0)
        )

        self.health = 100
        self.id = identifier
        self.username = username
        self._death_started = False
        self.team = getattr(self, "team", None)

    def _build_humanoid(self):
        """Create a simple humanoid silhouette using primitives."""
        base_color = ursina.color.red if getattr(self, "team", None) != "blue" else ursina.color.azure

        torso = ursina.Entity(
            parent=self,
            model="cube",
            position=ursina.Vec3(0, 0.1, 0),
            scale=ursina.Vec3(0.8, 0.9, 0.5),
            color=base_color,
            collider=None,
            collision=False
        )
        head = ursina.Entity(
            parent=self,
            model="sphere",
            position=ursina.Vec3(0, 0.82, 0),
            scale=ursina.Vec3(0.45, 0.5, 0.45),
            color=ursina.color.rgb(230, 210, 190),
            collider="sphere",
            collision=True,
            name="head"
        )
        left_arm = ursina.Entity(
            parent=self,
            model="cube",
            position=ursina.Vec3(-0.55, 0.1, 0),
            scale=ursina.Vec3(0.25, 0.9, 0.25),
            color=base_color,
            collider=None,
            collision=False
        )
        right_arm = ursina.Entity(
            parent=self,
            model="cube",
            position=ursina.Vec3(0.55, 0.1, 0),
            scale=ursina.Vec3(0.25, 0.9, 0.25),
            color=base_color,
            collider=None,
            collision=False
        )
        left_leg = ursina.Entity(
            parent=self,
            model="cube",
            position=ursina.Vec3(-0.25, -0.75, 0),
            scale=ursina.Vec3(0.3, 0.9, 0.3),
            color=base_color * 0.8,
            collider=None,
            collision=False
        )
        right_leg = ursina.Entity(
            parent=self,
            model="cube",
            position=ursina.Vec3(0.25, -0.75, 0),
            scale=ursina.Vec3(0.3, 0.9, 0.3),
            color=base_color * 0.8,
            collider=None,
            collision=False
        )

        self.gun = ursina.Entity(
            parent=self,
            position=ursina.Vec3(0.55, 0.2, 0.5),
            scale=ursina.Vec3(0.1, 0.15, 0.65),
            model="cube",
            texture="white_cube",
            color=self.gun_color,
            collider=None,
            collision=False
        )

        self.body_parts = [torso, head, left_arm, right_arm, left_leg, right_leg, self.gun]
        # Body collider covers torso/legs; head uses its own sphere collider for headshot detection.
        self.collider = ursina.BoxCollider(self, center=ursina.Vec3(0, -0.1, 0), size=ursina.Vec3(1.1, 1.95, 1.1))

    def update(self):
        if hasattr(self, "is_empty") and self.is_empty():
            return
        try:
            color_value = max(0.2, self.health / 100)
        except AttributeError:
            self.health = 100
            color_value = max(0.2, self.health / 100)

        hue = 0
        if getattr(self, "team", None) == "blue":
            hue = 220
        new_color = ursina.color.hsv(hue, 1, color_value)

        if self.health <= 0:
            if not self._death_started:
                self.die()
            return

        self._death_started = False
        self.color = new_color
        for part in getattr(self, "body_parts", []):
            try:
                if part is self.gun:
                    part.color = self.gun_color
                else:
                    part.color = new_color
            except Exception:
                pass

    def die(self):
        """Play a quick fall-over animation before disabling."""
        self._death_started = True
        try:
            fall_rot = ursina.Vec3(self.rotation_x + 90, self.rotation_y, self.rotation_z + 10)
            self.animate_rotation(fall_rot, duration=0.45, curve=ursina.curve.in_quad)
            self.animate_position(self.position + ursina.Vec3(0, -0.6, 0), duration=0.45, curve=ursina.curve.in_quad)
            self.animate_color(ursina.color.rgb(80, 0, 0), duration=0.45, curve=ursina.curve.out_expo)
        except Exception:
            # If animation fails, fall back to instant hide.
            self._finish_death()
            return
        ursina.invoke(self._finish_death, delay=0.5)

    def _finish_death(self):
        self.enabled = False
        self.collision = False
        self.visible = False

    def reset_state(self):
        """Restore default appearance and state after being revived."""
        self._death_started = False
        self.scale = ursina.Vec3(self.base_scale)
        self.rotation = ursina.Vec3(self.base_rotation)
        self.enabled = True
        self.visible = True
        self.collision = True
        base_color = ursina.color.red if getattr(self, "team", None) != "blue" else ursina.color.azure
        self.color = base_color
        for part in getattr(self, "body_parts", []):
            try:
                if part is self.gun:
                    part.color = self.gun_color
                else:
                    part.color = base_color
            except Exception:
                pass

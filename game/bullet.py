import random
import ursina

from enemy import Enemy
from collision_data import STATIC_AABBS


class Bullet(ursina.Entity):
    def __init__(self, position: ursina.Vec3, direction: float, x_direction: float, network, damage: int = random.randint(5, 20), slave=False, speed: float = 80.0, shooter_team=None):
        self.speed = speed
        self.shooter_team = shooter_team
        dir_rad = ursina.math.radians(direction)
        x_dir_rad = ursina.math.radians(x_direction)

        self.velocity = ursina.Vec3(
            ursina.math.sin(dir_rad) * ursina.math.cos(x_dir_rad),
            ursina.math.sin(x_dir_rad),
            ursina.math.cos(dir_rad) * ursina.math.cos(x_dir_rad)
        ) * self.speed

        super().__init__(
            position=position + self.velocity / speed,
            model="sphere",
            collider=None,  # collision handled via explicit raycasts
            scale=0.2
        )

        self.damage = damage
        self.direction = direction
        self.x_direction = x_direction
        self.slave = slave
        self.network = network

        # Cache static AABB list reference to avoid repeated imports.
        self._static_boxes = STATIC_AABBS
        # Safety: also consider floor boxes.
        try:
            from collision_data import FLOOR_AABBS
            self._static_boxes = self._static_boxes + FLOOR_AABBS
        except Exception:
            pass

        self._life = 0.0

    def _spawn_hit_effect(self, point):
        # Quick sparkle at the impact point.
        fx = ursina.Entity(
            position=point,
            model="sphere",
            scale=0.50,
            # Colors in Ursina expect 0-1 floats; this is an orangy red with some alpha.
            color=ursina.color.Color(1.0, 0.47, 0.16, 0.86),
            collider=None
        )
        fx.animate_scale(0.01, duration=0.2)
        fx.animate_color(ursina.color.Color(1.0, 0.47, 0.16, 0.0), duration=0.2)
        ursina.destroy(fx, delay=0.25)

    def update(self):
        if getattr(self, "_dead", False):
            return
        if hasattr(self, "is_empty") and self.is_empty():
            return

        step = self.velocity * ursina.time.dt
        if step.length() == 0:
            return

        prev_pos = ursina.Vec3(self.world_position)
        new_pos = prev_pos + step

        # Manual segment-vs-AABB sweep to avoid Panda3D collider crashes.
        def segment_hits_box(p0, p1, center, size, padding=0.0):
            # Slab method for segment/AABB intersection.
            pad = ursina.Vec3(padding, padding, padding)
            min_b = center - size * 0.5 - pad
            max_b = center + size * 0.5 + pad
            direction = p1 - p0
            tmin, tmax = 0.0, 1.0
            for axis in ("x", "y", "z"):
                d = getattr(direction, axis)
                o = getattr(p0, axis)
                mn = getattr(min_b, axis)
                mx = getattr(max_b, axis)
                if abs(d) < 1e-8:
                    if o < mn or o > mx:
                        return None
                    continue
                inv_d = 1.0 / d
                t1 = (mn - o) * inv_d
                t2 = (mx - o) * inv_d
                if t1 > t2:
                    t1, t2 = t2, t1
                tmin = max(tmin, t1)
                tmax = min(tmax, t2)
                if tmin > tmax:
                    return None
            return tmin if 0.0 <= tmin <= 1.0 else None

        hit_entity = None
        hit_point = None
        bullet_radius = 0.1

        # Use engine raycast for collisions; avoid destroying the hit entity.
        hit = ursina.raycast(
            origin=prev_pos,
            direction=step.normalized(),
            distance=step.length(),
            ignore=(self,),
            traverse_target=ursina.scene
        )

        if hit.hit:
            hit_entity = getattr(hit, "entity", None)
            target_enemy = None
            headshot = False

            if isinstance(hit_entity, Enemy):
                target_enemy = hit_entity
            elif hasattr(hit_entity, "parent") and isinstance(hit_entity.parent, Enemy):
                target_enemy = hit_entity.parent
                headshot = getattr(hit_entity, "name", "") == "head"

            # Fallback: infer headshots by impact height so we don't depend solely on the head collider.
            if target_enemy and hasattr(hit, "world_point") and hit.world_point is not None:
                if getattr(hit_entity, "name", "") == "head":
                    headshot = True
                else:
                    # Approx head center scales with enemy size; head is placed ~0.82 units above origin in model space.
                    head_height = target_enemy.world_y + 0.82 * getattr(target_enemy, "scale_y", 1)
                    if hit.world_point.y >= head_height - 0.15:
                        headshot = True

            if not self.slave and target_enemy:
                if self.shooter_team and getattr(target_enemy, "team", None) == self.shooter_team:
                    return
                damage = self.damage * (2 if headshot else 1)
                target_enemy.health -= damage
                if self.network:
                    self.network.send_health(target_enemy)
            if hasattr(hit, "world_point") and hit.world_point is not None:
                impact_point = hit.world_point
                self.position = impact_point
                self._spawn_hit_effect(impact_point)
            self._dead = True
            self.enabled = False
            self.visible = False
            return

        self.position = new_pos

        # Lifetime cleanup (replaces external delayed destroys)
        self._life += ursina.time.dt
        if self._life >= 2:
            self._dead = True
            self.enabled = False
            self.visible = False
            return

        # Despawn if we leave the play area
        if abs(self.world_x) > 140 or abs(self.world_z) > 140 or self.world_y < -5 or self.world_y > 100:
            self._dead = True
            self.enabled = False
            self.visible = False
            return

        # If nothing hit, keep moving and avoid further processing.
        return

import os
import ursina
from ursina import Vec3
from collision_data import STATIC_AABBS


class Wall(ursina.Entity):
    def __init__(self, position, size=Vec3(2, 2, 2)):
        super().__init__(
            position=position,
            scale=size,
            model="cube",
            texture=os.path.join("assets", "wall.png"),
            origin_y=0  # keep pivot at center; we position to sit on floor
        )
        self.texture.filtering = None
        # Use auto-sized collider to match the visual wall.
        self.collider = "box"
        # Track static AABB for manual bullet collisions (avoid Panda3D collider issues).
        STATIC_AABBS.append({
            "center": ursina.Vec3(*position),
            "size": ursina.Vec3(*size),
        })


class Map:
    def __init__(self):
        def wall_segment(center: Vec3, size: Vec3):
            # Centered segment; y is at half height so it rests on the floor.
            Wall(center, size=size)

        # Perimeter walls using large segments (fewer entities).
        half = 45
        height = 6
        thickness = 1.0  # thinner perimeter to reduce snagging
        wall_segment(Vec3(0, height / 2, -half), Vec3(2 * half + thickness, height, thickness))  # North
        wall_segment(Vec3(0, height / 2, half), Vec3(2 * half + thickness, height, thickness))   # South
        wall_segment(Vec3(-half, height / 2, 0), Vec3(thickness, height, 2 * half + thickness))  # West
        wall_segment(Vec3(half, height / 2, 0), Vec3(thickness, height, 2 * half + thickness))   # East

        # Buildings / cover blocks as larger chunks (reduce draw calls).
        wall_segment(Vec3(-10, 3, -10), Vec3(12, 6, 1))   # north wall of building 1
        wall_segment(Vec3(-10, 3, 0), Vec3(12, 6, 1))     # south wall of building 1
        wall_segment(Vec3(-16, 3, -5), Vec3(1, 6, 10))    # west wall of building 1
        wall_segment(Vec3(-4, 3, -5), Vec3(1, 6, 10))     # east wall of building 1

        wall_segment(Vec3(18, 2.5, -14), Vec3(16, 5, 1))  # building 2 north
        wall_segment(Vec3(18, 2.5, -6), Vec3(16, 5, 1))   # building 2 south
        wall_segment(Vec3(10, 2.5, -10), Vec3(1, 5, 8))   # building 2 west
        wall_segment(Vec3(26, 2.5, -10), Vec3(1, 5, 8))   # building 2 east

        wall_segment(Vec3(-28, 4, 14), Vec3(10, 8, 1))    # tall tower north
        wall_segment(Vec3(-28, 4, 22), Vec3(10, 8, 1))    # tall tower south
        wall_segment(Vec3(-33, 4, 18), Vec3(1, 8, 8))     # tall tower west
        wall_segment(Vec3(-23, 4, 18), Vec3(1, 8, 8))     # tall tower east

        wall_segment(Vec3(16, 3, 16), Vec3(12, 6, 1))     # courtyard north
        wall_segment(Vec3(16, 3, 24), Vec3(12, 6, 1))     # courtyard south
        wall_segment(Vec3(10, 3, 20), Vec3(1, 6, 8))      # courtyard west
        wall_segment(Vec3(22, 3, 20), Vec3(1, 6, 8))      # courtyard east

        wall_segment(Vec3(-4, 2.5, 24), Vec3(10, 5, 1))   # hut north
        wall_segment(Vec3(-4, 2.5, 30), Vec3(10, 5, 1))   # hut south
        wall_segment(Vec3(-8, 2.5, 27), Vec3(1, 5, 6))    # hut west
        wall_segment(Vec3(0, 2.5, 27), Vec3(1, 5, 6))     # hut east

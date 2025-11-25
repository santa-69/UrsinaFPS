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
        floor_thickness = 0.25

        def wall_segment(center: Vec3, size: Vec3):
            # Centered segment; y is at half height so it rests on the floor.
            Wall(center, size=size)

        def building(center: Vec3, size: Vec3, height: float, door_side="south", door_width=4.0):
            """Create a hollow building with a doorway opening."""
            cx, cz = center.x, center.z
            half_w = size.x / 2
            half_d = size.z / 2
            h = height
            t = 1.0

            def doorway_segments(side: str):
                dw = min(door_width, max(2.0, min(size.x, size.z) - 1.0))
                if side == "south":
                    z = cz + half_d
                    span = size.x
                    left_w = (span - dw) / 2
                    right_w = left_w
                    wall_segment(Vec3(cx - (dw / 2 + left_w / 2), h / 2, z), Vec3(left_w, h, t))
                    wall_segment(Vec3(cx + (dw / 2 + right_w / 2), h / 2, z), Vec3(right_w, h, t))
                elif side == "north":
                    z = cz - half_d
                    span = size.x
                    left_w = (span - dw) / 2
                    right_w = left_w
                    wall_segment(Vec3(cx - (dw / 2 + left_w / 2), h / 2, z), Vec3(left_w, h, t))
                    wall_segment(Vec3(cx + (dw / 2 + right_w / 2), h / 2, z), Vec3(right_w, h, t))
                elif side == "east":
                    x = cx + half_w
                    span = size.z
                    top_w = (span - dw) / 2
                    bottom_w = top_w
                    wall_segment(Vec3(x, h / 2, cz - (dw / 2 + top_w / 2)), Vec3(t, h, top_w))
                    wall_segment(Vec3(x, h / 2, cz + (dw / 2 + bottom_w / 2)), Vec3(t, h, bottom_w))
                elif side == "west":
                    x = cx - half_w
                    span = size.z
                    top_w = (span - dw) / 2
                    bottom_w = top_w
                    wall_segment(Vec3(x, h / 2, cz - (dw / 2 + top_w / 2)), Vec3(t, h, top_w))
                    wall_segment(Vec3(x, h / 2, cz + (dw / 2 + bottom_w / 2)), Vec3(t, h, bottom_w))

            # North/South with doorway on door_side
            if door_side == "south":
                doorway_segments("south")
                wall_segment(Vec3(cx, h / 2, cz - half_d), Vec3(size.x, h, t))
                wall_segment(Vec3(cx - half_w, h / 2, cz), Vec3(t, h, size.z))
                wall_segment(Vec3(cx + half_w, h / 2, cz), Vec3(t, h, size.z))
            elif door_side == "north":
                doorway_segments("north")
                wall_segment(Vec3(cx, h / 2, cz + half_d), Vec3(size.x, h, t))
                wall_segment(Vec3(cx - half_w, h / 2, cz), Vec3(t, h, size.z))
                wall_segment(Vec3(cx + half_w, h / 2, cz), Vec3(t, h, size.z))
            elif door_side == "east":
                doorway_segments("east")
                wall_segment(Vec3(cx - half_w, h / 2, cz), Vec3(t, h, size.z))
                wall_segment(Vec3(cx, h / 2, cz - half_d), Vec3(size.x, h, t))
                wall_segment(Vec3(cx, h / 2, cz + half_d), Vec3(size.x, h, t))
            else:
                doorway_segments("west")
                wall_segment(Vec3(cx + half_w, h / 2, cz), Vec3(t, h, size.z))
                wall_segment(Vec3(cx, h / 2, cz - half_d), Vec3(size.x, h, t))
                wall_segment(Vec3(cx, h / 2, cz + half_d), Vec3(size.x, h, t))

        def floor_plate(center: Vec3, size: Vec3):
            """Simple walkable floor inside multi-story buildings."""
            Wall(center, size=Vec3(size.x, floor_thickness, size.z))

        # Perimeter walls using large segments (fewer entities).
        half = 75
        height = 7
        thickness = 1.0
        wall_segment(Vec3(0, height / 2, -half), Vec3(2 * half + thickness, height, thickness))  # North
        wall_segment(Vec3(0, height / 2, half), Vec3(2 * half + thickness, height, thickness))   # South
        wall_segment(Vec3(-half, height / 2, 0), Vec3(thickness, height, 2 * half + thickness))  # West
        wall_segment(Vec3(half, height / 2, 0), Vec3(thickness, height, 2 * half + thickness))   # East

        # District 1: warehouse with interior pillars and doorway.
        building(Vec3(-25, 0, -20), Vec3(24, 18, 14), height=6, door_side="south", door_width=4)
        wall_segment(Vec3(-25, 3, -20), Vec3(2, 6, 2))  # center pillar
        wall_segment(Vec3(-31, 3, -24), Vec3(2, 6, 2))
        wall_segment(Vec3(-19, 3, -24), Vec3(2, 6, 2))
        wall_segment(Vec3(-31, 3, -16), Vec3(2, 6, 2))
        wall_segment(Vec3(-19, 3, -16), Vec3(2, 6, 2))

        # District 2: L-shaped offices with two entrances.
        building(Vec3(22, 0, -28), Vec3(22, 16, 12), height=6, door_side="east", door_width=5)
        building(Vec3(22, 0, -12), Vec3(22, 10, 10), height=6, door_side="south", door_width=4)
        wall_segment(Vec3(22, 3, -20), Vec3(1, 6, 14))  # interior divider
        wall_segment(Vec3(16, 3, -12), Vec3(10, 6, 1))  # interior divider horizontal
        # Add a second floor in offices.
        floor_plate(Vec3(22, 3.1, -20), Vec3(22, 16, 12))
        floor_plate(Vec3(22, 3.1, -12), Vec3(22, 10, 10))

        # District 3: central plaza with cover and two small huts.
        wall_segment(Vec3(0, 2, 0), Vec3(8, 4, 1))
        wall_segment(Vec3(0, 2, 6), Vec3(6, 4, 1))
        wall_segment(Vec3(-6, 2, 3), Vec3(1, 4, 6))
        wall_segment(Vec3(6, 2, 3), Vec3(1, 4, 6))
        building(Vec3(-10, 0, 16), Vec3(10, 8, 8), height=5, door_side="east", door_width=3)
        building(Vec3(10, 0, 16), Vec3(10, 8, 8), height=5, door_side="west", door_width=3)

        # District 4: long apartment block with two doorways and interior halls.
        building(Vec3(-35, 0, 28), Vec3(28, 12, 12), height=6, door_side="south", door_width=6)
        building(Vec3(-35, 0, 44), Vec3(28, 12, 12), height=6, door_side="north", door_width=6)
        wall_segment(Vec3(-35, 3, 36), Vec3(1, 6, 24))   # central divider connecting both halves
        wall_segment(Vec3(-43, 3, 36), Vec3(4, 6, 1))    # cross halls
        wall_segment(Vec3(-27, 3, 36), Vec3(4, 6, 1))
        # Add second floor slabs in apartment block.
        floor_plate(Vec3(-35, 3.1, 28), Vec3(28, 12, 12))
        floor_plate(Vec3(-35, 3.1, 44), Vec3(28, 12, 12))

        # District 5: tall tower with accessible base and upper floors.
        building(Vec3(40, 0, 26), Vec3(12, 12, 12), height=10, door_side="west", door_width=4)
        floor_plate(Vec3(40, 3.3, 26), Vec3(12, 12, 12))  # 2nd floor
        floor_plate(Vec3(40, 6.6, 26), Vec3(12, 12, 12))  # 3rd floor
        wall_segment(Vec3(40, 6, 26), Vec3(6, 4, 6))  # interior core for extra cover

        # Outskirts cover blocks and alleys.
        wall_segment(Vec3(55, 3, -40), Vec3(10, 6, 1))
        wall_segment(Vec3(55, 3, -32), Vec3(10, 6, 1))
        wall_segment(Vec3(50, 3, -36), Vec3(1, 6, 8))

        wall_segment(Vec3(-55, 3, -40), Vec3(12, 6, 1))
        wall_segment(Vec3(-50, 3, -32), Vec3(1, 6, 12))
        wall_segment(Vec3(-60, 3, -32), Vec3(1, 6, 12))

        wall_segment(Vec3(50, 2.5, 50), Vec3(10, 5, 1))
        wall_segment(Vec3(50, 2.5, 58), Vec3(10, 5, 1))
        wall_segment(Vec3(45, 2.5, 54), Vec3(1, 5, 8))
        wall_segment(Vec3(55, 2.5, 54), Vec3(1, 5, 8))

import os
import ursina


class Floor:
    def __init__(self):
        # Single large plane instead of thousands of cubes to keep FPS high.
        size = 160  # larger play space for expanded map
        self.entity = ursina.Entity(
            position=ursina.Vec3(0, 0, 0),
            model="plane",
            scale=ursina.Vec3(size, 1, size),
            texture=os.path.join("assets", "floor.png"),
            origin_y=0
        )
        self.entity.texture.filtering = None
        self.entity.texture_scale = (size, size)
        # Explicit box collider to ensure the player stands on the floor.
        self.entity.collider = ursina.BoxCollider(self.entity, center=ursina.Vec3(0, -0.5, 0), size=ursina.Vec3(size, 1, size))

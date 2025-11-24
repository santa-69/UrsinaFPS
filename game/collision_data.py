"""
Shared collision data for simple manual checks that avoid Panda3D collider crashes.
"""

# List of dicts: {"center": ursina.Vec3, "size": ursina.Vec3}
STATIC_AABBS = []

# Floor AABB entries populated by floor generation.
FLOOR_AABBS = []

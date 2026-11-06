"""Physical constants of the tag design (millimetres).

The layer plan, thickness and zip-tie slot are fixed; only the footprint scales.
"""

# --- fixed (never scaled) ---
LAYER_BODY = 0.20          # body layer height
LAYER_TOP = 0.08           # layer height of the text zone
Z_SWITCH = 2.80            # 14 x 0.20: layer height drops to LAYER_TOP here
TEXT_DEPTH = 0.64          # 8 x 0.08: orange inlay depth
THICKNESS = Z_SWITCH + TEXT_DEPTH   # 3.44 mm total tag height
ZIP_SECTION = 14.0         # length of the zip-tie end
SLOT_X0, SLOT_X1 = 4.0, 10.0        # zip-tie slot span along X (6 mm)
SLOT_Z0, SLOT_Z1 = 0.60, 2.60       # zip-tie slot span along Z (2 mm)

# --- baseline footprint at 100 % size ---
BASE_WIDTH = 16.0          # tag width (Y)
BASE_LABEL_LENGTH = 58.0   # length of the text end (X)
BASE_CAP_HEIGHT = 7.0      # default text cap height

# --- text placement ---
MARGIN_X = 4.0             # clear space at each end of the text zone
MARGIN_Y = 1.5             # minimum clear space above/below the text ink
WALL = 2.0                 # text is clipped this far from the tag edge
TRACKING_EM = 0.03         # extra letter spacing (fraction of cap height)
AUTO_MIN_PCT = 30.0        # auto-fit never shrinks text below this
MANUAL_MIN_PCT, MANUAL_MAX_PCT = 20.0, 150.0
LEGIBLE_CAP_MM = 3.0       # warn when cap height is below this
CLEAN_RADIUS = 0.12        # outline cleanup (close then open) radius
CURVE_STEPS = 10           # line segments per quadratic curve

# --- size slider ---
SIZE_MIN_PCT, SIZE_MAX_PCT, SIZE_DEFAULT_PCT = 50, 150, 100
MAX_TAGS = 40

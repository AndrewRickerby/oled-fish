import argparse
import json
import math
import os
import platform
import random
import sys
import time
import urllib.error
import urllib.request


# ===================== CUSTOMISABLE SETTINGS =====================

# Size of the OLED screen in pixels. 128x40 matches SteelSeries keyboards/headsets.
# Only change this if your device has a different sized screen.
SCREEN_WIDTH = 128
SCREEN_HEIGHT = 40

# How many frames are drawn per second. Higher = smoother and faster motion.
# Example: 30 makes the animation twice as smooth as 15. Can also be set with --fps.
DEFAULT_FRAMES_PER_SECOND = 15

# True shows the swaying seaweed at the bottom, False hides it.
SHOW_SEAWEED = True
# True shows the sand line along the bottom of the screen, False hides it.
SHOW_SAND = True
# Chance (0.0 to 1.0) that the fish blows a bubble each frame.
# Example: 0.0 = no bubbles, 0.06 = an occasional bubble, 0.5 = lots of bubbles.
BUBBLE_CHANCE_PER_FRAME = 0.06

# Internal ID used by SteelSeries GG. Uppercase letters, numbers, _ and - only.
GAMESENSE_GAME_NAME = "FISH_TANK"
# Name of the event that each animation frame is sent as. No need to change it.
GAMESENSE_EVENT_NAME = "FRAME"
# The name shown for this app inside the SteelSeries GG Engine "Apps" list.
GAMESENSE_DISPLAY_NAME = "Fish Tank"
# The developer name shown next to the app in SteelSeries GG.
GAMESENSE_DEVELOPER = "Andrew"


# The fish that take turns swimming across the screen. Add, remove or edit entries.
#   name              - shown under the tank in --preview mode
#   body_length       - width of the body in pixels (bigger = longer fish)
#   body_height       - height of the body in pixels (bigger = taller fish)
#   tail_length       - how far the tail sticks out behind the body
#   tail_spread       - how tall the tail is; 4 or more gives a forked tail
#   dorsal_fin_height - height of the fin on top (0 = no top fin)
#   bottom_fin_height - height of the fin underneath (0 = no bottom fin)
#   stripe_count      - number of vertical stripes on the body (0 = plain)
#   has_spikes        - True adds pufferfish spikes around the body
#   speed             - pixels moved per frame (1.0 = normal, 0.5 = slow, 2.0 = fast)
# Example: a new tiny fast fish could be
#   {"name": "Minnow", "body_length": 10, "body_height": 6, "tail_length": 4,
#    "tail_spread": 3, "dorsal_fin_height": 2, "bottom_fin_height": 0,
#    "stripe_count": 0, "has_spikes": False, "speed": 2.0},
FISH_SPECIES = [
    {
        "name": "Classic",
        "body_length": 18, "body_height": 10,
        "tail_length": 7, "tail_spread": 5,
        "dorsal_fin_height": 3, "bottom_fin_height": 0,
        "stripe_count": 0, "has_spikes": False,
        "speed": 1.0,
    },
    {
        "name": "Clownfish",
        "body_length": 20, "body_height": 11,
        "tail_length": 6, "tail_spread": 5,
        "dorsal_fin_height": 4, "bottom_fin_height": 0,
        "stripe_count": 2, "has_spikes": False,
        "speed": 0.8,
    },
    {
        "name": "Angelfish",
        "body_length": 14, "body_height": 14,
        "tail_length": 5, "tail_spread": 4,
        "dorsal_fin_height": 6, "bottom_fin_height": 5,
        "stripe_count": 3, "has_spikes": False,
        "speed": 0.6,
    },
    {
        "name": "Pufferfish",
        "body_length": 16, "body_height": 14,
        "tail_length": 4, "tail_spread": 3,
        "dorsal_fin_height": 0, "bottom_fin_height": 0,
        "stripe_count": 0, "has_spikes": True,
        "speed": 0.5,
    },
    {
        "name": "Long fish",
        "body_length": 30, "body_height": 7,
        "tail_length": 5, "tail_spread": 3,
        "dorsal_fin_height": 2, "bottom_fin_height": 0,
        "stripe_count": 0, "has_spikes": False,
        "speed": 1.4,
    },
]


def create_blank_canvas():
    return [[0] * SCREEN_WIDTH for _ in range(SCREEN_HEIGHT)]


def set_pixel(canvas, pixel_x, pixel_y, pixel_value=1):
    pixel_x = int(round(pixel_x))
    pixel_y = int(round(pixel_y))
    if 0 <= pixel_x < SCREEN_WIDTH and 0 <= pixel_y < SCREEN_HEIGHT:
        canvas[pixel_y][pixel_x] = pixel_value


def draw_line(canvas, start_x, start_y, end_x, end_y, pixel_value=1):
    start_x, start_y = int(round(start_x)), int(round(start_y))
    end_x, end_y = int(round(end_x)), int(round(end_y))
    delta_x = abs(end_x - start_x)
    delta_y = -abs(end_y - start_y)
    step_x = 1 if start_x < end_x else -1
    step_y = 1 if start_y < end_y else -1
    error = delta_x + delta_y
    current_x, current_y = start_x, start_y
    while True:
        set_pixel(canvas, current_x, current_y, pixel_value)
        if current_x == end_x and current_y == end_y:
            break
        doubled_error = 2 * error
        if doubled_error >= delta_y:
            error += delta_y
            current_x += step_x
        if doubled_error <= delta_x:
            error += delta_x
            current_y += step_y


def draw_filled_triangle(canvas, point_a, point_b, point_c, pixel_value=1):
    min_x = int(math.floor(min(point_a[0], point_b[0], point_c[0])))
    max_x = int(math.ceil(max(point_a[0], point_b[0], point_c[0])))
    min_y = int(math.floor(min(point_a[1], point_b[1], point_c[1])))
    max_y = int(math.ceil(max(point_a[1], point_b[1], point_c[1])))

    def edge_side(edge_start, edge_end, test_x, test_y):
        return ((edge_end[0] - edge_start[0]) * (test_y - edge_start[1])
                - (edge_end[1] - edge_start[1]) * (test_x - edge_start[0]))

    for pixel_y in range(min_y, max_y + 1):
        for pixel_x in range(min_x, max_x + 1):
            side_ab = edge_side(point_a, point_b, pixel_x, pixel_y)
            side_bc = edge_side(point_b, point_c, pixel_x, pixel_y)
            side_ca = edge_side(point_c, point_a, pixel_x, pixel_y)
            all_non_negative = side_ab >= 0 and side_bc >= 0 and side_ca >= 0
            all_non_positive = side_ab <= 0 and side_bc <= 0 and side_ca <= 0
            if all_non_negative or all_non_positive:
                set_pixel(canvas, pixel_x, pixel_y, pixel_value)
    draw_line(canvas, *point_a, *point_b, pixel_value)
    draw_line(canvas, *point_b, *point_c, pixel_value)
    draw_line(canvas, *point_c, *point_a, pixel_value)


def draw_fish(canvas, species, center_x, center_y, facing_direction, animation_time):
    center_x = int(round(center_x))
    center_y = int(round(center_y))
    body_radius_x = species["body_length"] / 2
    body_radius_y = species["body_height"] / 2

    def to_screen(local_x, local_y):
        return (center_x + facing_direction * local_x, center_y + local_y)

    tail_swing_speed = 6.0 + species["speed"] * 4.0
    tail_swing_amount = math.sin(animation_time * tail_swing_speed)
    fin_flap_amount = math.sin(animation_time * tail_swing_speed * 0.7 + 1.0)

    tail_root_x = -body_radius_x + 2
    tail_tip_x = -body_radius_x - species["tail_length"]
    tail_tip_offset_y = tail_swing_amount * (species["tail_spread"] * 0.6)
    tail_top_tip = (tail_tip_x, -species["tail_spread"] + tail_tip_offset_y)
    tail_bottom_tip = (tail_tip_x, species["tail_spread"] + tail_tip_offset_y)
    draw_filled_triangle(
        canvas,
        to_screen(tail_root_x, 0),
        to_screen(*tail_top_tip),
        to_screen(*tail_bottom_tip),
    )
    if species["tail_spread"] >= 4:
        notch_depth = species["tail_length"] * 0.45
        draw_filled_triangle(
            canvas,
            to_screen(tail_tip_x + notch_depth, tail_tip_offset_y * 0.5),
            to_screen(tail_tip_x - 1, tail_tip_offset_y - species["tail_spread"] * 0.45),
            to_screen(tail_tip_x - 1, tail_tip_offset_y + species["tail_spread"] * 0.45),
            pixel_value=0,
        )

    if species["dorsal_fin_height"] > 0:
        fin_sway = fin_flap_amount * 1.5
        draw_filled_triangle(
            canvas,
            to_screen(body_radius_x * 0.35, -body_radius_y + 1),
            to_screen(-body_radius_x * 0.45, -body_radius_y + 1),
            to_screen(-body_radius_x * 0.25 - fin_sway,
                      -body_radius_y - species["dorsal_fin_height"]),
        )

    if species["bottom_fin_height"] > 0:
        fin_sway = fin_flap_amount * 1.5
        draw_filled_triangle(
            canvas,
            to_screen(body_radius_x * 0.1, body_radius_y - 1),
            to_screen(-body_radius_x * 0.5, body_radius_y - 1),
            to_screen(-body_radius_x * 0.35 - fin_sway,
                      body_radius_y + species["bottom_fin_height"]),
        )

    whole_radius_x = int(math.ceil(body_radius_x))
    whole_radius_y = int(math.ceil(body_radius_y))
    for local_y in range(-whole_radius_y, whole_radius_y + 1):
        for local_x in range(-whole_radius_x, whole_radius_x + 1):
            ellipse_value = (local_x / body_radius_x) ** 2 + (local_y / body_radius_y) ** 2
            if ellipse_value <= 1.0:
                set_pixel(canvas, *to_screen(local_x, local_y), 1)

    stripe_count = species["stripe_count"]
    for stripe_index in range(stripe_count):
        stripe_center_x = body_radius_x * 0.5 - (stripe_index + 1) * (
            body_radius_x * 1.6 / (stripe_count + 1))
        for stripe_offset_x in (0, 1):
            local_x = int(round(stripe_center_x)) + stripe_offset_x
            for local_y in range(-whole_radius_y, whole_radius_y + 1):
                inner_ellipse_value = ((local_x / (body_radius_x - 1.5)) ** 2
                                       + (local_y / (body_radius_y - 1.5)) ** 2)
                if inner_ellipse_value <= 1.0:
                    set_pixel(canvas, *to_screen(local_x, local_y), 0)

    side_fin_start_x = body_radius_x * 0.15
    side_fin_start_y = body_radius_y * 0.25
    draw_line(
        canvas,
        *to_screen(side_fin_start_x, side_fin_start_y),
        *to_screen(side_fin_start_x - 4, side_fin_start_y + 1 + fin_flap_amount * 1.5),
        pixel_value=0,
    )

    eye_local_x = int(round(body_radius_x * 0.55))
    eye_local_y = int(round(-body_radius_y * 0.25))
    eye_size = 2 if species["body_height"] >= 9 else 1
    for eye_offset_x in range(eye_size):
        for eye_offset_y in range(eye_size):
            set_pixel(canvas, *to_screen(eye_local_x + eye_offset_x,
                                         eye_local_y + eye_offset_y), 0)

    set_pixel(canvas, *to_screen(whole_radius_x, 1), 0)
    set_pixel(canvas, *to_screen(whole_radius_x - 1, 1), 0)

    if species["has_spikes"]:
        spike_count = 14
        for spike_index in range(spike_count):
            spike_angle = (spike_index / spike_count) * 2 * math.pi
            edge_x = math.cos(spike_angle) * body_radius_x
            edge_y = math.sin(spike_angle) * body_radius_y
            tip_x = math.cos(spike_angle) * (body_radius_x + 2.5)
            tip_y = math.sin(spike_angle) * (body_radius_y + 2.5)
            draw_line(canvas, *to_screen(edge_x, edge_y), *to_screen(tip_x, tip_y))


# The seaweed plants along the bottom. Add or remove entries to change how many there are.
#   base_x - how far from the left edge the plant grows (0 to 127)
#   height - how tall the plant is in pixels
#   phase  - offsets the sway so plants don't all move in sync (any number, e.g. 0.0 to 3.0)
SEAWEED_STALKS = [
    {"base_x": 8, "height": 10, "phase": 0.0},
    {"base_x": 12, "height": 7, "phase": 1.3},
    {"base_x": 60, "height": 6, "phase": 2.1},
    {"base_x": 104, "height": 11, "phase": 0.7},
    {"base_x": 109, "height": 8, "phase": 2.8},
]


def draw_sand(canvas):
    sand_line_y = SCREEN_HEIGHT - 1
    for pixel_x in range(SCREEN_WIDTH):
        set_pixel(canvas, pixel_x, sand_line_y)
    for pixel_x in range(2, SCREEN_WIDTH, 7):
        set_pixel(canvas, pixel_x, sand_line_y - 1)


def draw_seaweed(canvas, animation_time):
    for stalk in SEAWEED_STALKS:
        for height_step in range(stalk["height"]):
            pixel_y = SCREEN_HEIGHT - 2 - height_step
            sway_strength = height_step / stalk["height"]
            sway_offset = math.sin(animation_time * 1.5 + height_step * 0.45
                                   + stalk["phase"]) * 1.8 * sway_strength
            set_pixel(canvas, stalk["base_x"] + sway_offset, pixel_y)


def draw_bubble(canvas, bubble):
    if bubble["size"] == 1:
        set_pixel(canvas, bubble["x"], bubble["y"])
    else:
        for offset_x, offset_y in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            set_pixel(canvas, bubble["x"] + offset_x, bubble["y"] + offset_y)


def update_bubbles(bubble_list, animation_time):
    for bubble in bubble_list:
        bubble["y"] -= bubble["rise_speed"]
        bubble["x"] += math.sin(animation_time * 3 + bubble["wobble_phase"]) * 0.3
    return [bubble for bubble in bubble_list if bubble["y"] > -2]


class FishTank:
    def __init__(self):
        self.animation_time = 0.0
        self.bubble_list = []
        self.current_species_index = -1
        self.facing_direction = random.choice([1, -1])
        self.start_new_fish()

    def start_new_fish(self):
        available_indexes = [index for index in range(len(FISH_SPECIES))
                             if index != self.current_species_index]
        self.current_species_index = random.choice(available_indexes)
        self.species = FISH_SPECIES[self.current_species_index]

        self.facing_direction *= -1

        fish_half_width = self.species["body_length"] / 2 + self.species["tail_length"] + 3
        self.fish_half_width = fish_half_width
        if self.facing_direction == 1:
            self.fish_x = -fish_half_width
        else:
            self.fish_x = SCREEN_WIDTH + fish_half_width

        fish_half_height = (self.species["body_height"] / 2
                            + max(self.species["dorsal_fin_height"],
                                  self.species["bottom_fin_height"], 3))
        lowest_allowed_y = fish_half_height + 1
        highest_allowed_y = SCREEN_HEIGHT - 4 - fish_half_height
        self.fish_base_y = random.uniform(lowest_allowed_y,
                                          max(lowest_allowed_y, highest_allowed_y))
        self.bob_phase = random.uniform(0, 2 * math.pi)

    def step(self, seconds_per_frame):
        self.animation_time += seconds_per_frame

        self.fish_x += self.species["speed"] * self.facing_direction
        bob_offset = math.sin(self.animation_time * 1.8 + self.bob_phase) * 2.0
        self.fish_y = self.fish_base_y + bob_offset

        if random.random() < BUBBLE_CHANCE_PER_FRAME:
            mouth_x = self.fish_x + self.facing_direction * (self.species["body_length"] / 2 + 1)
            self.bubble_list.append({
                "x": mouth_x,
                "y": self.fish_y - 1,
                "size": random.choice([1, 1, 2]),
                "rise_speed": random.uniform(0.3, 0.7),
                "wobble_phase": random.uniform(0, 2 * math.pi),
            })
        self.bubble_list = update_bubbles(self.bubble_list, self.animation_time)

        left_the_right_side = (self.facing_direction == 1
                               and self.fish_x - self.fish_half_width > SCREEN_WIDTH)
        left_the_left_side = (self.facing_direction == -1
                              and self.fish_x + self.fish_half_width < 0)
        if left_the_right_side or left_the_left_side:
            self.start_new_fish()

    def render(self):
        canvas = create_blank_canvas()
        if SHOW_SAND:
            draw_sand(canvas)
        if SHOW_SEAWEED:
            draw_seaweed(canvas, self.animation_time)
        for bubble in self.bubble_list:
            draw_bubble(canvas, bubble)
        draw_fish(canvas, self.species, self.fish_x, self.fish_y,
                  self.facing_direction, self.animation_time)
        return canvas


def find_gamesense_address():
    if platform.system() == "Windows":
        program_data_folder = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        core_props_path = os.path.join(program_data_folder, "SteelSeries",
                                       "SteelSeries Engine 3", "coreProps.json")
    elif platform.system() == "Darwin":
        core_props_path = ("/Library/Application Support/SteelSeries Engine 3/"
                           "coreProps.json")
    else:
        raise RuntimeError("SteelSeries GG only runs on Windows and macOS. "
                           "Use --preview to test on this machine.")

    if not os.path.exists(core_props_path):
        raise RuntimeError(f"Could not find {core_props_path}. Is SteelSeries GG running?")

    with open(core_props_path, "r", encoding="utf-8") as core_props_file:
        core_props = json.load(core_props_file)
    return "http://" + core_props["address"]


def post_to_gamesense(server_address, endpoint_path, payload):
    request_body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        server_address + endpoint_path,
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=2) as response:
        return response.read()


def register_with_gamesense(server_address):
    post_to_gamesense(server_address, "/game_metadata", {
        "game": GAMESENSE_GAME_NAME,
        "game_display_name": GAMESENSE_DISPLAY_NAME,
        "developer": GAMESENSE_DEVELOPER,
        "deinitialize_timer_length_ms": 5000,
    })
    blank_image = [0] * (SCREEN_WIDTH * SCREEN_HEIGHT // 8)
    post_to_gamesense(server_address, "/bind_game_event", {
        "game": GAMESENSE_GAME_NAME,
        "event": GAMESENSE_EVENT_NAME,
        "value_optional": True,
        "handlers": [{
            "device-type": "screened-128x40",
            "zone": "one",
            "mode": "screen",
            "datas": [{"has-text": False, "image-data": blank_image}],
        }],
    })


def canvas_to_oled_bytes(canvas):
    packed_bytes = []
    for pixel_y in range(SCREEN_HEIGHT):
        for byte_index in range(SCREEN_WIDTH // 8):
            byte_value = 0
            for bit_index in range(8):
                pixel_x = byte_index * 8 + bit_index
                if canvas[pixel_y][pixel_x]:
                    byte_value |= 1 << (7 - bit_index)
            packed_bytes.append(byte_value)
    return packed_bytes


def send_frame(server_address, canvas, frame_counter):
    post_to_gamesense(server_address, "/game_event", {
        "game": GAMESENSE_GAME_NAME,
        "event": GAMESENSE_EVENT_NAME,
        "data": {
            "value": frame_counter % 100,
            "frame": {"image-data-128x40": canvas_to_oled_bytes(canvas)},
        },
    })


def remove_from_gamesense(server_address):
    try:
        post_to_gamesense(server_address, "/remove_game", {"game": GAMESENSE_GAME_NAME})
    except (urllib.error.URLError, OSError):
        pass


def canvas_to_text(canvas):
    text_rows = []
    for pixel_y in range(0, SCREEN_HEIGHT, 2):
        row_characters = []
        for pixel_x in range(SCREEN_WIDTH):
            top_pixel = canvas[pixel_y][pixel_x]
            bottom_pixel = canvas[pixel_y + 1][pixel_x] if pixel_y + 1 < SCREEN_HEIGHT else 0
            if top_pixel and bottom_pixel:
                row_characters.append("█")
            elif top_pixel:
                row_characters.append("▀")
            elif bottom_pixel:
                row_characters.append("▄")
            else:
                row_characters.append(" ")
        text_rows.append("".join(row_characters))
    border = "+" + "-" * SCREEN_WIDTH + "+"
    return "\n".join([border] + ["|" + row + "|" for row in text_rows] + [border])


def main():
    argument_parser = argparse.ArgumentParser(description="Fish tank for SteelSeries OLED")
    argument_parser.add_argument("--preview", action="store_true",
                                 help="show the animation in the terminal instead")
    argument_parser.add_argument("--fps", type=int, default=DEFAULT_FRAMES_PER_SECOND,
                                 help="frames per second (default 15)")
    arguments = argument_parser.parse_args()

    seconds_per_frame = 1.0 / max(1, arguments.fps)
    fish_tank = FishTank()
    frame_counter = 0
    server_address = None

    if not arguments.preview:
        server_address = find_gamesense_address()
        register_with_gamesense(server_address)
        print(f"Connected to SteelSeries GG at {server_address}. Press Ctrl+C to stop.")

    try:
        while True:
            frame_start_time = time.monotonic()

            fish_tank.step(seconds_per_frame)
            canvas = fish_tank.render()

            if arguments.preview:
                sys.stdout.write("\033[H\033[2J" + canvas_to_text(canvas)
                                 + f"\n  {fish_tank.species['name']}\n")
                sys.stdout.flush()
            else:
                try:
                    send_frame(server_address, canvas, frame_counter)
                except (urllib.error.URLError, OSError):
                    print("Lost connection to SteelSeries GG, retrying...")
                    time.sleep(2)
                    try:
                        server_address = find_gamesense_address()
                        register_with_gamesense(server_address)
                    except (RuntimeError, urllib.error.URLError, OSError):
                        pass

            frame_counter += 1
            time_spent = time.monotonic() - frame_start_time
            time.sleep(max(0.0, seconds_per_frame - time_spent))
    except KeyboardInterrupt:
        print("\nStopping fish tank.")
    finally:
        if server_address:
            remove_from_gamesense(server_address)


if __name__ == "__main__":
    main()
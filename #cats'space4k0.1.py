#!/usr/bin/env python3
"""
cat's space invaders 0.1

Single-file arcade game. Everything drawn procedurally, FILES=off.
Python 3.10+ / pygame-ce.  Run:  python cats_space_invaders.py

Controls
  MENU   up/down + enter, or W/S
  PLAY   left/right or A/D, SPACE to fire, P pause, ESC menu
"""

import array
import math
import os
import random
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
try:
    import pygame
except ImportError:
    print("pip install pygame-ce", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------- constants
TITLE = "Space Invaders - Arcade Edition 0.1"
W, H = 800, 600
FPS = 60
STEP = 1.0 / FPS

BLACK = (8, 8, 16)
WHITE = (240, 244, 255)
GREY = (120, 126, 145)
DIM = (58, 62, 80)
CYAN = (110, 232, 255)
PINK = (255, 128, 196)
GREEN = (128, 240, 150)
ORANGE = (255, 176, 64)
YELLOW = (255, 224, 96)
RED = (255, 96, 96)
BG = (0, 0, 0)

ENEMY_COLORS = (WHITE, WHITE, WHITE)
ENEMY_POINTS = (30, 20, 10)

PLAYER_Y = 534
PLAYER_W, PLAYER_H = 40, 28
PLAYER_SPEED = 5.4
SHOT_COOLDOWN = 18
INVULN_FRAMES = 110

ENEMY_W, ENEMY_H = 32, 22
COLS, ROWS = 11, 5
SPACING_X, SPACING_Y = 52, 40
FORM_START_Y = 96
STEP_X, DROP_Y = 8, 16

BOMB_W, BOMB_H = 6, 11
BOMB_SPEED = 3.6
MAX_BOMBS = 3

CELL = 4
BUNKER_COLS, BUNKER_ROWS = 16, 12
BUNKER_Y = 462


def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


# ---------------------------------------------------------------- audio
def make_tone(freq, dur, vol=0.3, shape="sine"):
    if not pygame.mixer.get_init():
        return None
    rate = 22050
    n = max(1, int(rate * dur))
    buf = array.array("h")
    for i in range(n):
        t = i / rate
        env = 1.0 - (i / n)
        if shape == "square":
            wave = 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0
        else:
            wave = math.sin(2 * math.pi * freq * t)
        buf.append(int(32767 * vol * env * wave))
    return pygame.mixer.Sound(buffer=buf)


# ---------------------------------------------------------------- art
# Pixel patterns recreate the recognizable 1978 arcade silhouettes without assets.
PLAYER_PIXELS = [
    ".......XX.......", "......XXXX......", "......XXXX......",
    "XXXXXXXXXXXXXXX", "XXXXXXXXXXXXXXX", "XXXXXXXXXXXXXXX",
    "XXXXXXXXXXXXXXX", "XXXXXXXXXXXXXXX",
]
SQUID = [
    ["...XX...", "..XXXX..", ".XXXXXX.", "XX.XX.XX", "XXXXXXXX", "..X..X..", ".X.XX.X.", "X.X..X.X"],
    ["...XX...", "..XXXX..", ".XXXXXX.", "XX.XX.XX", "XXXXXXXX", ".X.XX.X.", "X......X", ".X....X."],
]
CRAB = [
    ["..X....X..", "...X..X...", "..XXXXXX..", ".XX.XX.XX.", "XXXXXXXXXX", "X.XXXXXX.X", "X.X....X.X", "...XX.XX.."],
    ["..X....X..", "X..X..X..X", "X.XXXXXX.X", "XXX.XX.XXX", "XXXXXXXXXX", ".XXXXXXXX.", "..X....X..", ".X......X."],
]
OCTOPUS = [
    ["...XXXX...", ".XXXXXXXX.", "XXXXXXXXXX", "XX..XX..XX", "XXXXXXXXXX", "..XX..XX..", ".XX.XX.XX.", "XX......XX"],
    ["...XXXX...", ".XXXXXXXX.", "XXXXXXXXXX", "XX..XX..XX", "XXXXXXXXXX", "...XXXX...", "..XX..XX..", ".XX....XX."],
]

def pixel_sprite(pattern, width, height, color):
    pw = max(len(line) for line in pattern)
    raw = pygame.Surface((pw, len(pattern)), pygame.SRCALPHA)
    for y, line in enumerate(pattern):
        for x, ch in enumerate(line):
            if ch == "X":
                raw.fill(color, (x, y, 1, 1))
    return pygame.transform.scale(raw, (width, height))


def make_player():
    return pixel_sprite(PLAYER_PIXELS, PLAYER_W, PLAYER_H, GREEN)


def make_enemy(kind, frame):
    patterns = (SQUID, CRAB, OCTOPUS)
    return pixel_sprite(patterns[kind][frame], ENEMY_W, ENEMY_H, WHITE)


def make_menu_cat():
    return pygame.transform.scale(make_player(), (PLAYER_W * 3, PLAYER_H * 3))


# ---------------------------------------------------------------- game
class Game:
    def __init__(self):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        try:
            pygame.mixer.init(22050, -16, 1, 512)
        except pygame.error:
            pass
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.font_xs = pygame.font.Font(None, 18)
        self.font_sm = pygame.font.Font(None, 22)
        self.font_md = pygame.font.Font(None, 32)
        self.font_lg = pygame.font.Font(None, 58)
        self.font_xl = pygame.font.Font(None, 92)

        self.player_img = make_player()
        self.enemy_imgs = [[make_enemy(k, f) for f in (0, 1)] for k in range(3)]
        self.menu_cat = make_menu_cat()

        self.sfx_shoot = make_tone(880, 0.07, 0.22, "square")
        self.sfx_hit = make_tone(320, 0.11, 0.3, "square")
        self.sfx_boom = make_tone(120, 0.42, 0.34)
        self.sfx_ui = make_tone(660, 0.05, 0.18, "square")
        self.sfx_wave = make_tone(1320, 0.22, 0.24)
        self.sfx_over = make_tone(70, 0.9, 0.36)
        self.march = [make_tone(f, 0.06, 0.16, "square") for f in (200, 170, 140, 115)]
        self.march_i = 0

        self.stars = []  # original arcade: pure black background

        self.state = "menu"
        self.menu_index = 0
        self.menu_items = ("START GAME", "HOW TO PLAY", "QUIT")
        self.blink = 0
        self.shake = 0
        self.high_score = 0

        self.new_game()

    # -- lifecycle ---------------------------------------------------
    def new_game(self):
        self.score = 0
        self.lives = 3
        self.wave = 1
        self.player_x = (W - PLAYER_W) / 2
        self.shot = None
        self.cooldown = 0
        self.invuln = 0
        self.bombs = []
        self.enemies = []
        self.bunkers = []
        self.wave_delay = 0
        self.step_dir = 1
        self.step_timer = 0
        self.anim = 0
        self.spawn_wave()

    def spawn_wave(self):
        self.enemies.clear()
        start_x = (W - (COLS * SPACING_X - SPACING_X + ENEMY_W)) // 2
        for row in range(ROWS):
            kind = 0 if row == 0 else (1 if row < 3 else 2)
            for col in range(COLS):
                self.enemies.append({
                    "rect": pygame.Rect(start_x + col * SPACING_X,
                                        FORM_START_Y + row * SPACING_Y,
                                        ENEMY_W, ENEMY_H),
                    "kind": kind, "col": col, "alive": True,
                })
        self.enemies_alive = len(self.enemies)
        self.bunkers = []
        for i in range(4):
            bx = int(W / 5 * (i + 1) - BUNKER_COLS * CELL / 2)
            grid = [[1] * BUNKER_COLS for _ in range(BUNKER_ROWS)]
            # Arcade shield: rounded top and an open lower central arch.
            for ry in range(BUNKER_ROWS):
                for rx in range(BUNKER_COLS):
                    if (ry < 2 and (rx < 3 - ry or rx >= BUNKER_COLS - 3 + ry)) or (ry >= 6 and 5 <= rx <= 10):
                        grid[ry][rx] = 0
            for r in range(2):
                for c in range(BUNKER_COLS):
                    if c < r + 2 or c > BUNKER_COLS - 3 - r:
                        grid[r][c] = 0
            self.bunkers.append({"x": bx, "y": BUNKER_Y, "grid": grid})
        self.bombs.clear()
        self.shot = None
        self.step_dir = 1
        self.step_timer = 0

    def play(self, snd):
        if snd:
            snd.play()

    # -- input -------------------------------------------------------
    def handle(self, e):
        if e.type == pygame.QUIT:
            return False
        if e.type != pygame.KEYDOWN:
            return True

        if self.state == "menu":
            if e.key in (pygame.K_UP, pygame.K_w):
                self.menu_index = (self.menu_index - 1) % len(self.menu_items)
                self.play(self.sfx_ui)
            elif e.key in (pygame.K_DOWN, pygame.K_s):
                self.menu_index = (self.menu_index + 1) % len(self.menu_items)
                self.play(self.sfx_ui)
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.play(self.sfx_ui)
                choice = self.menu_items[self.menu_index]
                if choice == "START GAME":
                    self.new_game()
                    self.state = "play"
                elif choice == "HOW TO PLAY":
                    self.state = "help"
                else:
                    return False
            elif e.key == pygame.K_ESCAPE:
                return False

        elif self.state == "help":
            if e.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                self.state = "menu"

        elif self.state == "play":
            if e.key == pygame.K_ESCAPE:
                self.state = "menu"
            elif e.key == pygame.K_p:
                self.state = "pause"

        elif self.state == "pause":
            if e.key == pygame.K_p:
                self.state = "play"
            elif e.key == pygame.K_ESCAPE:
                self.state = "menu"

        elif self.state == "over":
            if e.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.new_game()
                self.state = "play"
            elif e.key == pygame.K_ESCAPE:
                self.state = "menu"

        return True

    # -- update ------------------------------------------------------
    def update(self):
        self.blink += 1
        if self.shake > 0:
            self.shake -= 1
        for st in self.stars:
            st[1] += st[2]
            if st[1] > H:
                st[1] = -2
                st[0] = random.uniform(0, W)
        if self.state != "play":
            return
        if self.wave_delay > 0:
            self.wave_delay -= 1
            if self.wave_delay == 0:
                self.spawn_wave()
            return
        self.update_player()
        self.update_enemies()
        self.update_shot()
        self.update_bombs()
        self.check_collisions()

    def update_player(self):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.player_x -= PLAYER_SPEED
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.player_x += PLAYER_SPEED
        self.player_x = clamp(self.player_x, 6, W - PLAYER_W - 6)

        if self.cooldown > 0:
            self.cooldown -= 1
        if self.invuln > 0:
            self.invuln -= 1

        if keys[pygame.K_SPACE] and self.shot is None and self.cooldown == 0:
            self.shot = pygame.Rect(int(self.player_x + PLAYER_W / 2) - 2,
                                    PLAYER_Y - 12, 4, 12)
            self.cooldown = SHOT_COOLDOWN
            self.play(self.sfx_shoot)

    def player_rect(self):
        return pygame.Rect(int(self.player_x) + 4, PLAYER_Y + 2, PLAYER_W - 8, PLAYER_H - 4)

    def update_enemies(self):
        interval = max(5, int(40 - self.wave * 2 - (55 - self.enemies_alive) * 0.55))
        self.step_timer += 1
        if self.step_timer < interval:
            return
        self.step_timer = 0
        self.anim ^= 1

        dx = self.step_dir * STEP_X
        edge = False
        for e in self.enemies:
            if e["alive"]:
                r = e["rect"]
                if r.x + dx < 6 or r.x + dx + r.w > W - 6:
                    edge = True
                    break
        if edge:
            self.step_dir *= -1
            for e in self.enemies:
                if e["alive"]:
                    e["rect"].y += DROP_Y
        else:
            for e in self.enemies:
                if e["alive"]:
                    e["rect"].x += dx

        self.play(self.march[self.march_i])
        self.march_i = (self.march_i + 1) % len(self.march)

        for e in self.enemies:
            if e["alive"] and e["rect"].bottom >= PLAYER_Y + 6:
                self.game_over()
                return

        self.maybe_drop_bomb()

    def maybe_drop_bomb(self):
        if len(self.bombs) >= MAX_BOMBS or random.random() > 0.13:
            return
        columns = {}
        for e in self.enemies:
            if e["alive"]:
                columns[e["col"]] = e
        if not columns:
            return
        e = random.choice(list(columns.values()))
        self.bombs.append(pygame.Rect(e["rect"].centerx - BOMB_W // 2,
                                      e["rect"].bottom, BOMB_W, BOMB_H))

    def update_shot(self):
        if self.shot is None:
            return
        self.shot.y -= 11
        if self.shot.bottom < 0:
            self.shot = None

    def update_bombs(self):
        for b in self.bombs:
            b.y += BOMB_SPEED
        self.bombs = [b for b in self.bombs if b.top < PLAYER_Y + PLAYER_H]

    def check_collisions(self):
        p = self.player_rect()

        if self.shot is not None:
            for b in self.bunkers:
                if self.hit_bunker(b, self.shot, 5):
                    self.shot = None
                    break
            if self.shot is not None:
                for e in self.enemies:
                    if e["alive"] and self.shot.colliderect(e["rect"]):
                        e["alive"] = False
                        self.enemies_alive -= 1
                        self.score += ENEMY_POINTS[e["kind"]]
                        self.shot = None
                        self.play(self.sfx_hit)
                        if self.enemies_alive == 0:
                            self.wave += 1
                            self.wave_delay = 110
                            self.play(self.sfx_wave)
                        break

        for b in self.bombs[:]:
            if b not in self.bombs:
                continue
            for bk in self.bunkers:
                if self.hit_bunker(bk, b, 4):
                    self.bombs.remove(b)
                    break
            else:
                if self.invuln == 0 and b.colliderect(p):
                    self.bombs.remove(b)
                    self.kill_player()

        if self.invuln == 0:
            for e in self.enemies:
                if e["alive"] and e["rect"].colliderect(p):
                    self.kill_player()
                    break

        for e in self.enemies:
            if e["alive"]:
                for bk in self.bunkers:
                    self.erase_bunker(bk, e["rect"])

    def kill_player(self):
        self.lives -= 1
        self.invuln = INVULN_FRAMES
        self.shake = 14
        self.bombs.clear()
        self.shot = None
        self.player_x = (W - PLAYER_W) / 2
        self.play(self.sfx_boom)
        if self.lives <= 0:
            self.game_over()

    def game_over(self):
        self.high_score = max(self.high_score, self.score)
        self.state = "over"
        self.play(self.sfx_over)

    # -- bunkers -----------------------------------------------------
    def hit_bunker(self, bk, rect, radius):
        gx = rect.centerx - bk["x"]
        gy = rect.centery - bk["y"]
        c0, r0 = gx // CELL, gy // CELL
        if not (0 <= c0 < BUNKER_COLS and 0 <= r0 < BUNKER_ROWS):
            return False
        if not bk["grid"][r0][c0]:
            return False
        self.carve(bk, gx, gy, radius)
        return True

    def erase_bunker(self, bk, rect):
        if not rect.colliderect(pygame.Rect(bk["x"], bk["y"],
                                            BUNKER_COLS * CELL, BUNKER_ROWS * CELL)):
            return
        for ry in range(BUNKER_ROWS):
            for rx in range(BUNKER_COLS):
                if bk["grid"][ry][rx]:
                    px = bk["x"] + rx * CELL
                    py = bk["y"] + ry * CELL
                    if rect.collidepoint(px + 2, py + 2):
                        bk["grid"][ry][rx] = 0

    def carve(self, bk, gx, gy, radius):
        for ry in range(BUNKER_ROWS):
            for rx in range(BUNKER_COLS):
                dx = rx * CELL + 2 - gx
                dy = ry * CELL + 2 - gy
                if dx * dx + dy * dy <= radius * radius:
                    bk["grid"][ry][rx] = 0

    # -- draw --------------------------------------------------------
    def text(self, s, txt, font, col, cx, y, center=True):
        img = font.render(txt, True, col)
        if center:
            s.blit(img, (cx - img.get_width() // 2, y))
        else:
            s.blit(img, (cx, y))

    def draw_stars(self):
        for x, y, _sp, b in self.stars:
            self.screen.fill((b, b, min(255, b + 40)), (int(x), int(y), 1, 1))

    def draw(self):
        self.screen.fill(BG)
        # No starfield in the original arcade presentation.
        if self.state == "menu":
            self.draw_menu()
        elif self.state == "help":
            self.draw_help()
        else:
            self.draw_play()
            if self.state == "pause":
                self.draw_overlay("PAUSED", "P to resume   ESC for menu")
            elif self.state == "over":
                self.draw_overlay("GAME OVER", "ENTER to play again   ESC for menu")
        pygame.display.flip()

    def draw_menu(self):
        s = self.screen
        bob = math.sin(self.blink * 0.05) * 6
        s.blit(self.menu_cat, (W // 2 - self.menu_cat.get_width() // 2,
                               72 + bob))
        self.text(s, TITLE.upper(), self.font_lg, CYAN, W // 2, 190)
        self.text(s, "1978 ARCADE-STYLE  |  60 FPS  |  FILES OFF", self.font_sm, GREY, W // 2, 244)
        pygame.draw.line(s, DIM, (W // 2 - 190, 272), (W // 2 + 190, 272), 2)

        for i, item in enumerate(self.menu_items):
            y = 306 + i * 46
            sel = i == self.menu_index
            if sel:
                pygame.draw.rect(s, (24, 34, 60), (W // 2 - 150, y - 7, 300, 38),
                                 border_radius=6)
                pygame.draw.rect(s, CYAN, (W // 2 - 150, y - 7, 300, 38), 2,
                                 border_radius=6)
                caret = ">" if (self.blink // 16) % 2 == 0 else " "
                self.text(s, caret, self.font_md, YELLOW, W // 2 - 132, y + 2)
            self.text(s, item, self.font_md, WHITE if sel else GREY, W // 2, y + 2)

        if self.high_score:
            self.text(s, f"HIGH SCORE  {self.high_score}", self.font_sm, YELLOW,
                      W // 2, H - 78)
        self.text(s, "UP / DOWN to choose    ENTER to select", self.font_xs, DIM,
                  W // 2, H - 46)
        self.text(s, "LEFT/RIGHT or A/D to move, SPACE to fire", self.font_xs, DIM,
                  W // 2, H - 26)

    def draw_help(self):
        s = self.screen
        self.text(s, "HOW TO PLAY", self.font_lg, CYAN, W // 2, 74)
        lines = [
            "MOVE: LEFT / RIGHT arrows or A / D",
            "SHOOT: hold SPACE (one player shot at a time)",
            "PAUSE / RESUME: P",
            "RETURN TO MENU: ESC",
            "",
            "Shoot the invaders before they reach your cannon.",
            "Top row = 30 points, middle = 20, bottom = 10.",
            "Hide behind the green shields; shots destroy them.",
            "You have 3 lives. Clear all 55 to start a new wave.",
            "Invaders move faster as their numbers decrease.",
        ]
        y = 156
        for line in lines:
            self.text(s, line, self.font_sm, GREEN if line.startswith(("MOVE", "SHOOT", "PAUSE", "RETURN")) else WHITE, W // 2, y)
            y += 34
        self.text(s, "ESC to go back", self.font_sm, DIM, W // 2, H - 62)

    def draw_play(self):
        s = self.screen
        ox = oy = 0
        if self.shake > 0:
            ox = random.randint(-3, 3)
            oy = random.randint(-3, 3)

        for bk in self.bunkers:
            for ry in range(BUNKER_ROWS):
                row = bk["grid"][ry]
                for rx in range(BUNKER_COLS):
                    if row[rx]:
                        shade = GREEN
                        s.fill(shade, (bk["x"] + rx * CELL + ox,
                                       bk["y"] + ry * CELL + oy, CELL, CELL))

        for e in self.enemies:
            if e["alive"]:
                s.blit(self.enemy_imgs[e["kind"]][self.anim],
                       (e["rect"].x + ox, e["rect"].y + oy))

        for b in self.bombs:
            s.fill(WHITE, (b.x + ox, b.y + oy, BOMB_W, BOMB_H))

        if self.shot is not None:
            s.fill(WHITE, (self.shot.x + ox, self.shot.y + oy, 4, 12))


        if self.invuln == 0 or (self.blink // 5) % 2 == 0:
            s.blit(self.player_img, (int(self.player_x) + ox, PLAYER_Y + oy))

        s.fill((0, 0, 0), (0, 0, W, 40))
        self.text(s, f"SCORE {self.score:05d}", self.font_sm, WHITE, 16, 12, center=False)
        self.text(s, f"WAVE {self.wave}", self.font_sm, CYAN, W // 2, 12)
        self.text(s, f"HIGH {max(self.high_score, self.score):05d}", self.font_sm,
                  YELLOW, W - 150, 12, center=False)
        self.text(s, f"LIVES {self.lives}", self.font_sm, GREEN, W - 110, H - 30, center=False)
        pygame.draw.line(s, GREEN, (0, H - 44), (W, H - 44), 2)

        if self.wave_delay > 0:
            self.text(s, f"WAVE {self.wave - 1} CLEARED", self.font_lg, GREEN, W // 2, 250)

    def draw_overlay(self, title, sub):
        shade = pygame.Surface((W, H))
        shade.set_alpha(170)
        shade.fill(BLACK)
        self.screen.blit(shade, (0, 0))
        col = RED if title == "GAME OVER" else CYAN
        self.text(self.screen, title, self.font_xl, col, W // 2, H // 2 - 90)
        if title == "GAME OVER":
            self.text(self.screen, f"SCORE {self.score}   WAVE {self.wave}",
                      self.font_md, WHITE, W // 2, H // 2 + 10)
        self.text(self.screen, sub, self.font_sm, GREY, W // 2, H // 2 + 66)

    # -- loop --------------------------------------------------------
    def run(self):
        running = True
        acc = 0.0
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            acc += min(dt, 0.25)
            for e in pygame.event.get():
                if not self.handle(e):
                    running = False
            while acc >= STEP:
                self.update()
                acc -= STEP
            self.draw()
        pygame.quit()
        return 0


if __name__ == "__main__":
    raise SystemExit(Game().run())
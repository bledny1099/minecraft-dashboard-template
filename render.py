"""Top-down world renderer from Minecraft Anvil files (MC 1.16.5) — generates world icons for the dashboard.

Read-only inspection. Game does not need to be running. Pure Python (zlib/struct), zero Pillow dependency.
"""
import gzip
import hashlib
import math
import re
import struct
import zlib
from pathlib import Path

WORLD_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,32}$")
OUT = 384            # image dimensions in pixels
SCAN = 10            # chunk scan radius around spawn
BG = (13, 17, 23)

COLORS = {
    "grass_block": (95, 159, 53), "dirt": (134, 96, 67), "coarse_dirt": (119, 85, 59),
    "podzol": (91, 63, 24), "stone": (125, 125, 125), "cobblestone": (110, 110, 110),
    "sand": (219, 207, 163), "red_sand": (190, 102, 33), "gravel": (131, 127, 126),
    "water": (47, 91, 201), "lava": (234, 92, 15), "snow": (250, 250, 250),
    "snow_block": (250, 250, 250), "ice": (145, 183, 253), "bedrock": (60, 60, 60),
    "barrier": (200, 60, 60), "end_stone": (221, 223, 165), "obsidian": (21, 18, 30),
    "netherrack": (111, 54, 53), "sandstone": (216, 203, 155), "clay": (160, 166, 179),
    "mycelium": (111, 99, 105), "terracotta": (152, 94, 67), "grass_path": (148, 122, 65),
    "oak_planks": (162, 130, 78), "glass": (175, 213, 219), "farmland": (110, 75, 44),
    "netherite_block": (66, 61, 63), "diamond_block": (98, 219, 214), "gold_block": (246, 208, 61),
    "iron_block": (220, 220, 220), "bookshelf": (120, 90, 55), "torch": (255, 220, 120),
}
AIR = {"air", "cave_air", "void_air", "barrier", "light", "structure_void"}
KEYWORDS = [
    ("leaves", (56, 118, 29)), ("log", (102, 81, 49)), ("wood", (102, 81, 49)),
    ("planks", (162, 130, 78)), ("ore", (130, 130, 135)), ("grass", (95, 159, 53)),
    ("fern", (80, 140, 50)), ("flower", (200, 120, 160)), ("tulip", (200, 120, 160)),
    ("sand", (219, 207, 163)), ("stone", (125, 125, 125)), ("brick", (150, 97, 83)),
    ("concrete", (140, 140, 160)), ("wool", (220, 220, 220)), ("terracotta", (152, 94, 67)),
    ("dirt", (134, 96, 67)), ("water", (47, 91, 201)), ("kelp", (47, 120, 100)),
    ("seagrass", (47, 120, 100)), ("ice", (145, 183, 253)), ("snow", (250, 250, 250)),
    ("deepslate", (80, 80, 85)), ("nylium", (120, 40, 40)), ("basalt", (70, 70, 75)),
]
WATERISH = {"water", "kelp", "kelp_plant", "seagrass", "tall_seagrass", "bubble_column"}


def block_color(name: str):
    n = name.split(":", 1)[-1]
    if n in COLORS:
        return COLORS[n]
    for key, col in KEYWORDS:
        if key in n:
            return col
    h = hashlib.md5(n.encode()).digest()
    return (90 + h[0] % 120, 90 + h[1] % 120, 90 + h[2] % 120)


# ───────────── NBT ─────────────
def _nbt_payload(tag, b, p):
    if tag == 1:
        return struct.unpack_from(">b", b, p)[0], p + 1
    if tag == 2:
        return struct.unpack_from(">h", b, p)[0], p + 2
    if tag == 3:
        return struct.unpack_from(">i", b, p)[0], p + 4
    if tag == 4:
        return struct.unpack_from(">q", b, p)[0], p + 8
    if tag == 5:
        return struct.unpack_from(">f", b, p)[0], p + 4
    if tag == 6:
        return struct.unpack_from(">d", b, p)[0], p + 8
    if tag == 7:
        n = struct.unpack_from(">i", b, p)[0]
        return b[p + 4:p + 4 + n], p + 4 + n
    if tag == 8:
        n = struct.unpack_from(">H", b, p)[0]
        return b[p + 2:p + 2 + n].decode("utf-8", "replace"), p + 2 + n
    if tag == 9:
        t = b[p]
        n = struct.unpack_from(">i", b, p + 1)[0]
        p += 5
        out = []
        for _ in range(n):
            v, p = _nbt_payload(t, b, p)
            out.append(v)
        return out, p
    if tag == 10:
        out = {}
        while True:
            t = b[p]
            p += 1
            if t == 0:
                return out, p
            n = struct.unpack_from(">H", b, p)[0]
            key = b[p + 2:p + 2 + n].decode("utf-8", "replace")
            v, p = _nbt_payload(t, b, p + 2 + n)
            out[key] = v
    if tag == 11:
        n = struct.unpack_from(">i", b, p)[0]
        return list(struct.unpack_from(f">{n}i", b, p + 4)), p + 4 + 4 * n
    if tag == 12:
        n = struct.unpack_from(">i", b, p)[0]
        return list(struct.unpack_from(f">{n}Q", b, p + 4)), p + 4 + 8 * n
    raise ValueError("bad nbt tag")


def parse_nbt(data: bytes) -> dict:
    if data[0] != 10:
        raise ValueError("root is not a compound")
    n = struct.unpack_from(">H", data, 1)[0]
    val, _ = _nbt_payload(10, data, 3 + n)
    return val


# ───────────── Anvil ─────────────
def _read_chunk(region: bytes, cx: int, cz: int):
    i = 4 * ((cx & 31) + (cz & 31) * 32)
    ent = struct.unpack_from(">I", region, i)[0]
    off, cnt = ent >> 8, ent & 0xFF
    if off == 0 or cnt == 0:
        return None
    pos = off * 4096
    length = struct.unpack_from(">I", region, pos)[0]
    comp = region[pos + 4]
    raw = region[pos + 5:pos + 4 + length]
    if comp == 2:
        raw = zlib.decompress(raw)
    elif comp == 1:
        raw = gzip.decompress(raw)
    elif comp != 3:
        return None
    return parse_nbt(raw)


def _unpack(longs, bits, count):
    per = 64 // bits
    mask = (1 << bits) - 1
    out = []
    for v in longs:
        for k in range(per):
            out.append((v >> (k * bits)) & mask)
            if len(out) >= count:
                return out
    return out


def _chunk_columns(level: dict):
    """Returns a list of 256 (height, blockname) or None if chunk is not ready."""
    if level.get("Status") != "full":
        return None
    hm = level.get("Heightmaps", {}).get("WORLD_SURFACE")
    if not hm:
        return None
    heights = _unpack(hm, 9, 256)
    secs = {}
    for s in level.get("Sections", []):
        if "Palette" in s and "BlockStates" in s:
            secs[s["Y"]] = s
    cache = {}

    def block_at(x, y, z):
        s = secs.get(y >> 4)
        if s is None:
            return "air"
        pal = s["Palette"]
        if len(pal) == 1:
            return pal[0]["Name"]
        idx = cache.get(y >> 4)
        if idx is None:
            bits = max(4, (len(pal) - 1).bit_length())
            idx = cache[y >> 4] = _unpack(s["BlockStates"], bits, 4096)
        return pal[idx[((y & 15) << 8) | (z << 4) | x]]["Name"]

    cols = []
    for z in range(16):
        for x in range(16):
            h = heights[z * 16 + x]
            if h <= 0:
                cols.append((0, None, 0))
                continue
            y = h - 1
            name = block_at(x, y, z)
            n = name.split(":", 1)[-1]
            steps = 0
            while n in AIR and y > 0 and steps < 6:
                y -= 1
                steps += 1
                name = block_at(x, y, z)
                n = name.split(":", 1)[-1]
            depth = 0
            if n in WATERISH:
                yy = y
                while yy > 0 and depth < 10 and block_at(x, yy, z).split(":", 1)[-1] in WATERISH:
                    yy -= 1
                    depth += 1
            cols.append((y, None if n in AIR else name, depth))
    return cols


def _png(w, h, rgb: bytes) -> bytes:
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    stride = w * 3
    raw = b"".join(b"\x00" + rgb[y * stride:(y + 1) * stride] for y in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def placeholder(kind: str) -> bytes:
    top, bot = {"nether": ((90, 20, 25), (30, 8, 12)), "end": ((70, 50, 110), (18, 14, 30))}.get(
        kind, ((40, 50, 70), (13, 17, 23)))
    rows = []
    for y in range(OUT):
        t = y / (OUT - 1)
        px = bytes(int(top[i] * (1 - t) + bot[i] * t) for i in range(3))
        rows.append(px * OUT)
    return _png(OUT, OUT, b"".join(rows))


def _spawn(world_dir: Path):
    try:
        data = gzip.decompress((world_dir / "level.dat").read_bytes())
        d = parse_nbt(data)["Data"]
        return int(d.get("SpawnX", 0)), int(d.get("SpawnZ", 0))
    except Exception:  # noqa: BLE001
        return 0, 0


def render_world(base: Path, wid: str) -> bytes:
    """Top-down PNG around spawn of world `wid` (folder base/wid). Raises on error."""
    if not WORLD_ID_RE.match(wid):
        raise ValueError("bad world id")
    world_dir = (base / wid).resolve()
    if base.resolve() not in world_dir.parents:
        raise ValueError("path escape")
    if wid.endswith("_nether") and not (world_dir / "region").exists():
        return placeholder("nether")
    region_dir = world_dir / "region"
    if not region_dir.exists():
        region_dir = world_dir / "DIM1" / "region"
        kind = "end"
    else:
        kind = "overworld"
    if not region_dir.exists():
        return placeholder("nether" if wid.endswith("nether") else "end" if wid.endswith("end") else "x")

    # Center on (0, 0) or spawn coordinates
    sx, sz = (0, 0) if wid == "world" else _spawn(world_dir)
    ccx, ccz = sx >> 4, sz >> 4
    size = SCAN * 2 * 16
    ox, oz = (ccx - SCAN) * 16, (ccz - SCAN) * 16
    heights = [[None] * size for _ in range(size)]
    colors = [[None] * size for _ in range(size)]

    regions = {}
    for cz in range(ccz - SCAN, ccz + SCAN):
        for cx in range(ccx - SCAN, ccx + SCAN):
            key = (cx >> 5, cz >> 5)
            if key not in regions:
                f = region_dir / f"r.{key[0]}.{key[1]}.mca"
                try:
                    regions[key] = f.read_bytes() if f.is_file() else None
                except OSError:
                    regions[key] = None
            data = regions[key]
            if not data or len(data) < 8192:
                continue
            try:
                nbt = _read_chunk(data, cx, cz)
                cols = _chunk_columns(nbt["Level"]) if nbt else None
            except Exception:  # noqa: BLE001
                cols = None
            if not cols:
                continue
            for i, (y, name, depth) in enumerate(cols):
                if name is None:
                    continue
                px, pz = (cx * 16 + (i & 15)) - ox, (cz * 16 + (i >> 4)) - oz
                col = block_color(name)
                if depth:
                    k = max(0.45, 1 - depth * 0.06)
                    col = tuple(int(c * k) for c in col)
                heights[pz][px] = y
                colors[pz][px] = col

    # Bounding box of populated block columns
    xs = [x for row in colors for x, c in enumerate(row) if c]
    zs = [z for z, row in enumerate(colors) if any(row)]
    if not xs:
        return placeholder("x")
    x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
    side = max(x1 - x0, z1 - z0) + 1 + 16
    side = max(64, min(size, side))
    cx0 = max(0, min(size - side, (x0 + x1) // 2 - side // 2))
    cz0 = max(0, min(size - side, (z0 + z1) // 2 - side // 2))

    out = bytearray()
    for py in range(OUT):
        zz = cz0 + py * side // OUT
        for px in range(OUT):
            xx = cx0 + px * side // OUT
            c = colors[zz][xx]
            if c is None:
                out += bytes(BG)
                continue
            h = heights[zz][xx]
            hn = heights[zz - 1][xx] if zz > 0 and heights[zz - 1][xx] is not None else h
            k = 1 + max(-0.25, min(0.25, (h - hn) * 0.05))
            out += bytes(max(0, min(255, int(v * k))) for v in c)
    return _png(OUT, OUT, bytes(out))

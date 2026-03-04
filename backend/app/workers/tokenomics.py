"""
Hardcoded tokenomics schedule derived from the presale batches spreadsheet.

Each entry is keyed by day number (1-150) and contains:
  - price_usd: token price as on-chain u64 (USD × 10^6 precision)
  - tge: TGE unlock percentage (u8, 0-100)
  - daily_cap: daily token cap as on-chain u64 (tokens × 10^6)

On-chain precision:
  token_price_usd is stored as u64 with 10^6 precision.
    e.g. $0.0010 → 0.0010 * 10^6 = 1_000
  daily_cap is stored as u64 in smallest token units (10^6 decimals).
    e.g. 30_000_000 tokens → 30_000_000 * 10^6 = 30_000_000_000_000
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from app.core.config import settings
from app.core.utils import scale_to_chain


@dataclass(frozen=True, slots=True)
class DayConfig:
    price_usd: int  # on-chain u64 (USD price × 10^6)
    tge: int  # on-chain u8 (percentage 0-100)
    daily_cap: int  # on-chain u64 (tokens × 10^6)
    stage: int  # stage number
    daily_growth: float  # daily growth percentage


def _p(usd: float) -> int:
    """Convert a USD price (e.g. 0.0010) to on-chain u64."""
    return scale_to_chain(usd)


def _c(tokens_millions: int) -> int:
    """Convert token cap in whole tokens to on-chain u64."""
    return scale_to_chain(tokens_millions)


LISTING_PRICE_USD = 0.012

# fmt: off
SCHEDULE: dict[int, DayConfig] = {
    # --- Stay Score 1 (Days 1-10): price grows 1.75%/day, TGE 50%, 30M cap ---
    1:   DayConfig(_p(0.0010),  50, _c(30_000_000), 1, 1.75),
    2:   DayConfig(_p(0.00102), 50, _c(30_000_000), 1, 1.75),
    3:   DayConfig(_p(0.00104), 50, _c(30_000_000), 1, 1.75),
    4:   DayConfig(_p(0.00105), 50, _c(30_000_000), 1, 1.75),
    5:   DayConfig(_p(0.00107), 50, _c(30_000_000), 1, 1.75),
    6:   DayConfig(_p(0.00109), 50, _c(30_000_000), 1, 1.75),
    7:   DayConfig(_p(0.00111), 50, _c(30_000_000), 1, 1.75),
    8:   DayConfig(_p(0.00113), 50, _c(30_000_000), 1, 1.75),
    9:   DayConfig(_p(0.00115), 50, _c(30_000_000), 1, 1.75),
    10:  DayConfig(_p(0.00117), 50, _c(30_000_000), 1, 1.75),
    # --- Stay Score 2 (Days 11-20): price grows 1.70%/day, TGE 49%, 28M cap ---
    11:  DayConfig(_p(0.00119), 49, _c(28_000_000), 2, 1.70),
    12:  DayConfig(_p(0.00121), 49, _c(28_000_000), 2, 1.70),
    13:  DayConfig(_p(0.00123), 49, _c(28_000_000), 2, 1.70),
    14:  DayConfig(_p(0.00125), 49, _c(28_000_000), 2, 1.70),
    15:  DayConfig(_p(0.00127), 49, _c(28_000_000), 2, 1.70),
    16:  DayConfig(_p(0.00129), 49, _c(28_000_000), 2, 1.70),
    17:  DayConfig(_p(0.00132), 49, _c(28_000_000), 2, 1.70),
    18:  DayConfig(_p(0.00134), 49, _c(28_000_000), 2, 1.70),
    19:  DayConfig(_p(0.00136), 49, _c(28_000_000), 2, 1.70),
    20:  DayConfig(_p(0.00138), 49, _c(28_000_000), 2, 1.70),
    # --- Stay Score 3 (Days 21-30): price grows 1.65%/day, TGE 48%, 26M cap ---
    21:  DayConfig(_p(0.00141), 48, _c(26_000_000), 3, 1.65),
    22:  DayConfig(_p(0.00143), 48, _c(26_000_000), 3, 1.65),
    23:  DayConfig(_p(0.00145), 48, _c(26_000_000), 3, 1.65),
    24:  DayConfig(_p(0.00148), 48, _c(26_000_000), 3, 1.65),
    25:  DayConfig(_p(0.00150), 48, _c(26_000_000), 3, 1.65),
    26:  DayConfig(_p(0.00153), 48, _c(26_000_000), 3, 1.65),
    27:  DayConfig(_p(0.00155), 48, _c(26_000_000), 3, 1.65),
    28:  DayConfig(_p(0.00158), 48, _c(26_000_000), 3, 1.65),
    29:  DayConfig(_p(0.00160), 48, _c(26_000_000), 3, 1.65),
    30:  DayConfig(_p(0.00163), 48, _c(26_000_000), 3, 1.65),
    # --- Stay Score 4 (Days 31-40): price grows 1.60%/day, TGE 47%, 24M cap ---
    31:  DayConfig(_p(0.00166), 47, _c(24_000_000), 4, 1.60),
    32:  DayConfig(_p(0.00168), 47, _c(24_000_000), 4, 1.60),
    33:  DayConfig(_p(0.00171), 47, _c(24_000_000), 4, 1.60),
    34:  DayConfig(_p(0.00174), 47, _c(24_000_000), 4, 1.60),
    35:  DayConfig(_p(0.00176), 47, _c(24_000_000), 4, 1.60),
    36:  DayConfig(_p(0.00179), 47, _c(24_000_000), 4, 1.60),
    37:  DayConfig(_p(0.00182), 47, _c(24_000_000), 4, 1.60),
    38:  DayConfig(_p(0.00185), 47, _c(24_000_000), 4, 1.60),
    39:  DayConfig(_p(0.00188), 47, _c(24_000_000), 4, 1.60),
    40:  DayConfig(_p(0.00191), 47, _c(24_000_000), 4, 1.60),
    # --- Stay Score 5 (Days 41-50): price grows 1.55%/day, TGE 46%, 22M cap ---
    41:  DayConfig(_p(0.00194), 46, _c(22_000_000), 5, 1.55),
    42:  DayConfig(_p(0.00197), 46, _c(22_000_000), 5, 1.55),
    43:  DayConfig(_p(0.00200), 46, _c(22_000_000), 5, 1.55),
    44:  DayConfig(_p(0.00203), 46, _c(22_000_000), 5, 1.55),
    45:  DayConfig(_p(0.00206), 46, _c(22_000_000), 5, 1.55),
    46:  DayConfig(_p(0.00209), 46, _c(22_000_000), 5, 1.55),
    47:  DayConfig(_p(0.00213), 46, _c(22_000_000), 5, 1.55),
    48:  DayConfig(_p(0.00216), 46, _c(22_000_000), 5, 1.55),
    49:  DayConfig(_p(0.00219), 46, _c(22_000_000), 5, 1.55),
    50:  DayConfig(_p(0.00223), 46, _c(22_000_000), 5, 1.55),
    # --- Stay Score 6 (Days 51-60): price grows 1.50%/day, TGE 45%, 20M cap ---
    51:  DayConfig(_p(0.00226), 45, _c(20_000_000), 6, 1.50),
    52:  DayConfig(_p(0.00229), 45, _c(20_000_000), 6, 1.50),
    53:  DayConfig(_p(0.00233), 45, _c(20_000_000), 6, 1.50),
    54:  DayConfig(_p(0.00236), 45, _c(20_000_000), 6, 1.50),
    55:  DayConfig(_p(0.00240), 45, _c(20_000_000), 6, 1.50),
    56:  DayConfig(_p(0.00244), 45, _c(20_000_000), 6, 1.50),
    57:  DayConfig(_p(0.00247), 45, _c(20_000_000), 6, 1.50),
    58:  DayConfig(_p(0.00251), 45, _c(20_000_000), 6, 1.50),
    59:  DayConfig(_p(0.00255), 45, _c(20_000_000), 6, 1.50),
    60:  DayConfig(_p(0.00259), 45, _c(20_000_000), 6, 1.50),
    # --- Stay Score 7 (Days 61-70): price grows 1.45%/day, TGE 44%, 18M cap ---
    61:  DayConfig(_p(0.00262), 44, _c(18_000_000), 7, 1.45),
    62:  DayConfig(_p(0.00266), 44, _c(18_000_000), 7, 1.45),
    63:  DayConfig(_p(0.00270), 44, _c(18_000_000), 7, 1.45),
    64:  DayConfig(_p(0.00274), 44, _c(18_000_000), 7, 1.45),
    65:  DayConfig(_p(0.00278), 44, _c(18_000_000), 7, 1.45),
    66:  DayConfig(_p(0.00282), 44, _c(18_000_000), 7, 1.45),
    67:  DayConfig(_p(0.00286), 44, _c(18_000_000), 7, 1.45),
    68:  DayConfig(_p(0.00290), 44, _c(18_000_000), 7, 1.45),
    69:  DayConfig(_p(0.00294), 44, _c(18_000_000), 7, 1.45),
    70:  DayConfig(_p(0.00299), 44, _c(18_000_000), 7, 1.45),
    # --- Stay Score 8 (Days 71-80): price grows 1.40%/day, TGE 43%, 16M cap ---
    71:  DayConfig(_p(0.00303), 43, _c(16_000_000), 8, 1.40),
    72:  DayConfig(_p(0.00307), 43, _c(16_000_000), 8, 1.40),
    73:  DayConfig(_p(0.00311), 43, _c(16_000_000), 8, 1.40),
    74:  DayConfig(_p(0.00316), 43, _c(16_000_000), 8, 1.40),
    75:  DayConfig(_p(0.00320), 43, _c(16_000_000), 8, 1.40),
    76:  DayConfig(_p(0.00325), 43, _c(16_000_000), 8, 1.40),
    77:  DayConfig(_p(0.00329), 43, _c(16_000_000), 8, 1.40),
    78:  DayConfig(_p(0.00334), 43, _c(16_000_000), 8, 1.40),
    79:  DayConfig(_p(0.00338), 43, _c(16_000_000), 8, 1.40),
    80:  DayConfig(_p(0.00343), 43, _c(16_000_000), 8, 1.40),
    # --- Stay Score 9 (Days 81-90): price grows 1.35%/day, TGE 42%, 14M cap ---
    81:  DayConfig(_p(0.00348), 42, _c(14_000_000), 9, 1.35),
    82:  DayConfig(_p(0.00352), 42, _c(14_000_000), 9, 1.35),
    83:  DayConfig(_p(0.00357), 42, _c(14_000_000), 9, 1.35),
    84:  DayConfig(_p(0.00362), 42, _c(14_000_000), 9, 1.35),
    85:  DayConfig(_p(0.00367), 42, _c(14_000_000), 9, 1.35),
    86:  DayConfig(_p(0.00372), 42, _c(14_000_000), 9, 1.35),
    87:  DayConfig(_p(0.00377), 42, _c(14_000_000), 9, 1.35),
    88:  DayConfig(_p(0.00382), 42, _c(14_000_000), 9, 1.35),
    89:  DayConfig(_p(0.00387), 42, _c(14_000_000), 9, 1.35),
    90:  DayConfig(_p(0.00392), 42, _c(14_000_000), 9, 1.35),
    # --- Stay Score 10 (Days 91-100): price grows 1.30%/day, TGE 41%, 12M cap ---
    91:  DayConfig(_p(0.00397), 41, _c(12_000_000), 10, 1.30),
    92:  DayConfig(_p(0.00403), 41, _c(12_000_000), 10, 1.30),
    93:  DayConfig(_p(0.00408), 41, _c(12_000_000), 10, 1.30),
    94:  DayConfig(_p(0.00413), 41, _c(12_000_000), 10, 1.30),
    95:  DayConfig(_p(0.00418), 41, _c(12_000_000), 10, 1.30),
    96:  DayConfig(_p(0.00424), 41, _c(12_000_000), 10, 1.30),
    97:  DayConfig(_p(0.00429), 41, _c(12_000_000), 10, 1.30),
    98:  DayConfig(_p(0.00435), 41, _c(12_000_000), 10, 1.30),
    99:  DayConfig(_p(0.00441), 41, _c(12_000_000), 10, 1.30),
    100: DayConfig(_p(0.00446), 41, _c(12_000_000), 10, 1.30),
    # --- Stay Score 11 (Days 101-110): price grows 1.25%/day, TGE 40%, 10M cap ---
    101: DayConfig(_p(0.00452), 40, _c(10_000_000), 11, 1.25),
    102: DayConfig(_p(0.00458), 40, _c(10_000_000), 11, 1.25),
    103: DayConfig(_p(0.00463), 40, _c(10_000_000), 11, 1.25),
    104: DayConfig(_p(0.00469), 40, _c(10_000_000), 11, 1.25),
    105: DayConfig(_p(0.00475), 40, _c(10_000_000), 11, 1.25),
    106: DayConfig(_p(0.00481), 40, _c(10_000_000), 11, 1.25),
    107: DayConfig(_p(0.00487), 40, _c(10_000_000), 11, 1.25),
    108: DayConfig(_p(0.00493), 40, _c(10_000_000), 11, 1.25),
    109: DayConfig(_p(0.00499), 40, _c(10_000_000), 11, 1.25),
    110: DayConfig(_p(0.00505), 40, _c(10_000_000), 11, 1.25),
    # --- Stay Score 12 (Days 111-120): price grows 1.20%/day, TGE 39%, 8M cap ---
    111: DayConfig(_p(0.00512), 39, _c(8_000_000), 12, 1.20),
    112: DayConfig(_p(0.00518), 39, _c(8_000_000), 12, 1.20),
    113: DayConfig(_p(0.00524), 39, _c(8_000_000), 12, 1.20),
    114: DayConfig(_p(0.00530), 39, _c(8_000_000), 12, 1.20),
    115: DayConfig(_p(0.00537), 39, _c(8_000_000), 12, 1.20),
    116: DayConfig(_p(0.00543), 39, _c(8_000_000), 12, 1.20),
    117: DayConfig(_p(0.00549), 39, _c(8_000_000), 12, 1.20),
    118: DayConfig(_p(0.00556), 39, _c(8_000_000), 12, 1.20),
    119: DayConfig(_p(0.00563), 39, _c(8_000_000), 12, 1.20),
    120: DayConfig(_p(0.00569), 39, _c(8_000_000), 12, 1.20),
    # --- Stay Score 13 (Days 121-130): price grows 1.15%/day, TGE 38%, 6M cap ---
    121: DayConfig(_p(0.00576), 38, _c(6_000_000), 13, 1.15),
    122: DayConfig(_p(0.00583), 38, _c(6_000_000), 13, 1.15),
    123: DayConfig(_p(0.00589), 38, _c(6_000_000), 13, 1.15),
    124: DayConfig(_p(0.00596), 38, _c(6_000_000), 13, 1.15),
    125: DayConfig(_p(0.00603), 38, _c(6_000_000), 13, 1.15),
    126: DayConfig(_p(0.00610), 38, _c(6_000_000), 13, 1.15),
    127: DayConfig(_p(0.00617), 38, _c(6_000_000), 13, 1.15),
    128: DayConfig(_p(0.00624), 38, _c(6_000_000), 13, 1.15),
    129: DayConfig(_p(0.00631), 38, _c(6_000_000), 13, 1.15),
    130: DayConfig(_p(0.00638), 38, _c(6_000_000), 13, 1.15),
    # --- Stay Score 14 (Days 131-140): price grows 1.10%/day, TGE 37%, 4M cap ---
    131: DayConfig(_p(0.00645), 37, _c(4_000_000), 14, 1.10),
    132: DayConfig(_p(0.00653), 37, _c(4_000_000), 14, 1.10),
    133: DayConfig(_p(0.00660), 37, _c(4_000_000), 14, 1.10),
    134: DayConfig(_p(0.00667), 37, _c(4_000_000), 14, 1.10),
    135: DayConfig(_p(0.00674), 37, _c(4_000_000), 14, 1.10),
    136: DayConfig(_p(0.00682), 37, _c(4_000_000), 14, 1.10),
    137: DayConfig(_p(0.00689), 37, _c(4_000_000), 14, 1.10),
    138: DayConfig(_p(0.00697), 37, _c(4_000_000), 14, 1.10),
    139: DayConfig(_p(0.00705), 37, _c(4_000_000), 14, 1.10),
    140: DayConfig(_p(0.00712), 37, _c(4_000_000), 14, 1.10),
    # --- Stay Score 15 (Days 141-150): price grows 1.05%/day, TGE 36%, 2M cap ---
    141: DayConfig(_p(0.00720), 36, _c(2_000_000), 15, 1.05),
    142: DayConfig(_p(0.00727), 36, _c(2_000_000), 15, 1.05),
    143: DayConfig(_p(0.00735), 36, _c(2_000_000), 15, 1.05),
    144: DayConfig(_p(0.00743), 36, _c(2_000_000), 15, 1.05),
    145: DayConfig(_p(0.00750), 36, _c(2_000_000), 15, 1.05),
    146: DayConfig(_p(0.00758), 36, _c(2_000_000), 15, 1.05),
    147: DayConfig(_p(0.00766), 36, _c(2_000_000), 15, 1.05),
    148: DayConfig(_p(0.00774), 36, _c(2_000_000), 15, 1.05),
    149: DayConfig(_p(0.00782), 36, _c(2_000_000), 15, 1.05),
    150: DayConfig(_p(0.00791), 36, _c(2_000_000), 15, 1.05),
}
# fmt: on


def get_presale_day() -> int:
    """Return the current presale day number (1-based)."""
    start = date.fromisoformat(settings.presale_start_date)
    today = datetime.now(timezone.utc).date()
    return (today - start).days + 1


def get_today_token_data() -> DayConfig:
    day = get_presale_day()
    if day < 1:
        return DayConfig(0, 0, 0, 0, 0)
    elif day > TOTAL_DAYS:
        return SCHEDULE[TOTAL_DAYS]
    return SCHEDULE[day]


TOTAL_DAYS = len(SCHEDULE)  # 150

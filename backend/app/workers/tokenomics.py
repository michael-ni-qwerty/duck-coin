"""
Hardcoded tokenomics schedule derived from the presale batches spreadsheet.

Each entry is keyed by day number (1-150) and contains:
  - price_usd: token price as on-chain u64 (USD × 10^9 precision)
  - tge: TGE unlock percentage (u8, 0-100)
  - daily_cap: daily token cap as on-chain u64 (tokens × 10^9)

On-chain precision:
  token_price_usd is stored as u64 with 10^9 precision.
    e.g. $0.0010 → 0.0010 * 10^9 = 1_000_000
  daily_cap is stored as u64 in smallest token units (10^9 decimals).
    e.g. 30_000_000 tokens → 30_000_000 * 10^9 = 30_000_000_000_000_000
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timezone, timedelta
from app.core.config import settings

TOKEN_DECIMALS = 10**9
PRICE_PRECISION = 10**9


@dataclass(frozen=True, slots=True)
class DayConfig:
    price_usd: int      # on-chain u64 (USD price × 10^9)
    tge: int             # on-chain u8 (percentage 0-100)
    daily_cap: int       # on-chain u64 (tokens × 10^9)


def _p(usd: float) -> int:
    """Convert a USD price (e.g. 0.0010) to on-chain u64."""
    return int(round(usd * PRICE_PRECISION))


def _c(tokens_millions: int) -> int:
    """Convert token cap in whole tokens to on-chain u64."""
    return tokens_millions * TOKEN_DECIMALS

LISTING_PRICE_USD = 0.012

# fmt: off
SCHEDULE: dict[int, DayConfig] = {
    # --- Stay Score 1 (Days 1-10): price grows 1.75%/day, TGE 50%, 30M cap ---
    1:   DayConfig(_p(0.0010),  50, _c(30_000_000)),
    2:   DayConfig(_p(0.00102), 50, _c(30_000_000)),
    3:   DayConfig(_p(0.00104), 50, _c(30_000_000)),
    4:   DayConfig(_p(0.00105), 50, _c(30_000_000)),
    5:   DayConfig(_p(0.00107), 50, _c(30_000_000)),
    6:   DayConfig(_p(0.00109), 50, _c(30_000_000)),
    7:   DayConfig(_p(0.00111), 50, _c(30_000_000)),
    8:   DayConfig(_p(0.00113), 50, _c(30_000_000)),
    9:   DayConfig(_p(0.00115), 50, _c(30_000_000)),
    10:  DayConfig(_p(0.00117), 50, _c(30_000_000)),
    # --- Stay Score 2 (Days 11-20): price grows 1.70%/day, TGE 49%, 28M cap ---
    11:  DayConfig(_p(0.00119), 49, _c(28_000_000)),
    12:  DayConfig(_p(0.00121), 49, _c(28_000_000)),
    13:  DayConfig(_p(0.00123), 49, _c(28_000_000)),
    14:  DayConfig(_p(0.00125), 49, _c(28_000_000)),
    15:  DayConfig(_p(0.00127), 49, _c(28_000_000)),
    16:  DayConfig(_p(0.00129), 49, _c(28_000_000)),
    17:  DayConfig(_p(0.00132), 49, _c(28_000_000)),
    18:  DayConfig(_p(0.00134), 49, _c(28_000_000)),
    19:  DayConfig(_p(0.00136), 49, _c(28_000_000)),
    20:  DayConfig(_p(0.00138), 49, _c(28_000_000)),
    # --- Stay Score 3 (Days 21-30): price grows 1.65%/day, TGE 48%, 26M cap ---
    21:  DayConfig(_p(0.00141), 48, _c(26_000_000)),
    22:  DayConfig(_p(0.00143), 48, _c(26_000_000)),
    23:  DayConfig(_p(0.00145), 48, _c(26_000_000)),
    24:  DayConfig(_p(0.00148), 48, _c(26_000_000)),
    25:  DayConfig(_p(0.00150), 48, _c(26_000_000)),
    26:  DayConfig(_p(0.00153), 48, _c(26_000_000)),
    27:  DayConfig(_p(0.00155), 48, _c(26_000_000)),
    28:  DayConfig(_p(0.00158), 48, _c(26_000_000)),
    29:  DayConfig(_p(0.00160), 48, _c(26_000_000)),
    30:  DayConfig(_p(0.00163), 48, _c(26_000_000)),
    # --- Stay Score 4 (Days 31-40): price grows 1.60%/day, TGE 47%, 24M cap ---
    31:  DayConfig(_p(0.00166), 47, _c(24_000_000)),
    32:  DayConfig(_p(0.00168), 47, _c(24_000_000)),
    33:  DayConfig(_p(0.00171), 47, _c(24_000_000)),
    34:  DayConfig(_p(0.00174), 47, _c(24_000_000)),
    35:  DayConfig(_p(0.00176), 47, _c(24_000_000)),
    36:  DayConfig(_p(0.00179), 47, _c(24_000_000)),
    37:  DayConfig(_p(0.00182), 47, _c(24_000_000)),
    38:  DayConfig(_p(0.00185), 47, _c(24_000_000)),
    39:  DayConfig(_p(0.00188), 47, _c(24_000_000)),
    40:  DayConfig(_p(0.00191), 47, _c(24_000_000)),
    # --- Stay Score 5 (Days 41-50): price grows 1.55%/day, TGE 46%, 22M cap ---
    41:  DayConfig(_p(0.00194), 46, _c(22_000_000)),
    42:  DayConfig(_p(0.00197), 46, _c(22_000_000)),
    43:  DayConfig(_p(0.00200), 46, _c(22_000_000)),
    44:  DayConfig(_p(0.00203), 46, _c(22_000_000)),
    45:  DayConfig(_p(0.00206), 46, _c(22_000_000)),
    46:  DayConfig(_p(0.00209), 46, _c(22_000_000)),
    47:  DayConfig(_p(0.00213), 46, _c(22_000_000)),
    48:  DayConfig(_p(0.00216), 46, _c(22_000_000)),
    49:  DayConfig(_p(0.00219), 46, _c(22_000_000)),
    50:  DayConfig(_p(0.00223), 46, _c(22_000_000)),
    # --- Stay Score 6 (Days 51-60): price grows 1.50%/day, TGE 45%, 20M cap ---
    51:  DayConfig(_p(0.00226), 45, _c(20_000_000)),
    52:  DayConfig(_p(0.00229), 45, _c(20_000_000)),
    53:  DayConfig(_p(0.00233), 45, _c(20_000_000)),
    54:  DayConfig(_p(0.00236), 45, _c(20_000_000)),
    55:  DayConfig(_p(0.00240), 45, _c(20_000_000)),
    56:  DayConfig(_p(0.00244), 45, _c(20_000_000)),
    57:  DayConfig(_p(0.00247), 45, _c(20_000_000)),
    58:  DayConfig(_p(0.00251), 45, _c(20_000_000)),
    59:  DayConfig(_p(0.00255), 45, _c(20_000_000)),
    60:  DayConfig(_p(0.00259), 45, _c(20_000_000)),
    # --- Stay Score 7 (Days 61-70): price grows 1.45%/day, TGE 44%, 18M cap ---
    61:  DayConfig(_p(0.00262), 44, _c(18_000_000)),
    62:  DayConfig(_p(0.00266), 44, _c(18_000_000)),
    63:  DayConfig(_p(0.00270), 44, _c(18_000_000)),
    64:  DayConfig(_p(0.00274), 44, _c(18_000_000)),
    65:  DayConfig(_p(0.00278), 44, _c(18_000_000)),
    66:  DayConfig(_p(0.00282), 44, _c(18_000_000)),
    67:  DayConfig(_p(0.00286), 44, _c(18_000_000)),
    68:  DayConfig(_p(0.00290), 44, _c(18_000_000)),
    69:  DayConfig(_p(0.00294), 44, _c(18_000_000)),
    70:  DayConfig(_p(0.00299), 44, _c(18_000_000)),
    # --- Stay Score 8 (Days 71-80): price grows 1.40%/day, TGE 43%, 16M cap ---
    71:  DayConfig(_p(0.00303), 43, _c(16_000_000)),
    72:  DayConfig(_p(0.00307), 43, _c(16_000_000)),
    73:  DayConfig(_p(0.00311), 43, _c(16_000_000)),
    74:  DayConfig(_p(0.00316), 43, _c(16_000_000)),
    75:  DayConfig(_p(0.00320), 43, _c(16_000_000)),
    76:  DayConfig(_p(0.00325), 43, _c(16_000_000)),
    77:  DayConfig(_p(0.00329), 43, _c(16_000_000)),
    78:  DayConfig(_p(0.00334), 43, _c(16_000_000)),
    79:  DayConfig(_p(0.00338), 43, _c(16_000_000)),
    80:  DayConfig(_p(0.00343), 43, _c(16_000_000)),
    # --- Stay Score 9 (Days 81-90): price grows 1.35%/day, TGE 42%, 14M cap ---
    81:  DayConfig(_p(0.00348), 42, _c(14_000_000)),
    82:  DayConfig(_p(0.00352), 42, _c(14_000_000)),
    83:  DayConfig(_p(0.00357), 42, _c(14_000_000)),
    84:  DayConfig(_p(0.00362), 42, _c(14_000_000)),
    85:  DayConfig(_p(0.00367), 42, _c(14_000_000)),
    86:  DayConfig(_p(0.00372), 42, _c(14_000_000)),
    87:  DayConfig(_p(0.00377), 42, _c(14_000_000)),
    88:  DayConfig(_p(0.00382), 42, _c(14_000_000)),
    89:  DayConfig(_p(0.00387), 42, _c(14_000_000)),
    90:  DayConfig(_p(0.00392), 42, _c(14_000_000)),
    # --- Stay Score 10 (Days 91-100): price grows 1.30%/day, TGE 41%, 12M cap ---
    91:  DayConfig(_p(0.00397), 41, _c(12_000_000)),
    92:  DayConfig(_p(0.00403), 41, _c(12_000_000)),
    93:  DayConfig(_p(0.00408), 41, _c(12_000_000)),
    94:  DayConfig(_p(0.00413), 41, _c(12_000_000)),
    95:  DayConfig(_p(0.00418), 41, _c(12_000_000)),
    96:  DayConfig(_p(0.00424), 41, _c(12_000_000)),
    97:  DayConfig(_p(0.00429), 41, _c(12_000_000)),
    98:  DayConfig(_p(0.00435), 41, _c(12_000_000)),
    99:  DayConfig(_p(0.00441), 41, _c(12_000_000)),
    100: DayConfig(_p(0.00446), 41, _c(12_000_000)),
    # --- Stay Score 11 (Days 101-110): price grows 1.25%/day, TGE 40%, 10M cap ---
    101: DayConfig(_p(0.00452), 40, _c(10_000_000)),
    102: DayConfig(_p(0.00458), 40, _c(10_000_000)),
    103: DayConfig(_p(0.00463), 40, _c(10_000_000)),
    104: DayConfig(_p(0.00469), 40, _c(10_000_000)),
    105: DayConfig(_p(0.00475), 40, _c(10_000_000)),
    106: DayConfig(_p(0.00481), 40, _c(10_000_000)),
    107: DayConfig(_p(0.00487), 40, _c(10_000_000)),
    108: DayConfig(_p(0.00493), 40, _c(10_000_000)),
    109: DayConfig(_p(0.00499), 40, _c(10_000_000)),
    110: DayConfig(_p(0.00505), 40, _c(10_000_000)),
    # --- Stay Score 12 (Days 111-120): price grows 1.20%/day, TGE 39%, 8M cap ---
    111: DayConfig(_p(0.00512), 39, _c(8_000_000)),
    112: DayConfig(_p(0.00518), 39, _c(8_000_000)),
    113: DayConfig(_p(0.00524), 39, _c(8_000_000)),
    114: DayConfig(_p(0.00530), 39, _c(8_000_000)),
    115: DayConfig(_p(0.00537), 39, _c(8_000_000)),
    116: DayConfig(_p(0.00543), 39, _c(8_000_000)),
    117: DayConfig(_p(0.00549), 39, _c(8_000_000)),
    118: DayConfig(_p(0.00556), 39, _c(8_000_000)),
    119: DayConfig(_p(0.00563), 39, _c(8_000_000)),
    120: DayConfig(_p(0.00569), 39, _c(8_000_000)),
    # --- Stay Score 13 (Days 121-130): price grows 1.15%/day, TGE 38%, 6M cap ---
    121: DayConfig(_p(0.00576), 38, _c(6_000_000)),
    122: DayConfig(_p(0.00583), 38, _c(6_000_000)),
    123: DayConfig(_p(0.00589), 38, _c(6_000_000)),
    124: DayConfig(_p(0.00596), 38, _c(6_000_000)),
    125: DayConfig(_p(0.00603), 38, _c(6_000_000)),
    126: DayConfig(_p(0.00610), 38, _c(6_000_000)),
    127: DayConfig(_p(0.00617), 38, _c(6_000_000)),
    128: DayConfig(_p(0.00624), 38, _c(6_000_000)),
    129: DayConfig(_p(0.00631), 38, _c(6_000_000)),
    130: DayConfig(_p(0.00638), 38, _c(6_000_000)),
    # --- Stay Score 14 (Days 131-140): price grows 1.10%/day, TGE 37%, 4M cap ---
    131: DayConfig(_p(0.00645), 37, _c(4_000_000)),
    132: DayConfig(_p(0.00653), 37, _c(4_000_000)),
    133: DayConfig(_p(0.00660), 37, _c(4_000_000)),
    134: DayConfig(_p(0.00667), 37, _c(4_000_000)),
    135: DayConfig(_p(0.00674), 37, _c(4_000_000)),
    136: DayConfig(_p(0.00682), 37, _c(4_000_000)),
    137: DayConfig(_p(0.00689), 37, _c(4_000_000)),
    138: DayConfig(_p(0.00697), 37, _c(4_000_000)),
    139: DayConfig(_p(0.00705), 37, _c(4_000_000)),
    140: DayConfig(_p(0.00712), 37, _c(4_000_000)),
    # --- Stay Score 15 (Days 141-150): price grows 1.05%/day, TGE 36%, 2M cap ---
    141: DayConfig(_p(0.00720), 36, _c(2_000_000)),
    142: DayConfig(_p(0.00727), 36, _c(2_000_000)),
    143: DayConfig(_p(0.00735), 36, _c(2_000_000)),
    144: DayConfig(_p(0.00743), 36, _c(2_000_000)),
    145: DayConfig(_p(0.00750), 36, _c(2_000_000)),
    146: DayConfig(_p(0.00758), 36, _c(2_000_000)),
    147: DayConfig(_p(0.00766), 36, _c(2_000_000)),
    148: DayConfig(_p(0.00774), 36, _c(2_000_000)),
    149: DayConfig(_p(0.00782), 36, _c(2_000_000)),
    150: DayConfig(_p(0.00791), 36, _c(2_000_000)),
}
# fmt: on


def _get_presale_day() -> int:
    """Return the current presale day number (1-based)."""
    start = date.fromisoformat(settings.presale_start_date)
    today = datetime.now(timezone.utc).date()
    return (today - start).days + 1


def get_today_token_data() -> DayConfig:
    day = _get_presale_day()
    if day < 1:
        return DayConfig(0, 0, 0)
    elif day > TOTAL_DAYS:
        return SCHEDULE[TOTAL_DAYS]
    return SCHEDULE[day]



TOTAL_DAYS = len(SCHEDULE)  # 150

from dataclasses import dataclass
from typing import Optional

from .models import Trade


@dataclass
class Classified:
    trade: Trade
    status: str  # "profitable" | "unprofitable" | "breakeven" | "no_prior"
    buy: Optional[Trade]
    gross_profit: Optional[int]
    holding_years: Optional[float]
    annualized_return: Optional[float]


RESELL_TYPES = {"Resale", "Sub Sale"}


def classify(trades: list[Trade]) -> list[Classified]:
    """Pair trades within the same (block, floor, area, unit_type) bucket.

    URA does not publish unit numbers, so multiple physical units share a
    bucket. To avoid spurious pairs, only Resale / Sub Sale trades are
    treated as the "sell" side; each prior trade can be used as a "buy"
    at most once (FIFO: earliest unused prior trade matches the earliest
    sell).
    """
    out: list[Classified] = []
    buckets: dict[tuple, list[Trade]] = {}
    for t in trades:
        buckets.setdefault(t.pair_key, []).append(t)

    for group in buckets.values():
        group.sort(key=lambda t: t.contract_date)
        used_as_buy = [False] * len(group)
        pair_buy_idx: dict[int, int] = {}

        for i, t in enumerate(group):
            if t.sale_type not in RESELL_TYPES:
                continue
            for j in range(i):
                if used_as_buy[j]:
                    continue
                if group[j].contract_date >= t.contract_date:
                    continue
                used_as_buy[j] = True
                pair_buy_idx[i] = j
                break

        for i, t in enumerate(group):
            if i in pair_buy_idx:
                buy = group[pair_buy_idx[i]]
                profit = t.price_sgd - buy.price_sgd
                years = (t.contract_date - buy.contract_date).days / 365.25
                ann = (t.price_sgd / buy.price_sgd) ** (1 / years) - 1 if years > 0 else None
                if profit > 0:
                    status = "profitable"
                elif profit < 0:
                    status = "unprofitable"
                else:
                    status = "breakeven"
                out.append(Classified(t, status, buy, profit, years, ann))
            else:
                out.append(Classified(t, "no_prior", None, None, None, None))
    return out

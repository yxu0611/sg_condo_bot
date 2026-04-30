"""Condo configuration registry.

A ``Condo`` captures everything project-specific that the fetchers and
renderers need: the URA project name (used by URA + CSV filtering), the
EdgeProp asset id and listing slug, the SquareFoot URL slug, and a few
display fields. Add a new condo by appending to ``REGISTRY``; for ad-hoc
queries use :func:`get` with a name string and the URA / CSV path will
still work (other sources may be unavailable for that condo).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Condo:
    key: str
    name: str
    ura_project_name: str
    edgeprop_asset_id: Optional[int] = None
    edgeprop_slug: Optional[str] = None
    squarefoot_slug: Optional[str] = None
    district: Optional[str] = None
    tenure: Optional[str] = None
    top_year: Optional[int] = None
    units: Optional[int] = None
    location: Optional[str] = None

    @property
    def subtitle(self) -> str:
        bits = [b for b in (self.location, self.district, self.tenure) if b]
        if self.top_year:
            bits.append(f"TOP {self.top_year}")
        if self.units:
            bits.append(f"{self.units:,} units")
        return " · ".join(bits)


REGISTRY: dict[str, Condo] = {
    "florence": Condo(
        key="florence",
        name="The Florence Residences",
        ura_project_name="FLORENCE RESIDENCES",
        edgeprop_asset_id=291412,
        edgeprop_slug="The-Florence-Residences/m_2156876",
        squarefoot_slug="florence-residences-singapore",
        location="Hougang Ave 2",
        district="D19",
        tenure="99-yr from 2018",
        top_year=2022,
        units=1410,
    ),
    "parktown": Condo(
        key="parktown",
        name="Parktown Residence",
        ura_project_name="PARKTOWN RESIDENCE",
        edgeprop_asset_id=295529,
        edgeprop_slug="Parktown-Residence",
        squarefoot_slug=None,
        location="Tampines Street 62",
        district="D18",
        tenure="99-yr from 2023",
        top_year=None,  # not yet TOP (launched 2025)
        units=1193,
    ),
}


def get(key_or_name: str) -> Condo:
    """Return a registered Condo by short key, or build an ad-hoc one.

    The ad-hoc Condo only carries the URA project name, so EdgeProp /
    SquareFoot fetches will fail unless the caller supplies the missing
    slugs explicitly.
    """
    k = key_or_name.strip().lower()
    if k in REGISTRY:
        return REGISTRY[k]
    return Condo(
        key=k.replace(" ", "_"),
        name=key_or_name.title(),
        ura_project_name=key_or_name.upper(),
    )


def list_keys() -> list[str]:
    return sorted(REGISTRY.keys())

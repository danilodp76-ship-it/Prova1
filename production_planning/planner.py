"""Core logic for production planning and reporting."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional, Sequence, Tuple

import pandas as pd


class BillOfMaterialsError(RuntimeError):
    """Raised when the bill of materials contains invalid data."""


@dataclass
class BOMItem:
    parent: str
    component: str
    quantity: float


class BillOfMaterials:
    """Utility to navigate a bill of materials graph."""

    def __init__(self, items: Sequence[BOMItem]):
        self._children: Dict[str, List[Tuple[str, float]]] = {}
        for item in items:
            if item.quantity < 0:
                raise BillOfMaterialsError(
                    f"Negative quantity for component {item.component} under {item.parent}: {item.quantity}"
                )
            self._children.setdefault(item.parent, []).append((item.component, item.quantity))

    def explode(self, parent: str, quantity: float) -> Iterator[Tuple[str, float]]:
        """Yield flattened components for ``parent`` scaled by ``quantity``.

        The explosion traverses the BOM depth-first. A component is yielded once for
        every occurrence in the structure, scaled by the cumulative quantity required.
        """

        stack: List[Tuple[str, float, Iterator[Tuple[str, float]]]] = []
        visited: List[str] = []

        def push(code: str, qty: float) -> None:
            if code in visited:
                path = " -> ".join(visited + [code])
                raise BillOfMaterialsError(f"Cycle detected in BOM: {path}")
            visited.append(code)
            stack.append((code, qty, iter(self._children.get(code, []))))

        push(parent, quantity)

        while stack:
            code, qty, iterator = stack[-1]
            try:
                component, component_qty = next(iterator)
            except StopIteration:
                stack.pop()
                visited.pop()
                continue

            total_qty = qty * component_qty
            yield component, total_qty
            push(component, total_qty)


def read_shipments(
    path: str,
    *,
    code_column: str,
    quantity_column: str,
    vl_spedibile_column: str,
    vl_non_spedibile_column: str,
    produced_quantity_column: Optional[str] = None,
    sheet_name: str | int | None = 0,
) -> pd.DataFrame:
    """Load the shipments sheet with standardised column names."""

    df = pd.read_excel(path, sheet_name=sheet_name)

    required_columns = {code_column, quantity_column, vl_spedibile_column, vl_non_spedibile_column}
    missing = required_columns.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in shipments file: {sorted(missing)}")

    columns = {
        code_column: "codice",
        quantity_column: "quantita",
        vl_spedibile_column: "vl_spedibile",
        vl_non_spedibile_column: "vl_non_spedibile",
    }
    if produced_quantity_column:
        if produced_quantity_column not in df.columns:
            raise ValueError(f"Produced quantity column '{produced_quantity_column}' not found in shipments file")
        columns[produced_quantity_column] = "quantita_prodotta"

    normalized = df.rename(columns=columns)
    normalized["quantita"] = pd.to_numeric(normalized["quantita"], errors="coerce").fillna(0.0)
    normalized["vl_spedibile"] = pd.to_numeric(normalized["vl_spedibile"], errors="coerce").fillna(0.0)
    normalized["vl_non_spedibile"] = pd.to_numeric(normalized["vl_non_spedibile"], errors="coerce").fillna(0.0)
    if "quantita_prodotta" in normalized:
        normalized["quantita_prodotta"] = pd.to_numeric(
            normalized["quantita_prodotta"], errors="coerce"
        ).fillna(0.0)

    normalized["fatturato"] = normalized["vl_spedibile"] + normalized["vl_non_spedibile"]
    return normalized


def read_bom(
    path: str,
    *,
    parent_column: str,
    component_column: str,
    quantity_column: str,
    sheet_name: str | int | None = 0,
) -> BillOfMaterials:
    """Load the bill of materials from an Excel file."""

    df = pd.read_excel(path, sheet_name=sheet_name)

    required_columns = {parent_column, component_column, quantity_column}
    missing = required_columns.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in BOM file: {sorted(missing)}")

    items = [
        BOMItem(
            parent=str(row[parent_column]).strip(),
            component=str(row[component_column]).strip(),
            quantity=float(row[quantity_column]),
        )
        for _, row in df.iterrows()
        if pd.notna(row[parent_column]) and pd.notna(row[component_column])
    ]

    return BillOfMaterials(items)


def read_area_mapping(
    path: str,
    *,
    code_column: str,
    area_column: str,
    sheet_name: str | int | None = 0,
) -> Mapping[str, str]:
    """Load the mapping between product codes and production areas."""

    df = pd.read_excel(path, sheet_name=sheet_name)
    required_columns = {code_column, area_column}
    missing = required_columns.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in area mapping file: {sorted(missing)}")

    mapping: Dict[str, str] = {}
    for _, row in df.iterrows():
        code = row[code_column]
        area = row[area_column]
        if pd.isna(code) or pd.isna(area):
            continue
        mapping[str(code).strip()] = str(area).strip()
    return mapping


@dataclass
class ProductionPlanResult:
    plan: pd.DataFrame
    shipments: pd.DataFrame


class ProductionPlanner:
    """Compute production plans and progress reports."""

    def __init__(
        self,
        *,
        bom: BillOfMaterials,
        area_mapping: Mapping[str, str],
        missing_area_label: str = "Senza area",
    ) -> None:
        self._bom = bom
        self._area_mapping = dict(area_mapping)
        self._missing_area_label = missing_area_label

    def build_plan(
        self,
        shipments: pd.DataFrame,
        *,
        include_parent_codes: bool = True,
    ) -> ProductionPlanResult:
        """Build a production plan grouped by area and component code."""

        area_totals: MutableMapping[Tuple[str, str], float] = {}

        def add_to_plan(code: str, quantity: float) -> None:
            if not code:
                return
            area = self._area_mapping.get(code, self._missing_area_label)
            key = (area, code)
            area_totals[key] = area_totals.get(key, 0.0) + quantity

        for _, row in shipments.iterrows():
            parent_code = str(row["codice"]).strip()
            quantity = float(row["quantita"])
            if not parent_code:
                continue
            if include_parent_codes:
                add_to_plan(parent_code, quantity)
            for component, component_qty in self._bom.explode(parent_code, quantity):
                add_to_plan(component, component_qty)

        if area_totals:
            data = [
                {"area": area, "codice": code, "quantita_richiesta": qty}
                for (area, code), qty in sorted(area_totals.items())
            ]
        else:
            data = []
        plan_df = pd.DataFrame(data)
        return ProductionPlanResult(plan=plan_df, shipments=shipments.copy())

    @staticmethod
    def compute_progress(shipments: pd.DataFrame) -> pd.DataFrame:
        """Compute production progress and revenue metrics from shipments data."""

        columns = [col for col in ["codice", "quantita", "fatturato"] if col in shipments.columns]
        if "quantita_prodotta" in shipments.columns:
            columns.append("quantita_prodotta")
            shipments = shipments.assign(
                avanzamento_percentuale=lambda df: (df["quantita_prodotta"] / df["quantita"].where(df["quantita"] != 0, 1))
                .fillna(0.0)
                .clip(lower=0)
                * 100
            )
            columns.append("avanzamento_percentuale")
        return shipments[columns]

    def progress_by_area(self, shipments: pd.DataFrame) -> pd.DataFrame:
        """Aggregate shipment progress and revenue by area of the parent codes."""

        shipments = shipments.copy()
        shipments["area"] = shipments["codice"].map(self._area_mapping).fillna(self._missing_area_label)

        agg_columns = {
            "quantita": "sum",
            "fatturato": "sum",
        }
        if "quantita_prodotta" in shipments.columns:
            agg_columns["quantita_prodotta"] = "sum"

        summary = shipments.groupby("area", dropna=False).agg(agg_columns).reset_index()
        if "quantita_prodotta" in summary.columns:
            summary["avanzamento_percentuale"] = (
                summary["quantita_prodotta"] / summary["quantita"].where(summary["quantita"] != 0, 1)
            ).fillna(0.0) * 100
        return summary


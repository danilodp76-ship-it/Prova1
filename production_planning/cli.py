"""Command line interface for the production planning utilities."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from .planner import (
    BillOfMaterials,
    ProductionPlanner,
    ProductionPlanResult,
    read_area_mapping,
    read_bom,
    read_shipments,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Genera piani di produzione e report di avanzamento partendo "
            "dai file Excel del prospetto spedizioni, della distinta base "
            "e della mappatura delle aree di lavoro."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser(
        "plan",
        help="Genera un piano di produzione aggregato per area di lavoro.",
    )
    _add_common_file_arguments(plan_parser)
    plan_parser.add_argument(
        "--include-parent-codes",
        action="store_true",
        help="Include i codici padre direttamente nel piano, se assegnati a un'area.",
    )
    plan_parser.add_argument(
        "--output",
        type=Path,
        help=(
            "File di destinazione opzionale. L'estensione determina il formato: "
            "CSV (.csv) oppure Excel (.xlsx, .xlsm)."
        ),
    )
    plan_parser.add_argument(
        "--sheet-name",
        default=0,
        help="Nome o indice del foglio da leggere nei file Excel (default: primo foglio).",
    )

    report_parser = subparsers.add_parser(
        "report",
        help="Mostra un report di avanzamento e fatturato basato sul prospetto spedizioni.",
    )
    _add_common_file_arguments(report_parser, include_bom=False, include_areas=True)
    report_parser.add_argument(
        "--sheet-name",
        default=0,
        help="Nome o indice del foglio da leggere nel prospetto spedizioni e nella mappatura aree.",
    )
    report_parser.add_argument(
        "--group-by-area",
        action="store_true",
        help="Aggrega l'avanzamento e il fatturato per area di lavoro.",
    )

    return parser


def _add_common_file_arguments(
    parser: argparse.ArgumentParser,
    *,
    include_bom: bool = True,
    include_areas: bool = True,
) -> None:
    parser.add_argument("shipments", type=Path, help="Percorso del file 'Prospetto spedizioni'.")
    parser.add_argument(
        "--code-column",
        default="Codice",
        help="Nome della colonna contenente il codice del prodotto nel prospetto spedizioni.",
    )
    parser.add_argument(
        "--quantity-column",
        default="Quantita",
        help="Nome della colonna con la quantità ordinata nel prospetto spedizioni.",
    )
    parser.add_argument(
        "--vl-spedibile-column",
        default="VL spedibile",
        help="Nome della colonna con il valore del materiale spedibile.",
    )
    parser.add_argument(
        "--vl-non-spedibile-column",
        default="VL non spedibile",
        help="Nome della colonna con il valore del materiale non ancora spedibile.",
    )
    parser.add_argument(
        "--produced-column",
        default=None,
        help="Nome della colonna con la quantità prodotta (opzionale).",
    )
    if include_bom:
        parser.add_argument("bom", type=Path, help="Percorso del file 'Esplosione quantità DB'.")
        parser.add_argument(
            "--bom-parent-column",
            default="Codice padre",
            help="Nome della colonna con il codice padre nella distinta base.",
        )
        parser.add_argument(
            "--bom-component-column",
            default="Codice componente",
            help="Nome della colonna con il codice figlio nella distinta base.",
        )
        parser.add_argument(
            "--bom-quantity-column",
            default="Quantita",
            help="Nome della colonna con la quantità richiesta del componente.",
        )
    if include_areas:
        parser.add_argument("areas", type=Path, help="Percorso del file con la mappatura codice-area.")
        parser.add_argument(
            "--area-code-column",
            default="Codice",
            help="Nome della colonna con il codice prodotto nel file di mappatura delle aree.",
        )
        parser.add_argument(
            "--area-name-column",
            default="Area",
            help="Nome della colonna che contiene l'area di lavoro.",
        )


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "plan":
        plan_result = _handle_plan(args)
        _display_plan(plan_result, output=args.output)
        return 0

    if args.command == "report":
        _handle_report(args)
        return 0

    parser.error("Comando non riconosciuto")
    return 2


def _handle_plan(args: argparse.Namespace) -> ProductionPlanResult:
    shipments = read_shipments(
        args.shipments,
        code_column=args.code_column,
        quantity_column=args.quantity_column,
        vl_spedibile_column=args.vl_spedibile_column,
        vl_non_spedibile_column=args.vl_non_spedibile_column,
        produced_quantity_column=args.produced_column,
        sheet_name=args.sheet_name,
    )
    bom = read_bom(
        args.bom,
        parent_column=args.bom_parent_column,
        component_column=args.bom_component_column,
        quantity_column=args.bom_quantity_column,
        sheet_name=args.sheet_name,
    )
    areas = read_area_mapping(
        args.areas,
        code_column=args.area_code_column,
        area_column=args.area_name_column,
        sheet_name=args.sheet_name,
    )

    planner = ProductionPlanner(bom=bom, area_mapping=areas)
    return planner.build_plan(shipments, include_parent_codes=args.include_parent_codes)


def _display_plan(result: ProductionPlanResult, output: Optional[Path]) -> None:
    plan = result.plan
    if plan.empty:
        print("Nessun dato da mostrare nel piano di produzione.")
    else:
        print("Piano di produzione aggregato per area di lavoro:")
        print(plan.to_string(index=False))

    if output:
        if output.suffix.lower() in {".xlsx", ".xlsm"}:
            plan.to_excel(output, index=False)
        elif output.suffix.lower() == ".csv":
            plan.to_csv(output, index=False)
        else:
            raise ValueError(
                "Formato di output non supportato. Utilizzare estensioni .csv, .xlsx o .xlsm."
            )
        print(f"Piano salvato in: {output}")


def _handle_report(args: argparse.Namespace) -> None:
    shipments = read_shipments(
        args.shipments,
        code_column=args.code_column,
        quantity_column=args.quantity_column,
        vl_spedibile_column=args.vl_spedibile_column,
        vl_non_spedibile_column=args.vl_non_spedibile_column,
        produced_quantity_column=args.produced_column,
        sheet_name=args.sheet_name,
    )

    areas = read_area_mapping(
        args.areas,
        code_column=args.area_code_column,
        area_column=args.area_name_column,
        sheet_name=args.sheet_name,
    )
    planner = ProductionPlanner(
        bom=BillOfMaterials([]),  # Non necessario per il report, ma mantiene l'interfaccia coerente.
        area_mapping=areas,
    )

    progress = ProductionPlanner.compute_progress(shipments)
    print("Report di avanzamento per codice padre:")
    print(progress.to_string(index=False))

    if args.group_by_area:
        summary = planner.progress_by_area(shipments)
        print("\nAvanzamento e fatturato per area di lavoro:")
        print(summary.to_string(index=False))


if __name__ == "__main__":  # pragma: no cover - support direct execution
    raise SystemExit(main())

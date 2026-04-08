"""
IFC Checker Module
==================
Validates IFC model files against Sydney Metro BIM requirements.
Checks schema version (IFC4X3) and required property sets
(SM_PROJECT, SM_ASSET, SM_LOCATION).
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import List

from modules import ModuleResult

# ---------------------------------------------------------------------------
# Required properties per group (fallback when no EIR schema loaded)
# ---------------------------------------------------------------------------

LOCATION_REQUIRED = [
    "SM_LocationFacilityCode", "SM_LocationFacilityDesc",
    "SM_LocationLevelCode", "SM_LocationLevelDesc",
    "SM_LocationRoomSpaceInstNumber", "SM_LocationRoomSpaceName",
    "SM_LocationRoomSpaceTypeCode", "SM_LocationRoomSpaceTypeDesc",
    "SM_LocationZoneCode", "SM_LocationZoneDesc",
    "TfNSW_AssetLocationCode", "TfNSW_AssetLocationDesc",
    "TfNSW_AssetLocationID", "TfNSW_ParentAssetLocationCode",
    "TfNSW_ParentAssetLocationID", "TfNSW_UniClassAssetLocationCode",
    "TfNSW_UniClassAssetLocationTitle", "TfNSW_ProjectAssetID",
    "TfNSW_ParentProjectAssetID",
    "Uniclass_CoCode", "Uniclass_CoTitle",
    "Uniclass_EnCode", "Uniclass_EnTitle",
    "Uniclass_SLCode", "Uniclass_SLTitle",
    "Facility Code", "FacilityDesc",
]

PROJECT_REQUIRED = [
    "GLOBALID", "Project_Contract_Code",
    "SM_LocationCorridorCode", "SM_LocationCorridorDesc",
    "SM_LocationNetworkCode", "SM_LocationNetworkDesc",
    "SM_LocationSiteCode", "SM_LocationSiteDesc",
    "SM_ModelOriginator", "SM_ModelCheck", "SM_ModelApprover",
    "SM_ModelRevisionDate", "SM_ModelRevisionNumber",
    "tbAEODisciplineCode", "tbAEODisciplineDesc",
    "tbAEOSubDiscCode", "tbAEOSubDiscDesc",
    "tbAEOSuppCode", "tbAEOSuppName", "tbCoordSys",
    "tbDesignCompCode", "tbDesignCompName",
    "TfNSW_DocumentNumber", "TfNSW_DocumentTitle",
    "TfNSW_ProjectandContractName", "TfNSW_ProjectMilestoneDesc",
    "TfNSW_StateDesc", "TfNSW_SuitabilityDesc", "TfNSW_DocumentNo",
]

ASSET_REQUIRED = [
    "GUID", "GLOBALID", "End Latitude", "End Longitude",
    "SM_ActivityCode", "SM_ActivityName",
    "SM_CBS_ID", "SM_SBS_ID", "SM_WBS",
    "Start Latitude", "Start Longitude",
    "TfNSW_ AssetCode", "TfNSW_AssetDescription",
    "TfNSW_AssetID", "TfNSW_AssetInstance",
    "TfNSW_AssetMaintainerOrgName", "TfNSW_AssetOperatorOrgName",
    "TfNSW_AssetOwnerOrgName", "TfNSW_AssetStatusCode",
    "TfNSW_AssetTypeCode", "TfNSW_AssetTypeConfigCode",
    "TfNSW_AssetTypeConfigDesc", "TfNSW_DisciplineCode",
    "TfNSW_EndKm", "TfNSW_MMIFlag", "TfNSW_GPSCoordinates",
    "TfNSW_ParentAssetCode", "TfNSW_ParentAssetID",
    "TfNSW_StartKm", "TfNSW_SubDisciplineCode",
    "TfNSW_UniclassAssetCode", "TfNSW_UniclassAssetTitle",
    "Uniclass_EFCode", "Uniclass_EFTitle",
    "Uniclass_PrCode", "Uniclass_PrTitle",
    "Uniclass_SsCode", "Uniclass_SsTitle",
]

NA_ALLOWED_PROPERTIES = {
    "SM_LocationLevelCode", "SM_LocationLevelDesc",
    "SM_LocationRoomSpaceInstNumber", "SM_LocationRoomSpaceName",
    "SM_LocationRoomSpaceTypeCode", "SM_LocationRoomSpaceTypeDesc",
    "End Latitude", "End Longitude",
    "SM_ActivityCode", "SM_ActivityName",
}

REQUIRED_EXACT_VALUES = {"tbCoordSys": "GDA2020/MGA zone 56"}
MIN_LENGTH_RULES = {"TfNSW_DocumentNo": 36}


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _extract_schema(text: str) -> str:
    m = re.search(r"FILE_SCHEMA\s*\(\s*\((.*?)\)\s*\)", text, re.I | re.DOTALL)
    if not m:
        return ""
    return ", ".join(re.findall(r"'([^']+)'", m.group(1)))


def _extract_properties(text: str) -> dict[str, list[str | None]]:
    props: dict[str, list[str | None]] = {}
    pat = re.compile(
        r"IFCPROPERTYSINGLEVALUE\(\s*'(?P<name>[^']+)'\s*,\s*[^,]*,\s*(?P<value>.+?)\s*,\s*\$\s*\)\s*;",
        re.I,
    )
    for line in text.splitlines():
        m = pat.search(line)
        if not m:
            continue
        name = m.group("name").strip()
        raw = m.group("value").strip()
        props.setdefault(name, []).append(_norm_value(raw))
    return props


def _norm_value(raw: str) -> str | None:
    if raw == "$":
        return None
    m = re.match(r"[A-Z0-9_]+\('(.+)'\)", raw, re.I)
    if m:
        return m.group(1).strip()
    m = re.match(r"'(.+)'", raw)
    if m:
        return m.group(1).strip()
    return raw.strip()


def _has_valid(values: list[str | None]) -> bool:
    return any(v is not None and v.strip() for v in values)


def _check_rules(prop: str, values: list[str | None]) -> str | None:
    non_empty = [v.strip() for v in values if v is not None and v.strip()]
    if not non_empty:
        return None
    if prop in REQUIRED_EXACT_VALUES:
        expected = REQUIRED_EXACT_VALUES[prop]
        if all(v.lower() != expected.lower() for v in non_empty):
            unique = list(dict.fromkeys(non_empty))
            return f"expected '{expected}', found '{', '.join(unique)}'"
    if prop in MIN_LENGTH_RULES:
        req = MIN_LENGTH_RULES[prop]
        if all(len(v) != req for v in non_empty):
            return f"must be length {req}, found {', '.join(str(len(v)) for v in non_empty)}"
    if prop not in NA_ALLOWED_PROPERTIES:
        if any(v.upper() == "N/A" for v in non_empty):
            return "contains disallowed N/A"
    return None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_group(
    group_name: str,
    required: list[str],
    props: dict[str, list[str | None]],
) -> tuple[bool, list[str], list[str], list[str]]:
    missing, empty, invalid = [], [], []
    for p in required:
        if p not in props:
            missing.append(p)
            continue
        if not _has_valid(props[p]):
            empty.append(p)
            continue
        issue = _check_rules(p, props[p])
        if issue:
            invalid.append(f"{p}: {issue}")
    passed = not missing and not empty and not invalid
    return passed, missing, empty, invalid


def _validate_ifc(ifc_path: Path, result: ModuleResult, groups=None) -> None:
    fname = ifc_path.name
    try:
        text = ifc_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        result.add_finding(fname, "Open file", "FAIL", f"Cannot read: {exc}")
        return

    # Schema check
    schema = _extract_schema(text)
    if "IFC4X3" in schema.upper():
        result.add_finding(fname, "IFC Schema Version", "PASS", f"Detected: {schema}")
    else:
        result.add_finding(
            fname, "IFC Schema Version", "FAIL",
            f"Expected IFC4X3, found: {schema or 'not detected'}"
        )

    props = _extract_properties(text)

    if groups is None:
        groups = [
            ("SM_PROJECT", PROJECT_REQUIRED),
            ("SM_ASSET", ASSET_REQUIRED),
            ("SM_LOCATION", LOCATION_REQUIRED),
        ]

    for gname, required in groups:
        passed, missing, empty, invalid = _validate_group(gname, required, props)
        if passed:
            result.add_finding(fname, gname, "PASS", "All required properties present with values.")
        else:
            details = []
            if missing:
                details.append(f"Missing: {', '.join(missing[:10])}")
                if len(missing) > 10:
                    details.append(f"  ...and {len(missing)-10} more missing")
            if empty:
                details.append(f"Empty: {', '.join(empty[:10])}")
            if invalid:
                details.append(f"Invalid: {'; '.join(invalid[:5])}")
            result.add_finding(fname, gname, "FAIL", " | ".join(details))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(input_folder: Path, output_folder: Path, log_callback=None,
        bim_schema=None) -> ModuleResult:
    """
    Scan *input_folder* for .ifc files and validate each.
    If *bim_schema* (a BIMSchemaConfig) is provided, required properties
    are derived from the schema.  Otherwise the hardcoded fallback lists
    are used.
    Returns a ModuleResult with granular findings and summary.
    """
    result = ModuleResult(module_name="IFC Model")

    ifc_files = sorted(input_folder.glob("*.ifc"))
    ifc_files = [f for f in ifc_files if f.is_file()]

    if not ifc_files:
        result.build_granular_text()
        result.build_summary()
        if log_callback:
            log_callback("[IFC] No .ifc files found.")
        return result

    # Build property-set requirements from EIR schema or fallback
    if bim_schema and bim_schema.ifc_property_sets:
        groups = []
        _PS_MAP = {
            "SM_Project": "SM_PROJECT",
            "SM_Asset": "SM_ASSET",
            "SM_Location": "SM_LOCATION",
        }
        for ps_raw, attrs in bim_schema.ifc_property_sets.items():
            ps_key = ps_raw.strip()
            display = _PS_MAP.get(ps_key, ps_key)
            groups.append((display, attrs))
        if log_callback:
            total = sum(len(a) for _, a in groups)
            log_callback(f"[IFC] Using EIR schema: {total} properties across {len(groups)} property sets")
    else:
        groups = [
            ("SM_PROJECT", PROJECT_REQUIRED),
            ("SM_ASSET", ASSET_REQUIRED),
            ("SM_LOCATION", LOCATION_REQUIRED),
        ]
        if log_callback and bim_schema is None:
            log_callback("[IFC] No EIR schema — using built-in property lists")

    for ifc_file in ifc_files:
        result.files_checked.append(ifc_file.name)
        if log_callback:
            log_callback(f"[IFC] Checking: {ifc_file.name}")
        _validate_ifc(ifc_file, result, groups)

    result.build_granular_text()
    result.build_summary()

    # Write granular findings
    findings_path = output_folder / "ifc_findings.txt"
    findings_path.write_text(result.granular_text, encoding="utf-8")

    # Write module summary
    summary_path = output_folder / "ifc_summary.txt"
    summary_path.write_text(result.summary, encoding="utf-8")

    # Write CSV
    csv_path = output_folder / "ifc_validation_results.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "check", "status", "details"])
        w.writeheader()
        for f in result.findings:
            w.writerow({"file": f.file_name, "check": f.check_name,
                         "status": f.status, "details": f.detail})

    if log_callback:
        log_callback(f"[IFC] Done — {'PASS' if result.overall_passed else 'FAIL'}")

    return result

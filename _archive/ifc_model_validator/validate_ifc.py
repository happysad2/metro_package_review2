import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path


LOCATION_REQUIRED = [
    "SM_LocationFacilityCode",
    "SM_LocationFacilityDesc",
    "SM_LocationLevelCode",
    "SM_LocationLevelDesc",
    "SM_LocationRoomSpaceInstNumber",
    "SM_LocationRoomSpaceName",
    "SM_LocationRoomSpaceTypeCode",
    "SM_LocationRoomSpaceTypeDesc",
    "SM_LocationZoneCode",
    "SM_LocationZoneDesc",
    "TfNSW_AssetLocationCode",
    "TfNSW_AssetLocationDesc",
    "TfNSW_AssetLocationID",
    "TfNSW_ParentAssetLocationCode",
    "TfNSW_ParentAssetLocationID",
    "TfNSW_UniClassAssetLocationCode",
    "TfNSW_UniClassAssetLocationTitle",
    "TfNSW_ProjectAssetID",
    "TfNSW_ParentProjectAssetID",
    "Uniclass_CoCode",
    "Uniclass_CoTitle",
    "Uniclass_EnCode",
    "Uniclass_EnTitle",
    "Uniclass_SLCode",
    "Uniclass_SLTitle",
    "Facility Code",
    "FacilityDesc",
]

PROJECT_REQUIRED = [
    "GLOBALID",
    "Project_Contract_Code",
    "SM_LocationCorridorCode",
    "SM_LocationCorridorDesc",
    "SM_LocationNetworkCode",
    "SM_LocationNetworkDesc",
    "SM_LocationSiteCode",
    "SM_LocationSiteDesc",
    "SM_ModelOriginator",
    "SM_ModelCheck",
    "SM_ModelApprover",
    "SM_ModelRevisionDate",
    "SM_ModelRevisionNumber",
    "tbAEODisciplineCode",
    "tbAEODisciplineDesc",
    "tbAEOSubDiscCode",
    "tbAEOSubDiscDesc",
    "tbAEOSuppCode",
    "tbAEOSuppName",
    "tbCoordSys",
    "tbDesignCompCode",
    "tbDesignCompName",
    "TfNSW_DocumentNumber",
    "TfNSW_DocumentTitle",
    "TfNSW_ProjectandContractName",
    "TfNSW_ProjectMilestoneDesc",
    "TfNSW_StateDesc",
    "TfNSW_SuitabilityDesc",
    "TfNSW_DocumentNo",
]

ASSET_REQUIRED = [
    "GUID",
    "GLOBALID",
    "End Latitude",
    "End Longitude",
    "SM_ActivityCode",
    "SM_ActivityName",
    "SM_CBS_ID",
    "SM_SBS_ID",
    "SM_WBS",
    "Start Latitude",
    "Start Longitude",
    "TfNSW_ AssetCode",
    "TfNSW_AssetDescription",
    "TfNSW_AssetID",
    "TfNSW_AssetInstance",
    "TfNSW_AssetMaintainerOrgName",
    "TfNSW_AssetOperatorOrgName",
    "TfNSW_AssetOwnerOrgName",
    "TfNSW_AssetStatusCode",
    "TfNSW_AssetTypeCode",
    "TfNSW_AssetTypeConfigCode",
    "TfNSW_AssetTypeConfigDesc",
    "TfNSW_DisciplineCode",
    "TfNSW_EndKm",
    "TfNSW_MMIFlag",
    "TfNSW_GPSCoordinates",
    "TfNSW_ParentAssetCode",
    "TfNSW_ParentAssetID",
    "TfNSW_StartKm",
    "TfNSW_SubDisciplineCode",
    "TfNSW_UniclassAssetCode",
    "TfNSW_UniclassAssetTitle",
    "Uniclass_EFCode",
    "Uniclass_EFTitle",
    "Uniclass_PrCode",
    "Uniclass_PrTitle",
    "Uniclass_SsCode",
    "Uniclass_SsTitle",
]

NA_ALLOWED_PROPERTIES = {
    "SM_LocationLevelCode",
    "SM_LocationLevelDesc",
    "SM_LocationRoomSpaceInstNumber",
    "SM_LocationRoomSpaceName",
    "SM_LocationRoomSpaceTypeCode",
    "SM_LocationRoomSpaceTypeDesc",
    "End Latitude",
    "End Longitude",
    "SM_ActivityCode",
    "SM_ActivityName",
}

REQUIRED_EXACT_VALUES = {
    "tbCoordSys": "GDA2020/MGA zone 56",
}

MIN_LENGTH_RULES = {
    "TfNSW_DocumentNo": 36,
}


@dataclass
class GroupResult:
    name: str
    passed: bool
    missing: list[str]
    empty_values: list[str]
    invalid_values: list[str]

    @property
    def reason(self) -> str:
        details = []
        if self.missing:
            details.append(f"Missing: {', '.join(self.missing)}")
        if self.empty_values:
            details.append(f"Empty value: {', '.join(self.empty_values)}")
        if self.invalid_values:
            details.append(f"Invalid value: {', '.join(self.invalid_values)}")
        if not details:
            return "All required properties found with values"
        return " | ".join(details)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate IFC files from In folder and output logs/summary/CSV to out folder."
    )
    parser.add_argument(
        "--in-dir",
        default="In",
        help="Folder containing IFC files (default: In)",
    )
    parser.add_argument(
        "--out-dir",
        default="out",
        help="Folder for outputs (default: out)",
    )
    return parser.parse_args()


def extract_schema(text: str) -> str:
    schema_match = re.search(r"FILE_SCHEMA\s*\(\s*\((.*?)\)\s*\)", text, flags=re.IGNORECASE | re.DOTALL)
    if not schema_match:
        return ""
    schema_text = schema_match.group(1)
    quoted = re.findall(r"'([^']+)'", schema_text)
    return ", ".join(quoted)


def extract_properties(text: str) -> dict[str, list[str | None]]:
    properties: dict[str, list[str | None]] = {}
    pattern = re.compile(
        r"IFCPROPERTYSINGLEVALUE\(\s*'(?P<name>[^']+)'\s*,\s*[^,]*,\s*(?P<value>.+?)\s*,\s*\$\s*\)\s*;",
        flags=re.IGNORECASE,
    )

    for line in text.splitlines():
        match = pattern.search(line)
        if not match:
            continue
        name = match.group("name").strip()
        raw_value = match.group("value").strip()
        parsed_value = normalize_value(raw_value)
        properties.setdefault(name, []).append(parsed_value)
    return properties


def normalize_value(raw_value: str) -> str | None:
    if raw_value == "$":
        return None

    typed_match = re.match(r"[A-Z0-9_]+\('(.+)'\)", raw_value, flags=re.IGNORECASE)
    if typed_match:
        return typed_match.group(1).strip()

    quoted_match = re.match(r"'(.+)'", raw_value)
    if quoted_match:
        return quoted_match.group(1).strip()

    return raw_value.strip()


def has_valid_value(values: list[str | None]) -> bool:
    for value in values:
        if value is None:
            continue
        if value.strip() != "":
            return True
    return False


def check_values_against_rules(prop_name: str, values: list[str | None]) -> str | None:
    non_empty_values = [v.strip() for v in values if v is not None and v.strip() != ""]
    if not non_empty_values:
        return None

    if prop_name in REQUIRED_EXACT_VALUES:
        expected = REQUIRED_EXACT_VALUES[prop_name]
        if all(value != expected for value in non_empty_values):
            found = ", ".join(non_empty_values)
            return f"{prop_name} expected '{expected}', found '{found}'"

    if prop_name in MIN_LENGTH_RULES:
        required_length = MIN_LENGTH_RULES[prop_name]
        if all(len(value) != required_length for value in non_empty_values):
            lengths = ", ".join(str(len(value)) for value in non_empty_values)
            return f"{prop_name} must be length {required_length}, found length(s): {lengths}"

    if prop_name not in NA_ALLOWED_PROPERTIES:
        if any(value.upper() == "N/A" for value in non_empty_values):
            return f"{prop_name} contains disallowed N/A"

    return None


def validate_group(group_name: str, required_props: list[str], props: dict[str, list[str | None]]) -> GroupResult:
    missing = []
    empty_values = []
    invalid_values = []

    for prop_name in required_props:
        if prop_name not in props:
            missing.append(prop_name)
            continue
        if not has_valid_value(props[prop_name]):
            empty_values.append(prop_name)
            continue

        rule_issue = check_values_against_rules(prop_name, props[prop_name])
        if rule_issue:
            invalid_values.append(rule_issue)

    return GroupResult(
        name=group_name,
        passed=(len(missing) == 0 and len(empty_values) == 0 and len(invalid_values) == 0),
        missing=missing,
        empty_values=empty_values,
        invalid_values=invalid_values,
    )


def validate_ifc_file(ifc_path: Path) -> tuple[bool, str, list[GroupResult]]:
    text = ifc_path.read_text(encoding="utf-8", errors="ignore")
    schema = extract_schema(text)
    schema_pass = "IFC4X3" in schema.upper()
    schema_reason = (
        f"Detected schema: {schema}" if schema_pass else f"Expected IFC4X3, detected: {schema or 'Not found'}"
    )

    props = extract_properties(text)
    group_results = [
        validate_group("SM_PROJECT", PROJECT_REQUIRED, props),
        validate_group("SM_ASSET", ASSET_REQUIRED, props),
        validate_group("SM_LOCATION", LOCATION_REQUIRED, props),
    ]
    return schema_pass, schema_reason, group_results


def write_file_log(
    out_dir: Path,
    ifc_name: str,
    schema_pass: bool,
    schema_reason: str,
    group_results: list[GroupResult],
) -> None:
    log_path = out_dir / f"{ifc_name}_log.txt"
    lines = [
        f"FILE: {ifc_name}",
        "",
        f"IFC version {'PASS' if schema_pass else 'FAIL'} - {schema_reason}",
    ]

    for result in group_results:
        lines.append(f"{result.name} {'PASS' if result.passed else 'FAIL'}")
        lines.append("REASONS")
        lines.append(result.reason)
        lines.append("")

    log_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def write_summary(out_dir: Path, summaries: list[str]) -> None:
    summary_path = out_dir / "summary.txt"
    if summaries:
        summary_path.write_text("\n\n".join(summaries).strip() + "\n", encoding="utf-8")
    else:
        summary_path.write_text("No IFC files found in input folder.\n", encoding="utf-8")


def write_csv(out_dir: Path, rows: list[dict[str, str]]) -> None:
    csv_path = out_dir / "validation_results.csv"
    fieldnames = ["file", "check", "status", "details"]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_arguments()
    input_dir = Path(args.in_dir)
    if not input_dir.exists() and input_dir.name.lower() == "in":
        alt_dir = input_dir.parent / ("In" if input_dir.name == "in" else "in")
        if alt_dir.exists():
            input_dir = alt_dir
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not input_dir.exists() or not input_dir.is_dir():
        message = f"Input folder not found: {input_dir.resolve()}"
        (out_dir / "summary.txt").write_text(message + "\n", encoding="utf-8")
        print(message)
        return

    ifc_files = sorted(input_dir.glob("*.ifc"))
    summary_blocks: list[str] = []
    csv_rows: list[dict[str, str]] = []

    for ifc_file in ifc_files:
        schema_pass, schema_reason, group_results = validate_ifc_file(ifc_file)
        file_name = ifc_file.name
        file_stem = ifc_file.stem

        write_file_log(out_dir, file_stem, schema_pass, schema_reason, group_results)

        block_lines = [
            f"FILE: {file_name}",
            f"IFC version {'PASS' if schema_pass else 'FAIL'} - {schema_reason}",
        ]

        csv_rows.append(
            {
                "file": file_name,
                "check": "IFC_VERSION",
                "status": "PASS" if schema_pass else "FAIL",
                "details": schema_reason,
            }
        )

        for result in group_results:
            block_lines.append(f"{result.name} {'PASS' if result.passed else 'FAIL'}")
            block_lines.append("REASONS")
            block_lines.append(result.reason)

            csv_rows.append(
                {
                    "file": file_name,
                    "check": result.name,
                    "status": "PASS" if result.passed else "FAIL",
                    "details": result.reason,
                }
            )

        summary_blocks.append("\n".join(block_lines))

    write_summary(out_dir, summary_blocks)
    write_csv(out_dir, csv_rows)

    print(f"Processed {len(ifc_files)} IFC file(s).")
    print(f"Outputs written to: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
"""AUTOSAR XSD Schema to Rupa Domain Converter.

Usage:
    python tools/autosar-converter/converter.py <schema.xsd> <output-dir>
"""

import argparse
import sys
import os

# Add the converter directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from schema_parser import parse_schema, export_schema
from rupa_generator import generate_rupa_files


def main():
    parser = argparse.ArgumentParser(
        description="Convert AUTOSAR XSD schema to Rupa domain files."
    )
    parser.add_argument("schema", help="Path to AUTOSAR XSD schema file")
    parser.add_argument("output_dir", help="Output directory for .rupa files")
    parser.add_argument(
        "--alternatives", action="store_true", default=False,
        help="Generate variant alternative comments (// also:) on members",
    )
    args = parser.parse_args()

    if not os.path.exists(args.schema):
        print(f"Error: Schema file not found: {args.schema}")
        sys.exit(1)

    print(f"Parsing {args.schema}...")
    internal = parse_schema(args.schema)

    print("Exporting schema model...")
    schema = export_schema(internal)

    print(f"Generating Rupa files in {args.output_dir}/...")
    os.makedirs(args.output_dir, exist_ok=True)
    generate_rupa_files(schema, args.output_dir, show_alternatives=args.alternatives)

    print(f"Done. {len(schema.primitives)} primitives, "
          f"{len(schema.enums)} enums, "
          f"{len(schema.composites)} composites.")
    if schema.warnings:
        print(f"  {len(schema.warnings)} warnings (see mapping-report.md)")
    if schema.errors:
        print(f"  {len(schema.errors)} ERRORS (see mapping-report.md)")


if __name__ == "__main__":
    main()

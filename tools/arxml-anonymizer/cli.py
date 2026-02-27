"""CLI entry point for ARXML anonymizer."""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Anonymize ARXML files by replacing SHORT-NAMEs with nature-themed words."
    )
    parser.add_argument("input", help="Path to the input ARXML file")
    parser.add_argument("output", help="Path to write the anonymized ARXML file")
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for deterministic name generation"
    )
    args = parser.parse_args()

    from anonymizer import anonymize_arxml

    result = anonymize_arxml(args.input, args.output, seed=args.seed)

    print(f"Anonymized {result.mapping_count} SHORT-NAMEs")
    if result.verification_passed:
        print("Verification: PASSED (no original names found in output)")
    else:
        print(f"Verification: FAILED ({len(result.leaked_names)} names leaked)")
        for name in result.leaked_names:
            print(f"  - {name}")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Verify a Creator Studio static project ZIP without extracting or executing it."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import stat
import zipfile
import zlib

try:
    from .creator_project import (MAX_SPEC, assemble, expected_manifest, spec_bytes,
                                  validate_spec, unique_object, reject_constant)
except ImportError:
    from creator_project import (MAX_SPEC, assemble, expected_manifest, spec_bytes,
                                 validate_spec, unique_object, reject_constant)

MAX_ARCHIVE = 4 * 1024 * 1024
MAX_MEMBERS = 27


def read_member(archive, info, limit):
    if info.file_size > limit:
        raise ValueError("Bundle entry exceeds its expected size")
    with archive.open(info) as stream:
        data = stream.read(limit + 1)
    if len(data) > limit or len(data) != info.file_size:
        raise ValueError("Bundle entry size does not match")
    return data


def parse_json(data):
    return json.loads(data.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=reject_constant)


def read_verified_bundle(data):
    """Return a validated draft and evidence; never extract or execute the ZIP."""
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_ARCHIVE:
        raise ValueError("Select a static project ZIP up to 4 MiB")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if not 1 <= len(entries) <= MAX_MEMBERS:
                raise ValueError("Unexpected number of bundle entries")
            by_name = {}
            for info in entries:
                mode = stat.S_IFMT(info.external_attr >> 16)
                if (info.filename != info.orig_filename or info.filename in by_name
                        or info.is_dir() or mode not in (0, stat.S_IFREG)
                        or info.flag_bits & 1
                        or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                    raise ValueError("Unexpected or unsupported bundle entry")
                by_name[info.filename] = info
            if "project.json" not in by_name:
                raise ValueError("Missing project specification")
            spec = parse_json(read_member(archive, by_name["project.json"], MAX_SPEC))
            validate_spec(spec)
            if any(spec["review"].values()):
                raise ValueError("Studio bundles must be unapproved drafts")
            files = assemble(spec)
            expected_names = {"project.json", "site/creator-manifest.json"} | {
                "site/" + name for name in files
            }
            if set(by_name) != expected_names:
                raise ValueError("Unexpected or missing bundle entries")
            manifest = parse_json(read_member(archive, by_name["site/creator-manifest.json"], MAX_SPEC))
            if spec_bytes(manifest) != spec_bytes(expected_manifest(spec, files)):
                raise ValueError("Bundle manifest does not match the specification")
            for name, body in files.items():
                expected = body.encode("utf-8")
                actual = read_member(archive, by_name["site/" + name], len(expected))
                if actual != expected:
                    raise ValueError("Generated bundle file differs from current generator output")
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, zlib.error,
            UnicodeError, TypeError, KeyError, RecursionError) as exc:
        raise ValueError("Invalid or unsupported static project bundle") from exc
    report = {
        "version": 1,
        "status": "passed",
        "archive_sha256": hashlib.sha256(data).hexdigest(),
        "project_sha256": hashlib.sha256(spec_bytes(spec)).hexdigest(),
        "pages": len(spec["pages"]),
        "generated_files": len(files),
        "files": manifest["files"],
        "publication_ready": False,
        "limitations": [
            "Matches the current generator and draft specification only; not a digital signature.",
            "Older exports may need to be rebuilt after generator changes.",
            "No browser execution, extraction, originality certification or publication approval.",
        ],
    }

    return spec, report


def verify_bundle(data):
    """Return evidence of matching current generator output, not authenticity."""
    return read_verified_bundle(data)[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--report", type=Path, help="Write new evidence file without overwriting")
    args = parser.parse_args()
    try:
        with args.bundle.open("rb") as stream:
            report = verify_bundle(stream.read(MAX_ARCHIVE + 1))
        output = json.dumps(report, indent=2) + "\n"
        if args.report:
            with args.report.open("x", encoding="utf-8") as stream:
                stream.write(output)
        print(output, end="")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()

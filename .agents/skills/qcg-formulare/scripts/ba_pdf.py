#!/usr/bin/env python3
"""Inspect, fill and extract BA AcroForms locally with qpdf. No signature handling."""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


def qpdf(*arguments):
    result = subprocess.run(["qpdf", *map(str, arguments)], capture_output=True, text=True)
    if result.returncode not in (0, 3):
        raise ValueError(f"qpdf failed (status {result.returncode}); inspect the input PDF locally.")
    return result


@dataclass
class Pdf:
    path: Path

    def __post_init__(self):
        result = qpdf("--json", "--json-key=qpdf", "--json-key=acroform", "--json-key=pages",
                      "--json-key=encrypt", self.path)
        data = json.loads(result.stdout)
        self.header, self.objects = data["qpdf"]
        self.fields = data["acroform"]["fields"]
        self.pages = data["pages"]
        self.warnings = bool(result.stderr)
        self.root_ref = self.objects["trailer"]["value"]["/Root"]
        self.root = self.resolve(self.root_ref)
        if data["encrypt"]["encrypted"]:
            raise ValueError("Encrypted PDFs require an authorized editable copy.")
        self.form = self.resolve(self.root.get("/AcroForm")) or {}
        last_object = max(int(key.split(":")[1].split()[0]) for key in self.objects if key.startswith("obj:"))
        self.next_id = 1 + max(last_object, self.objects["trailer"]["value"].get("/Size", 0))

    def resolve(self, ref):
        if isinstance(ref, str) and re.fullmatch(r"\d+ \d+ R", ref):
            obj = self.objects["obj:" + ref]
            return obj.get("value", obj.get("stream", {}).get("dict"))
        return ref

    def editable(self):
        if self.form.get("/XFA") is not None:
            raise ValueError("XFA forms must be prepared in a compatible PDF editor.")
        if self.root.get("/Perms") or any(f["fieldtype"] == "/Sig" and f["value"] for f in self.fields):
            raise ValueError("A signed or certified PDF must be preserved. Use an unsigned source copy.")

    def new_object(self, patch, entry):
        ref = f"{self.next_id} 0 R"
        self.next_id += 1
        patch["obj:" + ref] = entry
        return ref

    def normal_states(self, field):
        widget = self.resolve(field["object"])
        appearance = self.resolve(widget.get("/AP")) or {}
        if isinstance(appearance.get("/N"), dict):
            return appearance["/N"]
        states = self.resolve(appearance.get("/N"))
        return states if isinstance(states, dict) and "/Off" in states else {}


def signing_field(field):
    label = field["alternativename"] or ""
    name = field["fullname"].lower()
    return (field["fieldtype"] == "/Sig" or "stempel" in name or "unterschrift" in name
            or bool(re.search(r"^(?:\d+\s*-\s*)?(?:Datum|Stempel|Unterschrift|Name, Unterschrift)\b", label, re.I)))


def inspect(pdf):
    payload = []
    for field in pdf.fields:
        value = field["value"]
        payload.append({
            "page": field["pageposfrom1"], "field": field["fullname"],
            "label": field["alternativename"], "type": field["fieldtype"],
            "present": value not in (None, "", "u:", "/Off"),
            "read_only": bool(field["fieldflags"] & 1), "manual_signing": signing_field(field),
            "states": list(pdf.normal_states(field)) if field["fieldtype"] == "/Btn" else [],
        })
    print(json.dumps({"pages": len(pdf.pages), "fields": payload,
                      "source_warnings": pdf.warnings}, ensure_ascii=False, indent=2))


def appearance(pdf, patch, field, widget, value):
    x0, y0, x1, y1 = widget["/Rect"]
    width, height = abs(x1 - x0), abs(y1 - y0)
    flags = field["fieldflags"]
    if flags & (8192 | 16777216 | 33554432) or (pdf.resolve(widget.get("/MK")) or {}).get("/R", 0):
        raise ValueError(f"Special layout requires a PDF editor: {field['fullname']}")
    lines = value.split("\n")
    if len(lines) > 1 and not flags & 4096:
        raise ValueError(f"Single-line field: {field['fullname']}")
    encoded = [line.encode("cp1252") for line in lines]
    # A conservative fit for the built-in Helvetica font. Final visual review is mandatory.
    def units(line):
        return sum(0.95 if c in b"MWmw@%" else 0.74 if c in b"ABCDEFGHKNOPQRSTUVXYZ" or c >= 128
                   else 0.36 if c in b" ilI1.,:;!|'" else 0.60 for c in line)

    size = min(10, (height - 3) / (1.18 * len(lines)),
               (width - 7) / max(1, *(units(line) for line in encoded)))
    if size < 6:
        raise ValueError(f"Text will not fit legibly: {field['fullname']}")
    mk = pdf.resolve(widget.get("/MK")) or {}
    border = pdf.resolve(widget.get("/BS")) or {}
    commands = [f"q 0 0 {width:g} {height:g} re W n"]
    if mk.get("/BG") == [1, 1, 1]:
        commands.append(f"1 g 0 0 {width:g} {height:g} re f")
    if mk.get("/BC") is not None and border.get("/W", 1) > 0:
        color = mk["/BC"]
        if len(color) in (1, 3, 4):
            op = {1: "G", 3: "RG", 4: "K"}[len(color)]
            stroke = " ".join(map(str, color))
            commands.append(f"{stroke} {op} 1 w .5 .5 {width-1:g} {height-1:g} re S")
    baseline = height - size - 2 if len(lines) > 1 else (height - size) / 2 + size * 0.17
    for index, line in enumerate(encoded):
        align = field.get("quadding", 0)
        text_width = units(line) * size
        left = {1: max(3, (width - text_width) / 2), 2: max(3, width - text_width - 3)}.get(align, 3)
        y = baseline - index * size * 1.18
        commands.append(f"BT /F0 {size:.2f} Tf 0 g 1 0 0 1 {left:.2f} {y:.2f} Tm <{line.hex()}> Tj ET")
    commands.append("Q")
    font = {"/Type": "/Font", "/Subtype": "/Type1", "/BaseFont": "/Helvetica", "/Encoding": "/WinAnsiEncoding"}
    stream = {"dict": {"/Type": "/XObject", "/Subtype": "/Form", "/BBox": [0, 0, width, height],
                       "/Resources": {"/Font": {"/F0": font}}},
              "data": base64.b64encode("\n".join(commands).encode("ascii")).decode("ascii")}
    return pdf.new_object(patch, {"stream": stream})


def edit(pdf, patch, fields, value, replace):
    field = fields[0]
    name = field["fullname"]
    if any(signing_field(f) or f["fieldflags"] & 1 for f in fields):
        raise ValueError(f"Manual or read-only field: {name}")
    field_type = field["fieldtype"]
    if field_type not in ("/Tx", "/Ch", "/Btn"):
        raise ValueError(f"Unsupported field type: {name}")
    wanted = value if field_type == "/Btn" else "u:" + value
    for item in fields:
        if item["value"] not in (None, "", "u:", "/Off", wanted) and not replace:
            raise ValueError(f"Existing value differs for {name}; confirm correction before using --replace.")

    if field_type == "/Btn":
        targets = [f for f in fields if value in pdf.normal_states(f)]
        if not targets or (field["isradiobutton"] and (value == "/Off" or len(targets) != 1)):
            raise ValueError(f"Select a valid exact state from inspect: {name}")
        actor = field["parent"] or field["object"]
        for item in fields:
            ref = item["object"]
            widget = dict(pdf.resolve(ref))
            widget["/AS"] = value if item in targets else "/Off"
            patch["obj:" + ref] = {"value": widget}
        record = patch.setdefault("obj:" + actor, {"value": dict(pdf.resolve(actor))})
        record["value"]["/V"] = value
        return wanted

    if field_type == "/Ch":
        raise ValueError(f"Choice fields require an editor: {name}")
    if len(fields) != 1:
        raise ValueError(f"Ambiguous text field name: {name}")
    ref = field["object"]
    widget = dict(pdf.resolve(ref))
    parent = field["parent"] or ref
    actor = widget if parent == ref else dict(pdf.resolve(parent))
    max_length = actor.get("/MaxLen", widget.get("/MaxLen"))
    if max_length and len(value) > max_length:
        raise ValueError(f"Field length exceeded: {name}")
    actor["/V"] = wanted
    widget["/AP"] = {"/N": appearance(pdf, patch, field, widget, value)}
    patch["obj:" + ref] = {"value": widget}
    patch["obj:" + parent] = {"value": actor}
    return wanted


def fill(pdf, output, edits_path, replace, pages):
    pdf.editable()
    edits_text = sys.stdin.read() if edits_path == "-" else Path(edits_path).read_text()
    edits = json.loads(edits_text)
    if not isinstance(edits, dict) or any(not isinstance(v, str) or not v.strip() for v in edits.values()):
        raise ValueError("Edits must be a JSON object of exact field names and non-empty string values.")
    if output.exists():
        raise ValueError("Output already exists. Choose a new file name.")
    with tempfile.TemporaryDirectory(prefix="qcg-pdf-") as temporary:
        temp = Path(temporary)
        clean = temp / "normalized.pdf"
        # Normalize incremental revisions and object streams before replacing appearances.
        normalized = qpdf("--qdf", "--object-streams=disable", pdf.path, clean)
        write_copy(Pdf(clean), output, edits, replace, pages, temp, pdf.warnings or bool(normalized.stderr))


def write_copy(pdf, output, edits, replace, pages, temp, input_warnings):
    groups = {}
    for field in pdf.fields:
        groups.setdefault(field["fullname"], []).append(field)
    patch, expected = {}, {}
    for name, value in edits.items():
        if name not in groups:
            raise ValueError(f"Unknown field in this PDF: {name}")
        expected[name] = edit(pdf, patch, groups[name], value, replace)

    patch_path = temp / "changes.json"
    updated = temp / "updated.pdf"
    patch_path.write_text(json.dumps({"qpdf": [pdf.header, patch]}, ensure_ascii=False))
    result = qpdf(pdf.path, f"--update-from-json={patch_path}", updated)
    checked = Pdf(updated)
    if {f["fullname"] for f in checked.fields} != set(groups):
        raise ValueError("Form fields changed unexpectedly.")
    warnings = input_warnings or checked.warnings or bool(result.stderr)
    final = checked
    if pages:
        if len(set(pages)) != len(pages) or min(pages) < 1 or max(pages) > len(pdf.pages):
            raise ValueError("Select unique existing page numbers.")
        if any(not all(f["pageposfrom1"] in pages for f in groups[name]) for name in expected):
            raise ValueError("At least one edited field is outside the requested pages.")
        subset = temp / "subset.pdf"
        # Using an empty primary document excludes linked pages in catalog-level outlines and name trees.
        extraction = qpdf("--empty", "--pages", updated, ",".join(map(str, pages)), "--", subset)
        warnings = warnings or bool(extraction.stderr)
        final = Pdf(subset)
    validate_copy(pdf, final, groups, expected, pages)
    check = qpdf("--check", final.path)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as destination, final.path.open("rb") as source:
        shutil.copyfileobj(source, destination)
    print(json.dumps({"pages": len(final.pages), "fields_filled": len(expected),
                      "pdf_warnings": bool(warnings or final.warnings or check.stderr)}))


def validate_copy(pdf, final, groups, expected, pages):
    page_objects = [obj for obj in final.objects.values()
                    if isinstance(obj.get("value"), dict) and obj["value"].get("/Type") == "/Page"]
    count = len(pages) if pages else len(pdf.pages)
    if len(final.pages) != count or len(page_objects) != count:
        raise ValueError("Page count verification failed.")
    selected_fields = {f["fullname"] for f in pdf.fields if not pages or f["pageposfrom1"] in pages}
    if any(f["pageposfrom1"] < 1 for f in final.fields) or {f["fullname"] for f in final.fields} != selected_fields:
        raise ValueError("Output form fields do not match the requested pages.")
    for field in final.fields:
        name = field["fullname"]
        if name not in expected:
            if not any(old["value"] == field["value"] for old in groups[name]):
                raise ValueError(f"An untouched field changed: {name}")
            continue
        if field["value"] != expected[name]:
            raise ValueError(f"Saved value verification failed: {name}")
        widget = final.resolve(field["object"])
        if field["fieldtype"] == "/Tx":
            normal = final.resolve(final.resolve(widget.get("/AP"))["/N"])
            resources = final.resolve(normal.get("/Resources")) or {}
            fonts = final.resolve(resources.get("/Font")) or {}
            if "/F0" not in fonts:
                raise ValueError(f"New text appearance did not survive export: {name}")
        elif field["fieldtype"] == "/Btn":
            state = expected[name] if expected[name] in final.normal_states(field) else "/Off"
            if widget.get("/AS") != state:
                raise ValueError(f"Button appearance differs from its saved value: {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inspect").add_argument("pdf", type=Path)
    edit_parser = commands.add_parser("fill")
    edit_parser.add_argument("pdf", type=Path)
    edit_parser.add_argument("output", type=Path)
    edit_parser.add_argument("--edits", default="-", help="JSON file or stdin (default).")
    edit_parser.add_argument("--pages", type=int, nargs="+")
    edit_parser.add_argument("--replace", action="store_true", help="Permit confirmed corrections to existing values.")
    args = parser.parse_args()
    try:
        pdf = Pdf(args.pdf)
        if args.command == "inspect":
            inspect(pdf)
        else:
            fill(pdf, args.output, args.edits, args.replace, args.pages)
    except (OSError, ValueError, KeyError) as error:
        if isinstance(error, (json.JSONDecodeError, UnicodeEncodeError)):
            print("Invalid JSON or unsupported text encoding. Use an appropriate local PDF editor if needed.", file=sys.stderr)
        else:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

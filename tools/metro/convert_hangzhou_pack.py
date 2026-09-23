#!/usr/bin/env python3
#
# SPDX-License-Identifier: Apache-2.0
#
"""Deterministic Hangzhou raw-material -> first-party runtime pack converter.

Inputs (read-only, shipped next to this script under raw/):
  hz_line_v2.decompressed.json  line network: line order, branches, station order
  hz_bs_v2.decoded.json         cell fingerprints keyed by station display name
                                (hz_bs_v2.decompressed.json holds obfuscated
                                negative cids and MUST NOT be used)

Output:
  --out     strict first-party pack, HangzhouTransitPack schema, packVersion 2,
            cellMatchMode LOCAL_CID_COMPAT
  --report  human readable conversion report (also printed to stdout)

Determinism: no timestamps, no output hashes, stable ordering everywhere
(stations sorted by code, cells sorted by (stationCode, cellId), lines in the
order of the line material). Two runs over identical inputs produce byte
identical output.

Honesty rules encoded here:
  * only `cid` is copied out of the raw material. The raw `lo`/`s`/`ot` fields
    have unverified semantics (not latitude/longitude, operator or network
    identity) and are dropped, never guessed.
  * the material carries no MCC/MNC/TAC at all, so LOCAL_CID_COMPAT cells are
    emitted with explicit unknown placeholders (0/0/0), exactly like the
    user-verified prototype pack. No fake full-identity data is generated.
"""

import argparse
import hashlib
import json
import os
import re
import sys

# --- contract constants -----------------------------------------------------

CITY = "hangzhou"
PACK_VERSION = 2
CELL_MATCH_MODE = "LOCAL_CID_COMPAT"
DEBUG_CELL_MATCH_MODE = "CELL_ID_ONLY_DEBUG"
EXACT_CELL_MATCH_MODE = "EXACT"
CELL_MATCH_MODES = (EXACT_CELL_MATCH_MODE, CELL_MATCH_MODE, DEBUG_CELL_MATCH_MODE)
EXACT_RATS = ("LTE", "NR", "WCDMA")

STATION_CODE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")

# Reused verbatim from HangzhouStationNames.keepStationSuffix: the ibus stop
# name for these keeps the trailing "站".
KEEP_STATION_SUFFIX = (
    "城站",
    "火车东站",
    "火车西站",
    "火车南站",
    "临平南高铁站",
    "永福站",
)

# Names where the ibus stop name differs from the normalized display name.
# 阳陂湖站 -> 阳坡湖 is recorded in the handover material (pure test fixture
# hz-mini.json and docs/architecture/METRO_COMMUTE_P0.md section 12).
NAME_FIXES = {
    "阳陂湖站": "阳坡湖",
}

# ibus reports the 3/6 branch services as their own routeName; these aliases map
# them back onto the metro line so that all directions of a station are queried
# from a single response.
ROUTE_ALIASES = (
    {"ibusRouteName": "3号线往石马", "lineName": "3号线", "directionTerminal": "石马"},
    {"ibusRouteName": "6号线往双浦", "lineName": "6号线", "directionTerminal": "双浦"},
)

# Lines present in the raw line material that must not enter the runtime pack.
# The realtime source (ibuscloud getMetroInfoList) does not cover the
# intercity line, and the pack schema has no per-line "no realtime ETA" flag, so
# shipping it would claim ETA support that does not exist.
EXCLUDED_LINES = {
    "杭海城际": "not covered by the realtime ETA source (ibus getMetroInfoList)",
}

BS_KEY_PREFIX = "杭州地铁("

# --- helpers ----------------------------------------------------------------


def direction_key(raw):
    """Mirror of HangzhouStationNames.directionKey."""
    key = raw
    if key.startswith("往"):
        key = key[len("往"):]
    for suffix in ("方向", "站"):
        if key.endswith(suffix):
            key = key[: -len(suffix)]
    return key


def to_ibus_stop_name(display_name, fixes):
    """Mirror of HangzhouStationNames.toIbusStopName."""
    if display_name in KEEP_STATION_SUFFIX:
        return display_name
    if display_name in fixes:
        return fixes[display_name]
    if display_name.endswith("站"):
        return display_name[: -len("站")]
    return display_name


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def line_sort_key(line):
    """Numeric line ids first, in numeric order; anything else afterwards."""
    ident = str(line.get("id"))
    if ident.isdigit():
        return (0, int(ident), ident)
    return (1, 0, ident)


def bs_display_name(key):
    """'杭州地铁(丁桥站)' -> '丁桥站'.

    The key text is the display name wrapped in 杭州地铁(...), including the
    station's own trailing 站 (杭州地铁(城站站) is the single double-站 entry in
    the material and is resolved as an alias of 城站).
    """
    if not (key.startswith(BS_KEY_PREFIX) and key.endswith(")")):
        return None
    return key[len(BS_KEY_PREFIX): -1]


# --- build -----------------------------------------------------------------


def build_pack(line_doc, bs_doc, code_overrides):
    anomalies = {
        "bs_unmatched": [],
        "bs_aliased": [],
        "cell_stations": {},
        "duplicate_cids": {},
        "stations_without_cells": [],
        "invalid_cids": [],
        "branch_junctions": [],
        "topology_breaks": [],
        "duplicate_stations_in_branch": [],
        "excluded_lines": [],
        "lines_without_cells": [],
        "unverified_ibus_names": [],
        "unknown_codes": [],
        "alias_problems": [],
        "codes_override_applied": [],
    }

    raw_lines = sorted(line_doc.get("lines", []), key=line_sort_key)

    # 1. station identity, first-appearance order over the non-excluded graph
    station_order = []
    station_lines = {}
    pack_lines = []
    excluded_raw = []
    for raw_line in raw_lines:
        line_name = raw_line.get("name")
        if line_name in EXCLUDED_LINES:
            excluded = []
            for branch in raw_line.get("branches", []):
                for name in branch.get("stations", []):
                    if name not in excluded:
                        excluded.append(name)
            excluded_raw.append((line_name, excluded))
            continue
        for branch in raw_line.get("branches", []):
            stations = list(branch.get("stations", []))
            if len(stations) < 2:
                anomalies["topology_breaks"].append(
                    {"line": line_name, "branch": branch.get("id"), "reason": "branch has <2 stations"}
                )
                continue
            duplicates = sorted({s for s in stations if stations.count(s) > 1})
            if duplicates:
                anomalies["duplicate_stations_in_branch"].append(
                    {"line": line_name, "branch": branch.get("id"), "stations": duplicates}
                )
            for name in stations:
                if name not in station_lines:
                    station_lines[name] = []
                    station_order.append(name)
                if branch.get("id") not in station_lines[name]:
                    station_lines[name].append(branch.get("id"))
            pack_lines.append(
                {
                    "id": branch.get("id"),
                    "name": line_name,
                    "terminals": [stations[0], stations[-1]],
                    "stationCodes": stations,
                    "_stations": stations,
                }
            )

    codes = {}
    for index, name in enumerate(station_order, start=1):
        codes[name] = "hz_s%03d" % index
    for name in sorted(code_overrides):
        code = code_overrides[name]
        if name not in codes:
            raise SystemExit(
                "station-codes.json: no station named %r in the line material" % name
            )
        if not STATION_CODE_RE.match(code):
            raise SystemExit(
                "station-codes.json: %r is not a valid station code" % code
            )
        codes[name] = code
        anomalies["codes_override_applied"].append({"name": name, "code": code})
    seen_codes = {}
    for name in station_order:
        code = codes[name]
        if code in seen_codes:
            raise SystemExit(
                "station code collision: %r used by both %r and %r"
                % (code, seen_codes[code], name)
            )
        seen_codes[code] = name

    # 2. lines[] with resolved station codes
    for line_name, raw_stations in excluded_raw:
        anomalies["excluded_lines"].append(
            {
                "line": line_name,
                "reason": EXCLUDED_LINES[line_name],
                "rawStations": len(raw_stations),
                "droppedStations": [s for s in raw_stations if s not in station_lines],
                "keptStations": [s for s in raw_stations if s in station_lines],
            }
        )

    lines = []
    for line in pack_lines:
        lines.append(
            {
                "id": line["id"],
                "name": line["name"],
                "terminals": line["terminals"],
                "stationCodes": [codes[name] for name in line["_stations"]],
            }
        )

    # 3. stations[] sorted by code
    stations = []
    for name in sorted(station_order, key=lambda n: (codes[n], n)):
        stations.append(
            {
                "code": codes[name],
                "displayName": name,
                "ibusStopName": to_ibus_stop_name(name, NAME_FIXES),
                "lineIds": list(station_lines[name]),
            }
        )

    by_code = {s["code"]: s for s in stations}
    by_display = {s["displayName"]: s["code"] for s in stations}

    # 4. cells[] from the decoded cell material
    cell_map = {}
    for key in bs_doc.get("data", {}):
        display = bs_display_name(key)
        if display is None:
            anomalies["bs_unmatched"].append({"key": key, "reason": "unexpected key shape"})
            continue
        code = by_display.get(display)
        if code is None and display.endswith("站") and display[: -1] in by_display:
            code = by_display[display[: -1]]
            anomalies["bs_aliased"].append({"from": display, "to": display[: -1]})
        if code is None:
            anomalies["bs_unmatched"].append(
                {"key": key, "name": display, "records": len(bs_doc["data"][key])}
            )
            continue
        for record in bs_doc["data"][key]:
            cid = record.get("cid")
            if not isinstance(cid, int) or isinstance(cid, bool) or cid <= 0:
                anomalies["invalid_cids"].append({"station": display, "record": record})
                continue
            cell_map.setdefault(code, set()).add(cid)

    cells = []
    cid_stations = {}
    for code in sorted(cell_map):
        for cid in sorted(cell_map[code]):
            cells.append(
                {
                    "stationCode": code,
                    "rat": CELL_MATCH_MODE,
                    "mcc": 0,
                    "mnc": 0,
                    "tacOrLac": 0,
                    "cellId": cid,
                }
            )
            cid_stations.setdefault(cid, set()).add(code)

    for cid in sorted(cid_stations):
        owners = cid_stations[cid]
        if len(owners) > 1:
            anomalies["duplicate_cids"][cid] = sorted(owners)

    for station in stations:
        if station["code"] not in cell_map:
            anomalies["stations_without_cells"].append(
                {"code": station["code"], "displayName": station["displayName"]}
            )

    line_has_cells = {line["id"]: False for line in lines}
    for cell in cells:
        for line in lines:
            if cell["stationCode"] in line["stationCodes"]:
                line_has_cells[line["id"]] = True
    for line in lines:
        if not line_has_cells[line["id"]]:
            anomalies["lines_without_cells"].append({"id": line["id"], "name": line["name"]})

    # 5. nameFixes / routeAliases actually consumed by this pack
    name_fixes = [
        {"from": name, "to": target}
        for name, target in sorted(NAME_FIXES.items())
        if name in by_display
    ]
    direction_terminals = {}
    for line in lines:
        direction_terminals.setdefault(line["name"], set()).update(
            direction_key(t) for t in line["terminals"]
        )
    route_aliases = []
    for alias in ROUTE_ALIASES:
        if alias["lineName"] not in direction_terminals:
            anomalies["alias_problems"].append(
                {"alias": alias, "reason": "line not present in pack"}
            )
            continue
        if direction_key(alias["directionTerminal"]) not in direction_terminals[alias["lineName"]]:
            anomalies["alias_problems"].append(
                {"alias": alias, "reason": "direction terminal not a terminal of that line"}
            )
        route_aliases.append(dict(alias))

    # 6. topology analysis: branch junctions and breaks
    line_branches = {}
    for line, raw in zip(lines, pack_lines):
        line_branches.setdefault(line["name"], []).append(raw)
    for name in sorted(line_branches):
        branches = line_branches[name]
        if len(branches) == 1:
            continue
        junctions = []
        for i in range(len(branches)):
            for j in range(i + 1, len(branches)):
                left, right = branches[i]["_stations"], branches[j]["_stations"]
                shared = sorted(set(left) & set(right))
                if shared:
                    junctions.append(
                        {
                            "left": branches[i]["id"],
                            "right": branches[j]["id"],
                            "shared": shared,
                            "overlap": len(shared),
                        }
                    )
        anomalies["branch_junctions"].append({"line": name, "junctions": junctions})
        # connectivity: branches joined through shared stations form one graph?
        parent = {b["id"]: b["id"] for b in branches}

        def find(node):
            while parent[node] != node:
                parent[node] = parent[parent[node]]
                node = parent[node]
            return node

        for junction in junctions:
            root_left, root_right = find(junction["left"]), find(junction["right"])
            if root_left != root_right:
                parent[root_left] = root_right
        roots = sorted({find(b["id"]) for b in branches})
        if len(roots) > 1:
            anomalies["topology_breaks"].append(
                {"line": name, "components": roots, "reason": "branches do not share any station"}
            )

    # 7. ibus stop names that the offline material cannot confirm
    for station in stations:
        display = station["displayName"]
        if display in NAME_FIXES or re.search(r"[()（）]", display):
            anomalies["unverified_ibus_names"].append(
                {"code": station["code"], "displayName": display, "ibusStopName": station["ibusStopName"]}
            )

    # 8. codes that are not referenced by any line (should never happen)
    referenced = {code for line in lines for code in line["stationCodes"]}
    for station in stations:
        if station["code"] not in referenced:
            anomalies["unknown_codes"].append(station["code"])

    pack = {
        "city": CITY,
        "packVersion": PACK_VERSION,
        "cellMatchMode": CELL_MATCH_MODE,
        "lines": lines,
        "stations": stations,
        "cells": cells,
        "nameFixes": name_fixes,
        "routeAliases": route_aliases,
    }
    return pack, anomalies


# --- strict self check (mirrors HangzhouTransitPack strict decoding) ---------


def validate_pack(pack):
    """Strict schema + invariant self check. Returns the list of executed checks."""
    checks = []

    def require(condition, message):
        if not condition:
            raise SystemExit("pack self check failed: " + message)

    top_keys = ["city", "packVersion", "cellMatchMode", "lines", "stations", "cells",
                "nameFixes", "routeAliases"]
    require(sorted(pack.keys()) == sorted(top_keys), "unexpected top level keys")
    checks.append("top level keys are exactly {city, packVersion, cellMatchMode, lines, "
                  "stations, cells, nameFixes, routeAliases} (unknown keys rejected)")

    require(pack["city"] == CITY, "city must be 'hangzhou'")
    checks.append("city == 'hangzhou'")
    require(pack["packVersion"] == PACK_VERSION, "packVersion must be 2")
    checks.append("packVersion == 2")
    require(pack["cellMatchMode"] in CELL_MATCH_MODES, "unknown cellMatchMode")
    checks.append("cellMatchMode is one of EXACT / LOCAL_CID_COMPAT / CELL_ID_ONLY_DEBUG")

    station_codes = [s["code"] for s in pack["stations"]]
    require(len(set(station_codes)) == len(station_codes), "station codes must be unique")
    require(all(STATION_CODE_RE.match(c) for c in station_codes),
            "station codes must be lowercase ASCII identifiers")
    checks.append("station codes unique and matching ^[a-z][a-z0-9_-]{0,31}$")
    require(all(s["displayName"] and s["ibusStopName"] and s["lineIds"] for s in pack["stations"]),
            "stations need displayName, ibusStopName and lineIds")
    checks.append("every station has non-empty displayName, ibusStopName and lineIds")

    line_ids = [l["id"] for l in pack["lines"]]
    require(len(set(line_ids)) == len(line_ids), "line ids must be unique")
    checks.append("line ids are unique")
    known = set(station_codes)
    for line in pack["lines"]:
        require(bool(line["id"]) and bool(line["name"]), "lines need id and name")
        require(len(line["terminals"]) == 2 and all(line["terminals"]),
                "lines need exactly two non-empty terminals")
        require(len(line["stationCodes"]) >= 2 and all(c in known for c in line["stationCodes"]),
                "lines need >=2 stationCodes, all of them known")
        require(line["terminals"][0] == _display(pack, line["stationCodes"][0])
                and line["terminals"][1] == _display(pack, line["stationCodes"][-1]),
                "line terminals must be the display names of its first and last station")
    checks.append("every line: id/name present, exactly two terminals matching the first and "
                  "last station display name, >=2 known stationCodes")
    for station in pack["stations"]:
        for line_id in station["lineIds"]:
            require(line_id in set(line_ids), "station references unknown line id")
            members = next(l for l in pack["lines"] if l["id"] == line_id)["stationCodes"]
            require(station["code"] in members, "line does not contain the referencing station")
    checks.append("station.lineIds <-> line.stationCodes are mutually consistent")

    for cell in pack["cells"]:
        require(sorted(cell.keys()) == ["cellId", "mcc", "mnc", "rat", "stationCode", "tacOrLac"],
                "unexpected cell keys")
        require(cell["stationCode"] in known, "cells must reference known stations")
        require(isinstance(cell["cellId"], int) and cell["cellId"] > 0, "cellId must be positive")
        require(-(2 ** 63) < cell["cellId"] <= 2 ** 63 - 1, "cellId must fit in a signed 64 bit int")
        if pack["cellMatchMode"] == EXACT_CELL_MATCH_MODE:
            require(cell["rat"] in EXACT_RATS and cell["mcc"] >= 0 and cell["mnc"] >= 0
                    and cell["tacOrLac"] >= 0, "EXACT cells need a supported RAT and identity")
        else:
            require(cell["rat"] == pack["cellMatchMode"], "cid-only cells must carry the mode label")
            require(cell["mcc"] == 0 and cell["mnc"] == 0 and cell["tacOrLac"] == 0,
                    "cid-only cells must use explicit unknown identity placeholders")
    checks.append("every cell: known stationCode, 64 bit positive cellId, and identity fields "
                  "consistent with cellMatchMode (placeholder 0/0/0 + mode label for "
                  "LOCAL_CID_COMPAT)")
    cells = [(c["stationCode"], c["cellId"]) for c in pack["cells"]]
    require(len(set(cells)) == len(cells), "duplicate (stationCode, cellId) pairs")
    checks.append("no duplicate (stationCode, cellId) pairs")

    for fix in pack["nameFixes"]:
        require(sorted(fix.keys()) == ["from", "to"], "unexpected nameFix keys")
    checks.append("nameFixes entries have exactly {from, to}")
    for alias in pack["routeAliases"]:
        require(sorted(alias.keys()) == ["directionTerminal", "ibusRouteName", "lineName"],
                "unexpected routeAlias keys")
        terminals = set()
        for line in pack["lines"]:
            if line["name"] == alias["lineName"]:
                terminals.update(direction_key(t) for t in line["terminals"])
        require(terminals, "routeAlias references a line that is not in the pack")
        require(direction_key(alias["directionTerminal"]) in terminals,
                "routeAlias terminal is not a terminal of its line")
    checks.append("routeAliases entries have exactly {ibusRouteName, lineName, "
                  "directionTerminal}, reference an existing line and one of its terminals")

    return checks


def _display(pack, code):
    for station in pack["stations"]:
        if station["code"] == code:
            return station["displayName"]
    return None


# --- report ----------------------------------------------------------------


def render_report(pack, anomalies, paths, checks):
    out = []
    add = out.append
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    add("Hangzhou metro runtime pack conversion report")
    add("(deterministic: no timestamps; regenerate with tools/metro/convert_hangzhou_pack.py)")
    add("")
    add("inputs")
    for label, path in paths:
        display_path = path
        if path and os.path.commonpath((repo_root, os.path.abspath(path))) == repo_root:
            display_path = os.path.relpath(path, repo_root)
        if path and os.path.exists(path):
            add("  %-6s %s  sha256=%s" % (label, display_path, sha256_file(path)))
        else:
            add("  %-6s %s  (missing)" % (label, display_path))
    add("")
    add("counts")
    add("  pack lines       %d (%d distinct metro lines)"
        % (len(pack["lines"]), len({l["name"] for l in pack["lines"]})))
    add("  stations         %d" % len(pack["stations"]))
    add("  cells            %d" % len(pack["cells"]))
    add("  stations w/cells %d" % len({c["stationCode"] for c in pack["cells"]}))
    ambiguous = anomalies["duplicate_cids"]
    ambiguous_codes = {code for codes in ambiguous.values() for code in codes}
    unique_codes = {
        cell["stationCode"] for cell in pack["cells"]
        if cell["cellId"] not in ambiguous
    }
    ambiguous_only = [
        station for station in pack["stations"]
        if station["code"] in ambiguous_codes and station["code"] not in unique_codes
    ]
    add("  distinct CIDs    %d" % len({cell["cellId"] for cell in pack["cells"]}))
    add("  ambiguous CIDs   %d (%d cell rows)" %
        (len(ambiguous), sum(len(codes) for codes in ambiguous.values())))
    add("  stations with unique CID %d" % len(unique_codes))
    add("  stations with ambiguous CIDs only %d" % len(ambiguous_only))
    add("  nameFixes        %d" % len(pack["nameFixes"]))
    add("  routeAliases     %d" % len(pack["routeAliases"]))
    add("  cellMatchMode    %s" % pack["cellMatchMode"])
    applied = anomalies["codes_override_applied"]
    add("  stable codes     %d override(s) applied from station-codes.json%s"
        % (len(applied), ": " + ", ".join(i["code"] for i in applied) if applied else ""))
    add("                   every other station gets a stable hz_sNNN code in first-appearance "
        "order")
    add("")

    dropped_records = sum(i.get("records", 0) for i in anomalies["bs_unmatched"])
    add("[A] unmatched station names (cell material station with no line station)")
    if not anomalies["bs_unmatched"]:
        add("  none (no cell record dropped)")
    for item in anomalies["bs_unmatched"]:
        add("  %s (%d records dropped)" % (item["name"], item["records"]))
    add("  total dropped cell records: %d" % dropped_records)
    add("")

    add("[A2] cell-material station names merged into another station (name alias)")
    if not anomalies["bs_aliased"]:
        add("  none")
    for item in sorted(anomalies["bs_aliased"], key=lambda i: (i["from"], i["to"])):
        add("  %s -> %s" % (item["from"], item["to"]))
    add("")

    add("[B] line stations without any cell record (pack station that can never match)")
    if not anomalies["stations_without_cells"]:
        add("  none")
    for item in anomalies["stations_without_cells"]:
        add("  %s %s" % (item["code"], item["displayName"]))
    add("")

    add("[B2] stations with cells but no unique CID (cannot match from a single CID without history)")
    if not ambiguous_only:
        add("  none")
    for station in ambiguous_only:
        add("  %s %s" % (station["code"], station["displayName"]))
    add("")

    add("[C] duplicate CIDs claimed by more than one station (%d cid values)"
        % len(anomalies["duplicate_cids"]))
    for cid in sorted(anomalies["duplicate_cids"]):
        owners = anomalies["duplicate_cids"][cid]
        add("  %s -> %s" % (cid, ", ".join(owners)))
    add("  note: kept in the pack; the matcher stays fail-closed when a CID maps to "
        "several stations unless the previous station is among them")
    add("")

    add("[D] topology")
    for item in anomalies["duplicate_stations_in_branch"]:
        add("  BREAK duplicate station inside one branch: %s" % json.dumps(item, ensure_ascii=False))
    for item in anomalies["topology_breaks"]:
        add("  BREAK %s" % json.dumps(item, ensure_ascii=False))
    for item in anomalies["branch_junctions"]:
        add("  %s branches: %s" % (item["line"], ", ".join(
            "%s+%s share %d (%s)" % (j["left"], j["right"], j["overlap"], "/".join(j["shared"]))
            for j in item["junctions"])))
        add("    represented as one pack line per branch so no false linear order is invented; "
            "the Y topology keeps its three terminals")
    if not anomalies["branch_junctions"] and not anomalies["topology_breaks"]:
        add("  no branched line, no break")
    add("")

    add("[E] lines without realtime ETA support (excluded from the pack)")
    for item in anomalies["excluded_lines"]:
        add("  %s: %s" % (item["line"], item["reason"]))
        add("    raw stations %d, dropped %d, kept because another line serves them %d %s"
            % (item["rawStations"], len(item["droppedStations"]), len(item["keptStations"]),
               "/".join(item["keptStations"])))
        if item["droppedStations"]:
            add("    dropped: %s" % ", ".join(item["droppedStations"]))
    add("  note: 1-10/16/19 are covered by the realtime source; branch services 3号线往石马 and "
        "6号线往双浦 are reached through routeAliases")
    add("  note: the pack schema has no per-line 'no realtime ETA' flag, so an uncovered line "
        "cannot be shipped without claiming ETA support it does not have; it is left out instead")
    add("  pack lines with no cell data: %s"
        % (", ".join(i["id"] for i in anomalies["lines_without_cells"]) or "none"))
    add("")

    add("[F] raw fields deliberately not converted")
    add("  lo/s/ot: semantics unverified in this pass, never interpreted as coordinates, "
        "operator or network identity")
    add("  mcc/mnc/tacOrLac: absent from the material, so LOCAL_CID_COMPAT cells carry explicit "
        "unknown placeholders (0/0/0); no full-identity data is fabricated")
    add("")

    add("[G] ibus stop names that need an online check against getMetroInfoList")
    if not anomalies["unverified_ibus_names"]:
        add("  none")
    for item in anomalies["unverified_ibus_names"]:
        add("  %s %s -> %s" % (item["code"], item["displayName"], item["ibusStopName"]))
    add("")

    if anomalies["invalid_cids"] or anomalies["unknown_codes"] or anomalies["alias_problems"]:
        add("[H] rejected input records / alias problems")
        for item in anomalies["invalid_cids"]:
            add("  invalid cell record %s" % json.dumps(item, ensure_ascii=False, sort_keys=True))
        for code in anomalies["unknown_codes"]:
            add("  station code not referenced by any line: %s" % code)
        for item in anomalies["alias_problems"]:
            add("  routeAlias problem %s" % json.dumps(item, ensure_ascii=False, sort_keys=True))
        add("")

    add("conventions baked into the pack")
    add("  displayName      raw material station name, trailing 站 kept as-is")
    add("  ibusStopName     KEEP-suffix rule + nameFixes, i.e. HangzhouStationNames."
        "toIbusStopName (城站/火车东站/火车西站/火车南站/临平南高铁站/永福站 keep 站)")
    add("  line entries     one pack line per raw branch (3-1/3-2, 6-1/6-2), so the Y topology, "
        "the branch direction and all three terminals survive without inventing a linear order")
    add("  direction        the app builds 往{terminal displayName}; directionKey strips "
        "往/方向/站, so ibus destinan still matches")
    add("  station codes    the accepted prototype codes are pinned in station-codes.json, every "
        "other station gets hz_sNNN in first-appearance order")
    add("  determinism      no timestamps, fixed key order, stable sorting; rerunning over the "
        "same inputs rewrites byte identical files")
    add("")

    add("self check (strict decoder equivalent), all passed:")
    for check in checks:
        add("  - %s" % check)
    add("")
    return "\n".join(out) + "\n"


# --- main ------------------------------------------------------------------


def main(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    device_metro = os.path.normpath(os.path.join(here, "..", "..", "metro"))
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--line", default=os.path.join(here, "raw", "hz_line_v2.decompressed.json"))
    parser.add_argument("--bs", default=os.path.join(here, "raw", "hz_bs_v2.decoded.json"))
    parser.add_argument("--codes", default=os.path.join(here, "station-codes.json"))
    parser.add_argument("--out", default=os.path.join(device_metro, "hangzhou-v2.json"))
    parser.add_argument("--report", default=os.path.join(device_metro, "hz-pack-report.txt"))
    parser.add_argument("--no-write", action="store_true",
                        help="build and self check only, do not touch the output files")
    parser.add_argument("--check", action="store_true",
                        help="verify checked-in pack and report match the raw inputs, without writing")
    args = parser.parse_args(argv)

    for path in (args.line, args.bs):
        if not os.path.exists(path):
            raise SystemExit("missing input: " + path)

    code_overrides = {}
    if os.path.exists(args.codes):
        code_overrides = {str(k): str(v) for k, v in load_json(args.codes).items()}

    pack, anomalies = build_pack(load_json(args.line), load_json(args.bs), code_overrides)
    checks = validate_pack(pack)

    report = render_report(
        pack,
        anomalies,
        (("line", args.line), ("bs", args.bs), ("codes", args.codes)),
        checks,
    )
    pack_text = json.dumps(pack, ensure_ascii=False, indent=2) + "\n"

    if args.check:
        for path, expected in ((args.out, pack_text), (args.report, report)):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    actual = handle.read()
            except OSError as exc:
                raise SystemExit("pack check failed: cannot read %s: %s" % (path, exc))
            if actual != expected:
                raise SystemExit("pack check failed: %s differs from generated content" % path)
        print("pack check passed: generated pack and report match checked-in files")
        return 0

    sys.stdout.write(report)

    if not args.no_write:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(pack_text)
        with open(args.report, "w", encoding="utf-8") as handle:
            handle.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

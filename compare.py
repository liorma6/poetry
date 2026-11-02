"""Compare the unchanged suite on a PR's parent and the submitted revision."""

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def read_report(name):
    path = Path(f"{name}.xml")
    if not path.exists():
        raise RuntimeError(f"{name}: no JUnit report; test execution did not finish")
    root = ET.parse(path).getroot()
    cases = {}
    for case in root.iter("testcase"):
        key = f"{case.attrib['classname']}::{case.attrib['name']}"
        status = "passed"
        for kind in ("failure", "error", "skipped"):
            if case.find(kind) is not None:
                status = kind
                break
        if key in cases:
            raise RuntimeError(f"Duplicate test in {name}: {key}")
        cases[key] = status
    if len(cases) < 3000:
        raise RuntimeError(f"{name}: unexpectedly incomplete suite ({len(cases)} tests)")
    return cases


baseline = read_report("baseline")
patch = read_report("patch")
added = "tests.config.test_config_source::test_config_source_migration_apply_missing_key_is_noop"
if added in baseline or patch.get(added) != "passed":
    raise RuntimeError("The added regression test must be new and must pass")
unchanged = {key: value for key, value in patch.items() if key != added}
differences = sorted(key for key in baseline.keys() | unchanged.keys() if baseline.get(key) != unchanged.get(key))
lines = [f"## Python {sys.version.split()[0]}", "", "| Revision | Passed | Failed | Errors | Skipped |", "|---|---:|---:|---:|---:|"]
for name, cases in (("Parent aa601cd", baseline), ("PR 2ae722a", patch)):
    counts = [sum(value == kind for value in cases.values()) for kind in ("passed", "failure", "error", "skipped")]
    lines.append(f"| {name} | " + " | ".join(map(str, counts)) + " |")
lines += ["", f"Added test: **{patch[added]}**.", f"Changed outcomes in existing tests: **{len(differences)}**.", "", "### Existing failures (also present without the PR)"]
lines += [f"- `{key}`" for key, value in sorted(baseline.items()) if value in ("failure", "error")]
lines += ["", "This comparison does not fix or waive upstream failures. A successful comparison only means that the PR adds no failures and its new test passes."]
report = "\n".join(lines) + "\n"
print(report)
with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
    stream.write(report)
for name in ("baseline", "patch"):
    print(f"\nLast lines from {name}.log:\n")
    print("\n".join(Path(f"{name}.log").read_text(encoding="utf-8").splitlines()[-35:]))
if differences:
    raise RuntimeError(f"Different test outcomes: {differences}")
for name, cases in (("baseline", baseline), ("patch", patch)):
    expected = "failure" if any(value in ("failure", "error") for value in cases.values()) else "success"
    if os.environ[f"{name.upper()}_OUTCOME"] != expected:
        raise RuntimeError(f"{name}: process outcome does not match its report")

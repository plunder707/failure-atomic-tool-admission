#!/usr/bin/env python3
"""Generate publication figures directly from released result artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "figures"
NAVY = "#17324D"
BLUE = "#2C6E9F"
PALE_BLUE = "#EAF2F8"
RED = "#B94343"
PALE_RED = "#F8E9E9"
GREEN = "#2E7D5B"
PALE_GREEN = "#E8F3ED"
GRAY = "#5D6872"
LIGHT = "#F4F6F7"
matplotlib.rcParams["svg.hashsalt"] = "failure-atomic-tool-admission-v0.1.2"


def save_all(fig: plt.Figure, name: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "svg", "pdf"):
        if suffix == "svg":
            metadata = {"Date": "2026-07-30"}
        elif suffix == "pdf":
            fixed = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
            metadata = {
                "Title": name.replace("_", " ").title(),
                "Author": "Andrew Gracey",
                "Creator": "failure-atomic-tool-admission v0.1.2",
                "CreationDate": fixed,
                "ModDate": fixed,
            }
        else:
            metadata = {"Software": "failure-atomic-tool-admission v0.1.2"}
        output = FIGURES / f"{name}.{suffix}"
        fig.savefig(
            output,
            dpi=220 if suffix == "png" else None,
            bbox_inches="tight",
            facecolor="white",
            metadata=metadata,
        )
        if suffix == "svg":
            lines = output.read_text(encoding="utf-8").splitlines()
            output.write_text(
                "\n".join(line.rstrip() for line in lines) + "\n",
                encoding="utf-8",
            )
    plt.close(fig)


def box(
    ax: plt.Axes,
    xy: tuple[float, float],
    width: float,
    height: float,
    text: str,
    *,
    facecolor: str = LIGHT,
    edgecolor: str = NAVY,
    textcolor: str = NAVY,
    fontsize: float = 9.5,
) -> None:
    x, y = xy
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle="round,pad=0.025,rounding_size=0.025",
            linewidth=1.4,
            facecolor=facecolor,
            edgecolor=edgecolor,
        )
    )
    ax.text(
        x + width / 2,
        y + height / 2,
        text,
        ha="center",
        va="center",
        color=textcolor,
        fontsize=fontsize,
        wrap=True,
    )


def arrow(
    ax: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color: str = GRAY,
) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=1.3,
            color=color,
        )
    )


def admission_boundary() -> None:
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6)
    ax.axis("off")
    ax.set_title(
        "Sequential admission leaks partial effects; batch prevalidation does not",
        loc="left",
        fontsize=16,
        fontweight="bold",
        color=NAVY,
        pad=14,
    )
    ax.text(0.15, 4.85, "Sequential baseline", fontsize=12, fontweight="bold", color=RED)
    ax.text(0.15, 2.15, "Failure-atomic candidate", fontsize=12, fontweight="bold", color=GREEN)
    labels_top = [
        ("Response enters\nhistory", PALE_RED, RED),
        ("Call 1 parses\nand executes", PALE_RED, RED),
        ("Call 2 JSON\nparse fails", PALE_RED, RED),
        ("Partial effect +\ncontaminated history", RED, "white"),
    ]
    labels_bottom = [
        ("Response received;\nactions buffered", PALE_BLUE, BLUE),
        ("Completed narrative\nsplit from actions", PALE_BLUE, BLUE),
        ("Whole batch\nvalidation fails", PALE_GREEN, GREEN),
        ("No dispatch;\ncontent retained", GREEN, "white"),
    ]
    xs = [0.2, 3.2, 6.2, 9.2]
    for row_y, labels in ((3.75, labels_top), (1.05, labels_bottom)):
        for index, (label, face, textcolor) in enumerate(labels):
            edge = RED if row_y > 2 else GREEN
            box(
                ax,
                (xs[index], row_y),
                2.35,
                0.9,
                label,
                facecolor=face,
                edgecolor=edge,
                textcolor=textcolor,
            )
            if index < len(labels) - 1:
                arrow(
                    ax,
                    (xs[index] + 2.38, row_y + 0.45),
                    (xs[index + 1] - 0.05, row_y + 0.45),
                    color=edge,
                )
    ax.text(
        0.2,
        0.25,
        "Invariant: cognition remains continuous; tool admission is atomic; side effects are committed individually.",
        fontsize=10,
        color=GRAY,
    )
    save_all(fig, "admission_boundary")


def protocol_state_machine() -> None:
    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    ax.set_xlim(0, 11.5)
    ax.set_ylim(0, 6.2)
    ax.axis("off")
    ax.set_title(
        "Admission and execution use separate state transitions",
        loc="left",
        fontsize=16,
        fontweight="bold",
        color=NAVY,
        pad=14,
    )
    nodes = {
        "received": ((0.3, 3.9), PALE_BLUE, BLUE),
        "validated": ((3.0, 3.9), PALE_GREEN, GREEN),
        "admitted": ((5.7, 3.9), PALE_GREEN, GREEN),
        "dispatched": ((8.4, 3.9), PALE_BLUE, BLUE),
        "rejected": ((3.0, 1.4), PALE_RED, RED),
        "committed": ((8.8, 1.4), PALE_GREEN, GREEN),
        "failed": ((6.4, 0.25), PALE_RED, RED),
        "unknown": ((9.6, 0.25), "#FFF3D9", "#9B6500"),
        "content retained /\nreissue": ((0.2, 1.4), LIGHT, GRAY),
    }
    sizes = {
        "content retained /\nreissue": (2.0, 0.85),
        "committed": (1.8, 0.85),
        "failed": (1.6, 0.85),
        "unknown": (1.6, 0.85),
    }
    for label, (xy, face, edge) in nodes.items():
        width, height = sizes.get(label, (2.0, 0.85))
        box(ax, xy, width, height, label, facecolor=face, edgecolor=edge, textcolor=edge)
    arrow(ax, (2.32, 4.33), (2.95, 4.33), color=GREEN)
    arrow(ax, (5.02, 4.33), (5.65, 4.33), color=GREEN)
    arrow(ax, (7.72, 4.33), (8.35, 4.33), color=BLUE)
    arrow(ax, (1.32, 3.88), (3.5, 2.3), color=RED)
    arrow(ax, (3.0, 1.83), (2.25, 1.83), color=GRAY)
    arrow(ax, (9.4, 3.88), (9.62, 2.3), color=GREEN)
    arrow(ax, (9.2, 3.88), (7.25, 1.12), color=RED)
    arrow(ax, (9.75, 3.88), (10.35, 1.12), color="#9B6500")
    ax.text(1.7, 3.1, "invalid batch", fontsize=9, color=RED)
    ax.text(2.46, 2.02, "preserve clean text only", fontsize=8.5, color=GRAY)
    ax.text(
        0.3,
        5.35,
        "Only a fully validated batch can cross the admission boundary.",
        fontsize=10.5,
        color=GRAY,
    )
    save_all(fig, "protocol_state_machine")


def fault_matrix() -> None:
    data = json.loads((ROOT / "artifact/results/fault_injection.json").read_text())
    summary = data["summary"]
    positions = summary["byte_fault_positions_tested"]
    baseline = [
        summary["byte_fault_baseline_partial_effect_count"],
        summary["byte_fault_baseline_history_contamination_count"],
    ]
    candidate = [
        summary["byte_fault_candidate_partial_effect_count"],
        summary["byte_fault_candidate_history_contamination_count"],
    ]
    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    x = [0, 1]
    width = 0.34
    bars_a = ax.bar(
        [value - width / 2 for value in x],
        baseline,
        width,
        label="Sequential baseline",
        color=RED,
    )
    bars_b = ax.bar(
        [value + width / 2 for value in x],
        candidate,
        width,
        label="Failure-atomic candidate",
        color=GREEN,
    )
    ax.set_title(
        f"All {positions} nonterminal byte cuts reproduce the boundary contrast",
        loc="left",
        fontsize=15,
        fontweight="bold",
        color=NAVY,
    )
    ax.set_ylabel("Fault positions with observed failure")
    ax.set_xticks(x, ["Partial effect", "Malformed history"])
    ax.set_ylim(0, positions * 1.17)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.2)
    ax.legend(frameon=False, loc="upper right")
    ax.bar_label(bars_a, padding=3, fontweight="bold")
    ax.bar_label(bars_b, padding=3, fontweight="bold")
    ax.text(
        0,
        -0.16,
        "Representative argument: 108 bytes; every prefix followed one valid call.",
        transform=ax.transAxes,
        fontsize=9,
        color=GRAY,
    )
    fig.subplots_adjust(bottom=0.22)
    save_all(fig, "fault_matrix")


def framework_surface_probe() -> None:
    data = json.loads((ROOT / "artifact/results/framework_surface_probe.json").read_text())
    rows = [
        row for row in data["results"]
        if row["surface_kind"] == "executable_path"
    ]
    names = [row["framework"] for row in rows]
    calls = [int(bool(row["call_1_executed"])) for row in rows]
    malformed_state = [int(bool(row["malformed_state_observed"])) for row in rows]
    y = list(range(len(rows)))
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    ax.scatter(calls, y, s=180, color=[RED if value else GREEN for value in calls], marker="s")
    ax.scatter(
        malformed_state,
        [value + 0.18 for value in y],
        s=130,
        color=[RED if value else GREEN for value in malformed_state],
        marker="o",
    )
    ax.set_yticks(y, names)
    ax.set_xticks([0, 1], ["No", "Yes"])
    ax.set_xlim(-0.35, 1.35)
    ax.invert_yaxis()
    ax.set_title(
        "All five tested executable paths partially admitted the mixed batch",
        loc="left",
        fontsize=14.5,
        fontweight="bold",
        color=NAVY,
    )
    ax.grid(axis="x", alpha=0.2)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    for index, row in enumerate(rows):
        label = (
            "partial admission"
            if row["classification"] == "partial_admission_observed"
            else row["classification"].replace("_", " ")
        )
        ax.text(1.08, index + 0.09, label, va="center", fontsize=9, color=GRAY)
    ax.scatter([], [], s=180, color=NAVY, marker="s", label="Valid call executed")
    ax.scatter([], [], s=130, color=NAVY, marker="o", label="Malformed state observed")
    ax.legend(
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.08),
        ncol=2,
    )
    ax.text(
        0,
        -0.21,
        "Separate result: the tested LlamaIndex typed core boundary rejected raw malformed arguments.",
        transform=ax.transAxes,
        fontsize=9,
        color=GRAY,
    )
    fig.subplots_adjust(left=0.22, right=0.82, bottom=0.28)
    save_all(fig, "framework_surface_probe")


def social_preview() -> None:
    fig, ax = plt.subplots(figsize=(12.8, 6.4), dpi=100)
    ax.set_xlim(0, 12.8)
    ax.set_ylim(0, 6.4)
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), 0.18, 6.4, color=GREEN))
    ax.text(
        0.75,
        5.25,
        "Continuous Cognition,\nFailure-Atomic Actuation",
        fontsize=27,
        fontweight="bold",
        color=NAVY,
        va="top",
    )
    ax.text(
        0.78,
        2.95,
        "Validate every tool call before admitting any of them.",
        fontsize=14,
        color=GRAY,
    )
    box(
        ax,
        (0.78, 1.15),
        3.25,
        1.1,
        "107 / 107\nbaseline partial effects",
        facecolor=PALE_RED,
        edgecolor=RED,
        textcolor=RED,
        fontsize=12,
    )
    box(
        ax,
        (4.35, 1.15),
        3.25,
        1.1,
        "0 / 107\ncandidate partial effects",
        facecolor=PALE_GREEN,
        edgecolor=GREEN,
        textcolor=GREEN,
        fontsize=12,
    )
    box(
        ax,
        (7.92, 1.15),
        3.85,
        1.1,
        "5 executable paths\npartial admission observed",
        facecolor=PALE_BLUE,
        edgecolor=BLUE,
        textcolor=BLUE,
        fontsize=11,
    )
    ax.text(0.8, 0.5, "Andrew Gracey | Independent Researcher", fontsize=11, color=NAVY)
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        FIGURES / "social_preview.png",
        dpi=100,
        facecolor="white",
        metadata={"Software": "failure-atomic-tool-admission v0.1.2"},
    )
    plt.close(fig)


def main() -> None:
    admission_boundary()
    protocol_state_machine()
    fault_matrix()
    framework_surface_probe()
    social_preview()
    print(f"wrote publication figures to {FIGURES}")


if __name__ == "__main__":
    main()

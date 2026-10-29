#!/usr/bin/env python3
"""Plots of the delay between the coex request and grant pins.

Single run (histogram, request/wait portions, time contribution, raw values):
    python delay_plotter.py <num_delays_below_10ms> <total_test_ms> <delay> [<delay> ...]
    ex: python delay_plotter.py 9651 100001 401 141 205 86 158

Compare policies (survival curve + markdown table of tail metrics, runs pooled):
    python delay_plotter.py --compare data.md --pool 0 4 --name "Baseline coex policy (700x)" \
        --pool 1 2 --name "Early request (REQ preemption)" [--max-ms 900] [--tail-ms 350 450 550]

Plots open in windows; nothing is saved to disk.
"""

import argparse
import re
import sys
from collections import Counter

import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

SMALL_LIMIT = 10  # delays below this are only counted, never listed
BUCKET_WIDTH = 50

SMALL_COLOR = "#4C78A8"
LONG_COLOR = "#E45756"


def set_window_title(fig, title):
    """Name the plot window (no manager when running headless)."""
    if fig.canvas.manager is not None:
        fig.canvas.manager.set_window_title(title)


def bucket_start(delay):
    """Lower edge of the bucket: 10 for 10-49, else the multiple of 50 at or below."""
    if delay < BUCKET_WIDTH:
        return SMALL_LIMIT
    return (delay // BUCKET_WIDTH) * BUCKET_WIDTH


def bucket_label(start):
    if start == SMALL_LIMIT:
        return f"{SMALL_LIMIT}-{BUCKET_WIDTH - 1}"
    return f"{start}-{start + BUCKET_WIDTH - 1}"


def build_buckets(num_small, delays):
    """Return (labels, counts) with <10 first and empty buckets kept in between."""
    counts = Counter(bucket_start(d) for d in delays)
    labels = [f"<{SMALL_LIMIT}"]
    values = [num_small]

    if counts:
        starts = [SMALL_LIMIT] + list(range(BUCKET_WIDTH, max(counts) + 1, BUCKET_WIDTH))
        for start in starts:
            labels.append(bucket_label(start))
            values.append(counts.get(start, 0))

    return labels, values


def plot_histogram(num_small, delays):
    """Occurrences per delay bucket, log y-axis."""
    labels, values = build_buckets(num_small, delays)

    fig, ax = plt.subplots(figsize=(max(6, 0.6 * len(labels)), 5))
    set_window_title(fig, "Delay Histogram")
    bars = ax.bar(labels, values, width=0.9, edgecolor="black")
    ax.set_yscale("log")
    ax.set_xlabel("Delay (ms)")
    ax.set_ylabel("Occurrences (log-scale)")
    ax.set_title("Delay Between Request and Grant Pin")
    ax.bar_label(bars, labels=[str(v) if v else "" for v in values], padding=2)
    ax.margins(y=0.15)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    fig.tight_layout()
    return fig


def time_split(num_small, total_ms, delays):
    """(time in logged waits, upper bound on time in the unlogged < SMALL_LIMIT waits)."""
    long_ms = sum(delays)
    rest_ms = total_ms - long_ms
    small_max_ms = min(num_small * SMALL_LIMIT, rest_ms)
    return long_ms, small_max_ms


def plot_portions(num_small, total_ms, delays):
    """Share of requests vs share of waiting time, 100% stacked bars."""
    long_ms, small_max_ms = time_split(num_small, total_ms, delays)
    n_long = len(delays)

    req_total = num_small + n_long
    wait_total = small_max_ms + long_ms
    req_shares = [100 * num_small / req_total, 100 * n_long / req_total]
    wait_shares = [100 * small_max_ms / wait_total, 100 * long_ms / wait_total]

    fig, ax = plt.subplots(figsize=(9, 4))
    set_window_title(fig, "Request and Delay Portions")
    rows = ["Portion of Requests", "Portion of Waiting Time"]
    for y, (small, long_) in enumerate([req_shares, wait_shares]):
        ax.barh(y, small, color=SMALL_COLOR, edgecolor="white",
                label=f"<{SMALL_LIMIT} ms" if y == 0 else None)
        ax.barh(y, long_, left=small, color=LONG_COLOR, edgecolor="white",
                label=f">={SMALL_LIMIT} ms" if y == 0 else None)
        if small > 6:
            ax.text(small / 2, y, f"{small:.1f}%", ha="center", va="center", color="white")
        if long_ > 6:
            ax.text(small + long_ / 2, y, f"{long_:.1f}%", ha="center", va="center",
                    color="white")
        elif long_ > 0:
            ax.text(100.5, y, f"{long_:.1f}%", ha="left", va="center", color=LONG_COLOR)
    ax.set_yticks(range(len(rows)), rows)
    ax.set_xlim(0, 108)
    ax.set_xlabel("Portion (Percent)")
    ax.invert_yaxis()
    ax.set_title("Comparison of Request and Delay Timings")
    ax.legend(loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.25))
    fig.tight_layout()
    return fig


def plot_contribution(total_ms, delays):
    """Histogram weighted by time, each bucket as % of the test."""
    counts = Counter()
    for d in delays:
        counts[bucket_start(d)] += d

    starts = [SMALL_LIMIT] + list(range(BUCKET_WIDTH, max(counts, default=SMALL_LIMIT) + 1,
                                        BUCKET_WIDTH))
    labels = [bucket_label(s) for s in starts]
    shares = [100 * counts.get(s, 0) / total_ms for s in starts]

    fig, ax = plt.subplots(figsize=(max(6, 0.6 * len(labels)), 5))
    set_window_title(fig, "Contribution to Test Delay")
    bars = ax.bar(labels, shares, width=0.9, color=LONG_COLOR, edgecolor="black")
    ax.set_xlabel("Delay (ms)")
    ax.set_ylabel("Portion of Test Delay (Percent)")
    ax.set_title("Contribution to Test Delay")
    ax.bar_label(bars, labels=[f"{s:.1f}%" if s else "" for s in shares], padding=2, fontsize=8)
    ax.margins(y=0.15)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    fig.tight_layout()
    return fig


def plot_raw(delays):
    """One bar per unique delay value, placed on a number line."""
    counts = Counter(delays)
    xs = sorted(counts)
    ys = [counts[x] for x in xs]

    fig, ax = plt.subplots(figsize=(11, 5))
    set_window_title(fig, "Raw Delay Values")
    ax.bar(xs, ys, width=max(xs) / 250, color=LONG_COLOR)
    ax.set_xlabel("Delay (ms)")
    ax.yaxis.set_major_locator(MultipleLocator(5))
    ax.set_ylabel("Occurrences")
    ax.set_title("Raw Delay Values")
    fig.tight_layout()
    return fig


# ---- compare mode: pool runs from data.md and compare their tails ----
COMPARE_STEP_MS = 10
PERCENTILES = (90, 95, 99)


def parse_runs(path):
    """[(label, delays)] per "specific delays above" line; label = nearest text line above."""
    runs, label = [], "run"
    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if "specific delays above" in line:
                runs.append((label, [int(t) for t in line.split(":", 1)[1].split()]))
            elif not line.startswith("[") and not re.match(r"\d+:\d", line):
                label = line  # not a log line
    return runs


def is_baseline(label):
    label = label.lower()
    return label.startswith("base") or "baseline" in label or "no early" in label


def pooled(group):
    return [d for delays in group for d in delays]


def plot_survival(groups, max_ms=None):
    """Count of waits >= x vs x (complementary CDF), log y. Baseline blue, others orange."""
    fig, ax = plt.subplots(figsize=(10, 6))
    set_window_title(fig, "Wait Complementary CDF")
    top = max_ms or max(max(pooled(g)) for _, g in groups)
    xs = list(range(SMALL_LIMIT, top + COMPARE_STEP_MS, COMPARE_STEP_MS))
    colors = iter(["C1", "C2", "C3", "C4"])
    for label, group in groups:
        delays = pooled(group)
        ys = [sum(1 for d in delays if d >= x) for x in xs]
        last = max((j for j, y in enumerate(ys) if y > 0), default=-1)  # log axis: drop zeros
        if last < 0:
            continue
        color = "C0" if is_baseline(label) else next(colors)
        ax.step(xs[:last + 1], ys[:last + 1], where="post", color=color, linewidth=1.8,
                label=label)
    ax.set_yscale("log")
    ax.set_xlabel("Wait length (ms)")
    ax.set_ylabel("Remaining number of delays, runs pooled (log scale)")
    ax.set_title("Total delay survival curve")
    ax.xaxis.set_major_locator(MultipleLocator(100))
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def tail_metrics(delays, tail_ms):
    """[(row name, value)]: counts and seconds in waits >= each threshold, percentiles."""
    ordered = sorted(delays)
    rows = [(f"Waits \u2265 {t} ms", sum(1 for d in delays if d >= t)) for t in tail_ms]
    rows += [(f"Time stalled in waits \u2265 {t} ms (s)", sum(d for d in delays if d >= t) / 1000)
             for t in tail_ms]
    rows += [(f"{p}th percentile wait (ms)",
              ordered[min(len(ordered) - 1, int(p / 100 * len(ordered)))]) for p in PERCENTILES]
    return rows


def print_tail_table(groups, tail_ms):
    """Markdown table of pooled tail metrics with % change vs the baseline group."""
    metrics = [tail_metrics(pooled(g), tail_ms) for _, g in groups]
    base = next((i for i, (label, _) in enumerate(groups) if is_baseline(label)), 0)
    others = [i for i in range(len(groups)) if i != base]
    order = [base] + others
    change = ["Change"] if len(others) == 1 else [f"Change ({groups[i][0]})" for i in others]
    header = ["Metric"] + [groups[i][0] for i in order] + change
    print("\n| " + " | ".join(header) + " |")
    print("|" + "---|" * len(header))
    for r, (name, base_val) in enumerate(metrics[base]):
        row = [name] + [f"{metrics[i][r][1]:.3g}" for i in order]
        row += [f"{100 * (metrics[i][r][1] - base_val) / base_val:+.0f}%" if base_val else "n/a"
                for i in others]
        print("| " + " | ".join(row) + " |")
    print("\n(runs pooled per column: " +
          ", ".join(f"{label} = {len(g)}" for label, g in groups) + ")")


def compare_main(argv):
    parser = argparse.ArgumentParser(description="Compare pooled runs from data.md")
    parser.add_argument("--compare", metavar="FILE", required=True, help="data.md log")
    parser.add_argument("--pool", type=int, nargs="+", action="append", required=True,
                        metavar="I", help="run indices (file order, from 0) pooled into one "
                                          "data set; repeat per policy")
    parser.add_argument("--name", action="append", default=[],
                        help="legend/column name for each --pool, in order")
    parser.add_argument("--max-ms", type=int, help="x-axis limit in ms")
    parser.add_argument("--tail-ms", type=int, nargs="+", default=[350, 450, 550],
                        help="tail thresholds in ms (default 350 450 550)")
    args = parser.parse_args(argv)

    runs = parse_runs(args.compare)
    if not runs:
        parser.error(f"no 'specific delays above' lines in {args.compare}")
    for i, (label, delays) in enumerate(runs):
        print(f"[{i}] {len(delays):4d} waits >= {SMALL_LIMIT} ms  {label}")
    bad = [i for g in args.pool for i in g if not 0 <= i < len(runs)]
    if bad:
        parser.error(f"run indices out of range: {bad}")
    if len(args.name) > len(args.pool):
        parser.error("more --name values than --pool groups")

    groups = [(args.name[k] if k < len(args.name) else runs[g[0]][0], [runs[i][1] for i in g])
              for k, g in enumerate(args.pool)]
    plot_survival(groups, args.max_ms)
    print_tail_table(groups, args.tail_ms)
    plt.show()


def main():
    if "--compare" in sys.argv[1:]:
        compare_main(sys.argv[1:])
        return
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("num_small", type=int,
                        help=f"number of delays below {SMALL_LIMIT} ms")
    parser.add_argument("total_ms", type=int, help="total time of the test in ms")
    parser.add_argument("delays", type=int, nargs="*",
                        help=f"space-separated delays of {SMALL_LIMIT} ms or more")
    args = parser.parse_args()

    if args.num_small < 0 or any(d < SMALL_LIMIT for d in args.delays):
        parser.error(f"num_small must be >= 0 and listed delays must be >= {SMALL_LIMIT} ms")
    if not args.delays:
        parser.error(f"at least one delay of {SMALL_LIMIT} ms or more is required")
    if args.total_ms <= sum(args.delays):
        parser.error(f"total_ms ({args.total_ms}) must exceed the sum of the listed delays "
                     f"({sum(args.delays)})")

    plot_histogram(args.num_small, args.delays)
    plot_portions(args.num_small, args.total_ms, args.delays)
    plot_contribution(args.total_ms, args.delays)
    plot_raw(args.delays)
    plt.show()


if __name__ == "__main__":
    main()

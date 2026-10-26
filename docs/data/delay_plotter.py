#!/usr/bin/env python3
"""Plots of the delay between the coex request and grant pin

Usage:
    python delay_plotter.py <num_delays_below_10ms> <total_test_ms> <delay> [<delay> ...]
                            [--save <dir>]
    ex: python delay_plotter.py 9651 100001 401 141 205 86 158

Opens one window per plot, all at once. With --save <dir> the plots are written
to <dir> as PNGs instead.

Plots: delay histogram (buckets <10, 10-49, 50-99, 100-149, etc.), request vs
waiting-time portions, each bucket's contribution to test delay, and the raw delay values.
"""

import argparse
import os
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
    """Long-delay time is exact. Everything else is total minus that.

    The time spent in the <10 ms requests is not logged, only bounded: each one
    is under SMALL_LIMIT ms, so their total is at most num_small * SMALL_LIMIT.
    """
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


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("num_small", type=int,
                        help=f"number of delays below {SMALL_LIMIT} ms")
    parser.add_argument("total_ms", type=int, help="total time of the test in ms")
    parser.add_argument("delays", type=int, nargs="*",
                        help=f"space-separated delays of {SMALL_LIMIT} ms or more")
    parser.add_argument("--save", metavar="DIR",
                        help="write the plots to DIR as PNGs instead of opening windows")
    args = parser.parse_args()

    if args.num_small < 0 or any(d < SMALL_LIMIT for d in args.delays):
        parser.error(f"num_small must be >= 0 and listed delays must be >= {SMALL_LIMIT} ms")
    if not args.delays:
        parser.error(f"at least one delay of {SMALL_LIMIT} ms or more is required")
    if args.total_ms <= sum(args.delays):
        parser.error(f"total_ms ({args.total_ms}) must exceed the sum of the listed delays "
                     f"({sum(args.delays)})")

    figs = {
        "histogram": plot_histogram(args.num_small, args.delays),
        "portions": plot_portions(args.num_small, args.total_ms, args.delays),
        "contribution": plot_contribution(args.total_ms, args.delays),
        "raw_values": plot_raw(args.delays),
    }

    if args.save:
        os.makedirs(args.save, exist_ok=True)
        for name, fig in figs.items():
            path = os.path.join(args.save, f"{name}.png")
            fig.savefig(path, dpi=200)
            print(f"Saved {path}")
    else:
        plt.show()


if __name__ == "__main__":
    main()

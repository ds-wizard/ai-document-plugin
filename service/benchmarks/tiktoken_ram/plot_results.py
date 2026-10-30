"""Turns the raw samples into per-run and averaged RAM plots, plus CSV summaries."""

import argparse
import json
from pathlib import Path

import matplotlib as mpl

mpl.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

MODES = ['tiktoken', 'approx']
LABELS = {'tiktoken': 'With tiktoken', 'approx': 'Without tiktoken (len // 4)'}
COLORS = {'tiktoken': '#2a78d6', 'approx': '#eb6834'}
SURFACE = '#fcfcfb'
TEXT_PRIMARY = '#0b0b0b'
TEXT_SECONDARY = '#52514e'
GRID = '#e4e3df'
GRID_STEP_SECONDS = 0.5
KB_PER_MIB = 1024
END_WINDOW_SECONDS = 5.0


def load_runs(results_dir: Path) -> list[dict]:
    runs = []
    for meta_path in sorted((results_dir / 'raw').glob('*.json')):
        meta = json.loads(meta_path.read_text())
        # The sampler is killed with the container, which can leave a partial last line.
        samples = pd.read_csv(meta_path.with_suffix('.csv')).dropna(subset=['vmrss_kb', 'vmhwm_kb', 'rssanon_kb'])
        # Every run is aligned on the moment the pipeline was requested.
        samples['t'] = (samples['epoch_ms'] - meta['pipeline_start_ms']) / 1000
        meta['duration'] = (meta['pipeline_end_ms'] - meta['pipeline_start_ms']) / 1000
        runs.append({**meta, 'samples': samples})
    return runs


def summarize_run(run: dict) -> dict:
    samples = run['samples']
    before = samples[samples['t'] < 0]
    end_t = samples['t'].max()
    after = samples[samples['t'] >= end_t - END_WINDOW_SECONDS]
    return {
        'mode': run['mode'],
        'round': run['round'],
        'idle_before_pipeline_mib': before['vmrss_kb'].iloc[-1] / KB_PER_MIB,
        'peak_mib': samples['vmhwm_kb'].max() / KB_PER_MIB,
        'idle_after_pipeline_mib': after['vmrss_kb'].median() / KB_PER_MIB,
        'idle_after_pipeline_anon_mib': after['rssanon_kb'].median() / KB_PER_MIB,
        'pipeline_seconds': run['duration'],
        'assignment_calls': run['assignment_calls'],
        'generation_calls': run['generation_calls'],
    }


def average_series(runs: list[dict]) -> pd.DataFrame:
    """Interpolates runs onto a shared time grid, kept only where every run has data."""
    start = max(run['samples']['t'].min() for run in runs)
    end = min(run['samples']['t'].max() for run in runs)
    grid = np.arange(start, end, GRID_STEP_SECONDS)
    values = np.array([np.interp(grid, run['samples']['t'], run['samples']['vmrss_kb']) for run in runs]) / KB_PER_MIB
    return pd.DataFrame({'t': grid, 'mean': values.mean(axis=0), 'min': values.min(axis=0), 'max': values.max(axis=0)})


def style_axes(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    ax.grid(axis='y', color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ('top', 'right', 'left'):
        ax.spines[side].set_visible(False)
    ax.spines['bottom'].set_color(GRID)
    ax.tick_params(colors=TEXT_SECONDARY, length=0)
    ax.set_xlabel('Seconds since the pipeline was requested', color=TEXT_SECONDARY)
    ax.axvline(0, color=TEXT_SECONDARY, linewidth=0.8, linestyle=(0, (3, 3)))
    ax.set_ylim(bottom=0)


def plot_runs(runs_by_mode: dict[str, list[dict]], path: Path) -> None:
    fig, axes = plt.subplots(1, len(runs_by_mode), figsize=(12, 5), sharex=True, sharey=True, facecolor=SURFACE)
    for ax, (mode, runs) in zip(np.atleast_1d(axes), runs_by_mode.items(), strict=True):
        for run in runs:
            ax.plot(run['samples']['t'], run['samples']['vmrss_kb'] / KB_PER_MIB, color=COLORS[mode], linewidth=1.2, alpha=0.8)
        style_axes(ax)
        ax.set_title(f'{LABELS[mode]}: {len(runs)} runs', color=TEXT_PRIMARY, loc='left', fontsize=12)
    np.atleast_1d(axes)[0].set_ylabel('Service memory, VmRSS (MiB)', color=TEXT_SECONDARY)
    fig.suptitle('RAM usage of each run', color=TEXT_PRIMARY, x=0.01, ha='left', fontsize=15)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_average(averages: dict[str, pd.DataFrame], runs_by_mode: dict[str, list[dict]], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.5), facecolor=SURFACE)
    for mode, average in averages.items():
        ax.fill_between(average['t'], average['min'], average['max'], color=COLORS[mode], alpha=0.18, linewidth=0)
        ax.plot(average['t'], average['mean'], color=COLORS[mode], linewidth=2, label=LABELS[mode])
    style_axes(ax)

    # The higher line is labelled above its end and the lower one below, so the labels can't collide.
    order = sorted(averages, key=lambda mode: averages[mode]['mean'].iloc[-1], reverse=True)
    for index, mode in enumerate(order):
        last = averages[mode].iloc[-1]
        ax.annotate(
            f'{LABELS[mode]}: {last["mean"]:.0f} MiB',
            xy=(last['t'], last['mean']),
            xytext=(0, 8 if index == 0 else -8),
            textcoords='offset points',
            ha='right',
            va='bottom' if index == 0 else 'top',
            color=TEXT_PRIMARY,
            fontsize=10,
        )

    ax.annotate(
        'Pipeline requested',
        xy=(0, 0),
        xycoords=('data', 'axes fraction'),
        xytext=(4, 6),
        textcoords='offset points',
        color=TEXT_SECONDARY,
        fontsize=9,
    )
    ax.set_ylabel('Service memory, VmRSS (MiB)', color=TEXT_SECONDARY)
    calls = ', '.join(
        f'{LABELS[mode]}: {int(np.median([run["assignment_calls"] for run in runs]))} chunks'
        for mode, runs in runs_by_mode.items()
    )
    ax.set_title(f'Average RAM usage, with the min-max range across runs\n{calls}', color=TEXT_PRIMARY, loc='left', fontsize=12)
    legend = ax.legend(loc='upper left', frameon=False)
    for text in legend.get_texts():
        text.set_color(TEXT_SECONDARY)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def print_comparison(summary: pd.DataFrame) -> None:
    medians = summary.groupby('mode').median(numeric_only=True)
    rows = [
        ('Idle before the pipeline (MiB)', 'idle_before_pipeline_mib'),
        ('Peak (MiB)', 'peak_mib'),
        ('Idle after the pipeline (MiB)', 'idle_after_pipeline_mib'),
        ('Pipeline duration (s)', 'pipeline_seconds'),
        ('Chunks (assignment calls)', 'assignment_calls'),
    ]
    print(f'\n{"Median per run":<34}{"tiktoken":>10}{"approx":>10}{"difference":>12}')
    for label, column in rows:
        with_tiktoken = medians.loc['tiktoken', column]
        without = medians.loc['approx', column]
        print(f'{label:<34}{with_tiktoken:>10.1f}{without:>10.1f}{with_tiktoken - without:>12.1f}')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results_dir', type=Path)
    args = parser.parse_args()

    runs = load_runs(args.results_dir)
    runs_by_mode = {mode: [run for run in runs if run['mode'] == mode] for mode in MODES}
    runs_by_mode = {mode: mode_runs for mode, mode_runs in runs_by_mode.items() if mode_runs}
    averages = {mode: average_series(mode_runs) for mode, mode_runs in runs_by_mode.items()}

    summary = pd.DataFrame([summarize_run(run) for run in runs]).sort_values(['mode', 'round'])
    summary.to_csv(args.results_dir / 'summary.csv', index=False, float_format='%.1f')
    pd.concat([average.assign(mode=mode) for mode, average in averages.items()]).to_csv(
        args.results_dir / 'average_timeseries.csv', index=False, float_format='%.2f'
    )
    plot_runs(runs_by_mode, args.results_dir / 'ram_per_run.png')
    plot_average(averages, runs_by_mode, args.results_dir / 'ram_average.png')

    if len(runs_by_mode) == len(MODES):
        print_comparison(summary)
    print(f'\nWrote ram_per_run.png, ram_average.png, summary.csv and average_timeseries.csv to {args.results_dir}')


if __name__ == '__main__':
    main()

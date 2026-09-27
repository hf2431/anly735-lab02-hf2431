# ANLY 735 Replication Laboratory 2

This repository contains a focused proxy replication of the stability–plasticity phenomenon discussed in Klein et al. (2024). It uses a small two-task neural-network experiment to compare retention of a prior task with learning after a condition change.

## Reproduce the analysis

From the repository root, run:

```bash
python code/lab02_analysis.py
```

The script writes `analysis/lab02_trajectory.csv`, `analysis/lab02_summary.csv`, and the two figures in `figures/`. The completed report source is `replication-lab/replication-lab.qmd`, and the Word submission is `replication-lab/replication-lab.docx`.

The experiment uses a fixed random seed (`20250927`). Package versions are listed in `requirements.txt`.

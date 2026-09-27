# Replication Laboratory 2 analysis

Run the controlled proxy experiment from the repository root with:

```bash
python code/lab02_analysis.py
```

The script uses a fixed seed and writes `lab02_trajectory.csv` and
`lab02_summary.csv` to this directory. It also writes the learning and
retention plots to `figures/`. The experiment compares a replay stability
agent, a no-replay agent, and a freshly initialized Task B benchmark.

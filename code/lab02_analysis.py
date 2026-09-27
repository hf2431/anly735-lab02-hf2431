"""Controlled proxy replication for ANLY 735 Replication Laboratory #2.

The experiment creates two binary classification conditions with the same
two-dimensional input space. Task A uses feature 0; after the change, Task B
uses feature 1. A small neural network first learns Task A. After the change,
one agent trains only on new data, while a stability-biased agent trains on
new data plus replayed Task A examples. A newly initialized model provides a
learning-rate benchmark for Task B.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from torch import nn


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = ROOT / "analysis"
FIGURES_DIR = ROOT / "figures"
ANALYSIS_DIR.mkdir(exist_ok=True)
FIGURES_DIR.mkdir(exist_ok=True)

SEED = 20250927
PRETRAIN_EPOCHS = 10
POST_CHANGE_EPOCHS = 10
BATCH_SIZE = 128
LEARNING_RATE = 0.10
REPLAY_WEIGHT = 2.0


def set_seed(seed: int) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)


class SmallMLP(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(2, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x).squeeze(-1)


def make_task(feature: int, n: int, seed: int) -> tuple[torch.Tensor, torch.Tensor]:
    """Generate a balanced task: the label is the sign of one feature."""
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 2)).astype(np.float32)
    y = (x[:, feature] > 0).astype(np.float32)
    return torch.from_numpy(x), torch.from_numpy(y)


def accuracy(model: nn.Module, x: torch.Tensor, y: torch.Tensor) -> float:
    model.eval()
    with torch.no_grad():
        prediction = (torch.sigmoid(model(x)) >= 0.5).float()
    return float((prediction == y).float().mean().item())


def train_epoch(
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    x_new: torch.Tensor,
    y_new: torch.Tensor,
    replay: tuple[torch.Tensor, torch.Tensor] | None = None,
    replay_weight: float = 0.0,
) -> None:
    model.train()
    order = torch.randperm(len(x_new))
    for batch_indices in order.split(BATCH_SIZE):
        optimizer.zero_grad()
        new_loss = nn.functional.binary_cross_entropy_with_logits(
            model(x_new[batch_indices]), y_new[batch_indices]
        )
        loss = new_loss
        if replay is not None and replay_weight > 0:
            replay_indices = torch.randint(0, len(replay[0]), (len(batch_indices),))
            replay_loss = nn.functional.binary_cross_entropy_with_logits(
                model(replay[0][replay_indices]), replay[1][replay_indices]
            )
            loss = loss + replay_weight * replay_loss
        loss.backward()
        optimizer.step()


def fit_task_a(model: nn.Module, optimizer: torch.optim.Optimizer, x_a: torch.Tensor, y_a: torch.Tensor) -> None:
    for _ in range(PRETRAIN_EPOCHS):
        train_epoch(model, optimizer, x_a, y_a)


def new_model(seed: int) -> tuple[SmallMLP, torch.optim.Optimizer]:
    set_seed(seed)
    model = SmallMLP()
    optimizer = torch.optim.SGD(model.parameters(), lr=LEARNING_RATE)
    return model, optimizer


def main() -> None:
    set_seed(SEED)
    x_a, y_a = make_task(feature=0, n=2000, seed=SEED + 1)
    x_b, y_b = make_task(feature=1, n=2000, seed=SEED + 2)
    x_a_test, y_a_test = make_task(feature=0, n=2000, seed=SEED + 3)
    x_b_test, y_b_test = make_task(feature=1, n=2000, seed=SEED + 4)

    # Both persistent agents start from the same initialization and learn Task A.
    replay_agent, replay_optimizer = new_model(SEED + 10)
    no_replay_agent, no_replay_optimizer = new_model(SEED + 10)
    fit_task_a(replay_agent, replay_optimizer, x_a, y_a)
    fit_task_a(no_replay_agent, no_replay_optimizer, x_a, y_a)

    records: list[dict[str, object]] = []
    for name, model in [("Replay stability agent", replay_agent), ("No-replay agent", no_replay_agent)]:
        records.append(
            {
                "agent": name,
                "phase": "before_change",
                "epoch": 0,
                "task_a_accuracy": accuracy(model, x_a_test, y_a_test),
                "task_b_accuracy": accuracy(model, x_b_test, y_b_test),
            }
        )

    for epoch in range(1, POST_CHANGE_EPOCHS + 1):
        train_epoch(
            replay_agent,
            replay_optimizer,
            x_b,
            y_b,
            replay=(x_a, y_a),
            replay_weight=REPLAY_WEIGHT,
        )
        train_epoch(no_replay_agent, no_replay_optimizer, x_b, y_b)
        records.extend(
            [
                {
                    "agent": "Replay stability agent",
                    "phase": "after_change",
                    "epoch": epoch,
                    "task_a_accuracy": accuracy(replay_agent, x_a_test, y_a_test),
                    "task_b_accuracy": accuracy(replay_agent, x_b_test, y_b_test),
                },
                {
                    "agent": "No-replay agent",
                    "phase": "after_change",
                    "epoch": epoch,
                    "task_a_accuracy": accuracy(no_replay_agent, x_a_test, y_a_test),
                    "task_b_accuracy": accuracy(no_replay_agent, x_b_test, y_b_test),
                },
            ]
        )

    # Fresh initialization is a benchmark for learning Task B without prior training.
    fresh_agent, fresh_optimizer = new_model(SEED + 20)
    for epoch in range(1, POST_CHANGE_EPOCHS + 1):
        train_epoch(fresh_agent, fresh_optimizer, x_b, y_b)
        records.append(
            {
                "agent": "Fresh Task B benchmark",
                "phase": "new_initialization",
                "epoch": epoch,
                "task_a_accuracy": accuracy(fresh_agent, x_a_test, y_a_test),
                "task_b_accuracy": accuracy(fresh_agent, x_b_test, y_b_test),
            }
        )

    trajectory = pd.DataFrame(records)
    trajectory.to_csv(ANALYSIS_DIR / "lab02_trajectory.csv", index=False)

    before = trajectory[trajectory["phase"] == "before_change"].set_index("agent")
    after = trajectory[trajectory["phase"] == "after_change"]
    final_after = after.sort_values("epoch").groupby("agent", as_index=False).tail(1).set_index("agent")

    def first_epoch_at_or_above(agent: str, threshold: float = 0.80) -> float:
        rows = trajectory[(trajectory.agent == agent) & (trajectory.task_b_accuracy >= threshold)]
        return float(rows.epoch.min()) if not rows.empty else np.nan

    summary_rows = []
    for agent in ["Replay stability agent", "No-replay agent"]:
        summary_rows.append(
            {
                "agent": agent,
                "task_a_before_change": before.loc[agent, "task_a_accuracy"],
                "task_b_before_change": before.loc[agent, "task_b_accuracy"],
                "task_a_final": final_after.loc[agent, "task_a_accuracy"],
                "task_b_final": final_after.loc[agent, "task_b_accuracy"],
                "task_a_retention_drop": before.loc[agent, "task_a_accuracy"] - final_after.loc[agent, "task_a_accuracy"],
                "epochs_to_task_b_80pct": first_epoch_at_or_above(agent),
            }
        )
    fresh_rows = trajectory[trajectory.agent == "Fresh Task B benchmark"]
    summary_rows.append(
        {
            "agent": "Fresh Task B benchmark",
            "task_a_before_change": np.nan,
            "task_b_before_change": np.nan,
            "task_a_final": fresh_rows.iloc[-1]["task_a_accuracy"],
            "task_b_final": fresh_rows.iloc[-1]["task_b_accuracy"],
            "task_a_retention_drop": np.nan,
            "epochs_to_task_b_80pct": first_epoch_at_or_above("Fresh Task B benchmark"),
        }
    )
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(ANALYSIS_DIR / "lab02_summary.csv", index=False)

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    for agent, group in trajectory.groupby("agent"):
        group = group[group["epoch"] > 0]
        ax.plot(group["epoch"], group["task_b_accuracy"], marker="o", label=agent)
    ax.axhline(0.80, color="gray", linestyle="--", linewidth=1, label="80% recovery threshold")
    ax.set(xlabel="Epochs after Task B begins", ylabel="Task B accuracy", title="New learning after the condition change")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "task_b_learning.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    for agent, group in trajectory[trajectory["phase"] != "new_initialization"].groupby("agent"):
        group = group.sort_values("epoch")
        ax.plot(group["epoch"], group["task_a_accuracy"], marker="o", label=agent)
    ax.set(xlabel="Epochs after Task B begins", ylabel="Task A accuracy", title="Retention of the previously learned task")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "task_a_retention.png", dpi=180)
    plt.close(fig)

    print("Task A training complete; Task B introduced after", PRETRAIN_EPOCHS, "epochs.")
    print(summary.round(3).to_string(index=False))


if __name__ == "__main__":
    main()

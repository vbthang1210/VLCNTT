from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from training.config import NUM_EPOCHS, PROCESSED_DATASET_DIR

DEFAULT_DATASET_DIR = PROCESSED_DATASET_DIR


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--epochs", type=int, default=NUM_EPOCHS)
    args = parser.parse_args()
    if args.epochs < 1:
        parser.error("--epochs must be >= 1")

    try:
        import torch
        from torch import nn
        from torch.utils.data import DataLoader, random_split
    except ImportError as exc:
        raise RuntimeError("Install backend/requirements-ai.txt first") from exc

    from model.keyword_cnn import build_model
    from training.config import (
        BATCH_SIZE,
        CLASS_NAMES,
        LEARNING_RATE,
        MODEL_DIR,
        MODEL_PATH,
        MODEL_VERSION,
        NUM_CLASSES,
        WEIGHT_DECAY,
    )
    from training.dataset import KeywordDataset

    dataset = KeywordDataset(args.dataset)
    validation_size = max(1, int(len(dataset) * 0.2))
    train_size = len(dataset) - validation_size
    if train_size < 1:
        raise RuntimeError("Dataset needs at least two samples")
    train_set, validation_set = random_split(
        dataset,
        [train_size, validation_size],
        generator=torch.Generator().manual_seed(42),
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model(NUM_CLASSES).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
    )
    criterion = nn.CrossEntropyLoss()
    train_loader = DataLoader(train_set, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    validation_loader = DataLoader(
        validation_set,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
    )
    best_accuracy = -1.0
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    for epoch in range(args.epochs):
        model.train()
        for features, labels in train_loader:
            optimizer.zero_grad()
            loss = criterion(model(features.to(device)), labels.to(device))
            loss.backward()
            optimizer.step()
        model.eval()
        correct = total = 0
        with torch.no_grad():
            for features, labels in validation_loader:
                predictions = model(features.to(device)).argmax(dim=1).cpu()
                correct += int((predictions == labels).sum())
                total += labels.numel()
        accuracy = correct / total if total else 0.0
        print(f"epoch={epoch + 1}/{args.epochs} validation_accuracy={accuracy:.4f}")
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "class_names": CLASS_NAMES,
                    "model_version": MODEL_VERSION,
                    "validation_accuracy": accuracy,
                },
                MODEL_PATH,
            )
    print(f"Best validation accuracy: {best_accuracy:.4f}")
    print(f"Saved model: {MODEL_PATH}")


if __name__ == "__main__":
    main()

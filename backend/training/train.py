import sys
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split

sys.path.append(
    str(Path(__file__).resolve().parents[2] / "backend")
)

from model.keyword_cnn import KeywordCNN

from training.config import (
    RAW_DATASET_DIR,
    MODEL_DIR,
    MODEL_PATH,
    CLASS_NAMES,
    NUM_CLASSES,
    BATCH_SIZE,
    NUM_EPOCHS,
    LEARNING_RATE,
    WEIGHT_DECAY,
    NUM_WORKERS,
    SAMPLE_RATE,
    AUDIO_DURATION,
    N_MELS,
    N_FFT,
    HOP_LENGTH,
    MODEL_VERSION,
)

from training.dataset import KeywordDataset


def evaluate(
    model,
    dataloader,
    criterion,
    device,
):

    model.eval()

    total_loss = 0.0
    correct = 0
    total = 0

    with torch.no_grad():

        for x, y in dataloader:

            x = x.to(device)
            y = y.to(device)

            logits = model(x)

            loss = criterion(logits, y)

            total_loss += loss.item() * x.size(0)

            predictions = logits.argmax(dim=1)

            correct += (
                predictions == y
            ).sum().item()

            total += y.size(0)

    return (
        total_loss / total,
        correct / total,
    )


def main():

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "mps"
        if torch.backends.mps.is_available()
        else "cpu"
    )

    print(f"Using device: {device}")

    # --------------------------------------------------------
    # Dataset
    # --------------------------------------------------------

    dataset = KeywordDataset(
        RAW_DATASET_DIR
    )

    print(
        f"Total samples: {len(dataset)}"
    )

    # --------------------------------------------------------
    # Train / validation split
    # --------------------------------------------------------

    validation_size = int(
        0.2 * len(dataset)
    )

    train_size = (
        len(dataset)
        - validation_size
    )

    train_dataset, validation_dataset = random_split(
        dataset,
        [train_size, validation_size],
        generator=torch.Generator().manual_seed(42),
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=NUM_WORKERS,
    )

    validation_loader = DataLoader(
        validation_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=NUM_WORKERS,
    )

    # --------------------------------------------------------
    # Model
    # --------------------------------------------------------

    model = KeywordCNN(
        num_classes=NUM_CLASSES
    ).to(device)

    criterion = nn.CrossEntropyLoss()

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
    )

    # --------------------------------------------------------
    # Training
    # --------------------------------------------------------

    best_validation_accuracy = 0.0

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for epoch in range(NUM_EPOCHS):

        model.train()

        running_loss = 0.0
        correct = 0
        total = 0

        for x, y in train_loader:

            x = x.to(device)
            y = y.to(device)

            optimizer.zero_grad()

            logits = model(x)

            loss = criterion(
                logits,
                y,
            )

            loss.backward()

            optimizer.step()

            running_loss += (
                loss.item() * x.size(0)
            )

            predictions = logits.argmax(
                dim=1
            )

            correct += (
                predictions == y
            ).sum().item()

            total += y.size(0)

        train_loss = (
            running_loss / total
        )

        train_accuracy = (
            correct / total
        )

        validation_loss, validation_accuracy = evaluate(
            model,
            validation_loader,
            criterion,
            device,
        )

        print(
            f"Epoch {epoch + 1:02d}/{NUM_EPOCHS} | "
            f"Train Loss: {train_loss:.4f} | "
            f"Train Acc: {train_accuracy:.4f} | "
            f"Val Loss: {validation_loss:.4f} | "
            f"Val Acc: {validation_accuracy:.4f}"
        )

        # ----------------------------------------------------
        # Save best model
        # ----------------------------------------------------

        if validation_accuracy > best_validation_accuracy:

            best_validation_accuracy = (
                validation_accuracy
            )

            checkpoint = {
                "model_state_dict":
                    model.state_dict(),

                "class_names":
                    CLASS_NAMES,

                "sample_rate":
                    SAMPLE_RATE,

                "audio_duration":
                    AUDIO_DURATION,

                "n_mels":
                    N_MELS,

                "n_fft":
                    N_FFT,

                "hop_length":
                    HOP_LENGTH,

                "model_version":
                    MODEL_VERSION,

                "validation_accuracy":
                    validation_accuracy,
            }

            torch.save(
                checkpoint,
                MODEL_PATH,
            )

            print(
                f"Saved best model → {MODEL_PATH}"
            )

    print()
    print(
        f"Best validation accuracy: "
        f"{best_validation_accuracy:.4f}"
    )


if __name__ == "__main__":
    main()
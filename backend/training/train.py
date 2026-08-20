from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from training.config import (
        MODEL_PATH,
        NUM_CLASSES,
        CLASS_NAMES,
        PROCESSED_DATASET_DIR,
    )
except ModuleNotFoundError:
    from backend.training.config import (
        MODEL_PATH,
        NUM_CLASSES,
        CLASS_NAMES,
        PROCESSED_DATASET_DIR,
    )


torch = None
nn = None
DataLoader = None
random_split = None
KeywordCNN = None
KeywordDataset = None


# ============================================================
# Training configuration
# ============================================================

BATCH_SIZE = 32
EPOCHS = 30

LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4

RANDOM_SEED = 42

TRAIN_RATIO = 0.80
VALIDATION_RATIO = 0.10
TEST_RATIO = 0.10

DEFAULT_DATASET_DIR = PROCESSED_DATASET_DIR


def _require_training_dependencies() -> None:
    global torch, nn, DataLoader, random_split, KeywordCNN, KeywordDataset
    if torch is not None:
        return
    try:
        import torch as torch_module
        from torch import nn as nn_module
        from torch.utils.data import DataLoader as data_loader
        from torch.utils.data import random_split as split_function

        try:
            from model.keyword_cnn import KeywordCNN as keyword_cnn
            from training.dataset import KeywordDataset as keyword_dataset
        except ModuleNotFoundError:
            from backend.model.keyword_cnn import KeywordCNN as keyword_cnn
            from backend.training.dataset import KeywordDataset as keyword_dataset
    except ImportError as exc:
        raise RuntimeError(
            "Install backend/requirements-ai.txt before running training"
        ) from exc

    torch = torch_module
    nn = nn_module
    DataLoader = data_loader
    random_split = split_function
    KeywordCNN = keyword_cnn
    KeywordDataset = keyword_dataset


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Train the optional keyword CNN model")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_DIR,
        help="processed dataset directory (default: %(default)s)",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=EPOCHS,
        help="number of training epochs (default: %(default)s)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=RANDOM_SEED,
        help="random seed (default: %(default)s)",
    )
    return parser.parse_args(argv)


# ============================================================
# Reproducibility
# ============================================================

def set_seed(seed: int) -> None:
    _require_training_dependencies()
    random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ============================================================
# Device
# ============================================================

def get_device() -> torch.device:
    """
    Priority:
        CUDA
        MPS
        CPU
    """

    _require_training_dependencies()
    if torch.cuda.is_available():
        return torch.device("cuda")

    if (
        hasattr(torch.backends, "mps")
        and torch.backends.mps.is_available()
    ):
        return torch.device("mps")

    return torch.device("cpu")


# ============================================================
# Dataset splitting
# ============================================================

def split_dataset(dataset: KeywordDataset, seed: int = RANDOM_SEED):
    """
    Split:
        80% train
        10% validation
        10% test

    Note:
        This is still sample-level random splitting.
        Augmented versions of one original recording may still
        appear in different splits. Group-based splitting should
        be added before official model evaluation.
    """

    _require_training_dependencies()
    dataset_size = len(dataset)

    if dataset_size < 3:
        raise ValueError(
            "Dataset must contain at least 3 samples."
        )

    train_size = int(
        dataset_size * TRAIN_RATIO
    )

    validation_size = int(
        dataset_size * VALIDATION_RATIO
    )

    test_size = (
        dataset_size
        - train_size
        - validation_size
    )

    if validation_size == 0:
        validation_size = 1
        train_size -= 1

    if test_size == 0:
        test_size = 1
        train_size -= 1

    if train_size <= 0:
        raise ValueError(
            "Dataset is too small after splitting."
        )

    generator = torch.Generator().manual_seed(seed)

    train_set, validation_set, test_set = random_split(
        dataset,
        [
            train_size,
            validation_size,
            test_size,
        ],
        generator=generator,
    )

    return (
        train_set,
        validation_set,
        test_set,
    )


# ============================================================
# DataLoaders
# ============================================================

def create_data_loaders(
    train_set,
    validation_set,
    test_set,
):

    train_loader = DataLoader(
        train_set,
        batch_size=BATCH_SIZE,
        shuffle=True,
    )

    validation_loader = DataLoader(
        validation_set,
        batch_size=BATCH_SIZE,
        shuffle=False,
    )

    test_loader = DataLoader(
        test_set,
        batch_size=BATCH_SIZE,
        shuffle=False,
    )

    return (
        train_loader,
        validation_loader,
        test_loader,
    )


# ============================================================
# Train one epoch
# ============================================================

def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device: torch.device,
):

    model.train()

    total_loss = 0.0
    correct = 0
    total = 0

    for features, labels in loader:

        features = features.to(device)
        labels = labels.to(device)

        optimizer.zero_grad()

        logits = model(features)

        loss = criterion(
            logits,
            labels,
        )

        loss.backward()

        optimizer.step()

        batch_size = labels.size(0)

        total_loss += (
            loss.item()
            * batch_size
        )

        predictions = logits.argmax(
            dim=1
        )

        correct += (
            predictions == labels
        ).sum().item()

        total += batch_size

    if total == 0:
        raise RuntimeError(
            "Training DataLoader contains no samples."
        )

    average_loss = (
        total_loss / total
    )

    accuracy = (
        correct / total
    )

    return (
        average_loss,
        accuracy,
    )


# ============================================================
# Evaluation
# ============================================================

def evaluate(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
):

    model.eval()

    total_loss = 0.0
    correct = 0
    total = 0

    with torch.no_grad():

        for features, labels in loader:

            features = features.to(device)
            labels = labels.to(device)

            logits = model(features)

            loss = criterion(
                logits,
                labels,
            )

            batch_size = labels.size(0)

            total_loss += (
                loss.item()
                * batch_size
            )

            predictions = logits.argmax(
                dim=1
            )

            correct += (
                predictions == labels
            ).sum().item()

            total += batch_size

    if total == 0:
        raise RuntimeError(
            "Evaluation DataLoader contains no samples."
        )

    average_loss = (
        total_loss / total
    )

    accuracy = (
        correct / total
    )

    return (
        average_loss,
        accuracy,
    )


# ============================================================
# Main training pipeline
# ============================================================

def train(argv=None) -> None:
    args = parse_args(argv)
    _require_training_dependencies()
    set_seed(args.seed)

    # --------------------------------------------------------
    # Device
    # --------------------------------------------------------

    device = get_device()

    print("=" * 60)
    print(
        f"Training device: {device}"
    )

    if device.type == "cuda":
        print(
            "NVIDIA CUDA acceleration enabled."
        )

    elif device.type == "mps":
        print(
            "Apple Silicon MPS acceleration enabled."
        )

    else:
        print(
            "Training on CPU."
        )

    print("=" * 60)

    # --------------------------------------------------------
    # Dataset
    # --------------------------------------------------------

    print(
        f"Processed dataset: "
        f"{args.dataset}"
    )

    dataset = KeywordDataset(
        root_dir=args.dataset
    )

    dataset_size = len(dataset)

    if dataset_size == 0:
        raise RuntimeError(
            "Processed dataset contains no samples. "
            "Run preprocessing first."
        )

    print(
        f"Total dataset samples: "
        f"{dataset_size}"
    )

    (
        train_set,
        validation_set,
        test_set,
    ) = split_dataset(dataset, seed=args.seed)

    print()
    print("Dataset split:")

    print(
        f"  Train      : "
        f"{len(train_set)}"
    )

    print(
        f"  Validation : "
        f"{len(validation_set)}"
    )

    print(
        f"  Test       : "
        f"{len(test_set)}"
    )

    # --------------------------------------------------------
    # DataLoaders
    # --------------------------------------------------------

    (
        train_loader,
        validation_loader,
        test_loader,
    ) = create_data_loaders(
        train_set,
        validation_set,
        test_set,
    )

    # --------------------------------------------------------
    # Model
    # --------------------------------------------------------

    model = KeywordCNN(
        num_classes=NUM_CLASSES
    ).to(device)

    print()
    print(
        f"Number of classes: "
        f"{NUM_CLASSES}"
    )

    print(
        f"Classes: "
        f"{CLASS_NAMES}"
    )

    # --------------------------------------------------------
    # Loss
    # --------------------------------------------------------

    criterion = nn.CrossEntropyLoss()

    # --------------------------------------------------------
    # Optimizer
    # --------------------------------------------------------

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
    )

    # --------------------------------------------------------
    # Model directory
    # --------------------------------------------------------

    MODEL_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Training loop
    # --------------------------------------------------------

    best_validation_accuracy = -1.0

    print()
    print("=" * 60)
    print("Starting training")
    print("=" * 60)
    print()

    for epoch in range(
        1,
        args.epochs + 1,
    ):

        # ----------------------------------------------------
        # Train
        # ----------------------------------------------------

        (
            train_loss,
            train_accuracy,
        ) = train_one_epoch(
            model=model,
            loader=train_loader,
            optimizer=optimizer,
            criterion=criterion,
            device=device,
        )

        # ----------------------------------------------------
        # Validation
        # ----------------------------------------------------

        (
            validation_loss,
            validation_accuracy,
        ) = evaluate(
            model=model,
            loader=validation_loader,
            criterion=criterion,
            device=device,
        )

        # ----------------------------------------------------
        # Metrics
        # ----------------------------------------------------

        print(
            f"Epoch "
            f"{epoch:02d}/{args.epochs}"
        )

        print(
            f"  Train      "
            f"loss={train_loss:.4f} "
            f"accuracy={train_accuracy:.4f}"
        )

        print(
            f"  Validation "
            f"loss={validation_loss:.4f} "
            f"accuracy={validation_accuracy:.4f}"
        )

        # ----------------------------------------------------
        # Save best checkpoint
        # ----------------------------------------------------

        if (
            validation_accuracy
            > best_validation_accuracy
        ):

            best_validation_accuracy = (
                validation_accuracy
            )

            checkpoint = {
                "model_state_dict":
                    model.state_dict(),

                "class_names":
                    CLASS_NAMES,

                "validation_accuracy":
                    validation_accuracy,

                "model_version":
                    "keyword-cnn-v1",
            }

            torch.save(
                checkpoint,
                MODEL_PATH,
            )

            print(
                "  -> Saved new best model"
            )

        print()

    # ========================================================
    # Load best checkpoint
    # ========================================================

    print("=" * 60)
    print("Training complete")
    print("=" * 60)

    checkpoint = torch.load(
        MODEL_PATH,
        map_location=device,
    )

    model.load_state_dict(
        checkpoint[
            "model_state_dict"
        ]
    )

    # ========================================================
    # Final test
    # ========================================================

    (
        test_loss,
        test_accuracy,
    ) = evaluate(
        model=model,
        loader=test_loader,
        criterion=criterion,
        device=device,
    )

    print()
    print("=" * 60)
    print("Final results")
    print("=" * 60)

    print(
        f"Best validation accuracy : "
        f"{best_validation_accuracy:.4f}"
    )

    print(
        f"Final test loss          : "
        f"{test_loss:.4f}"
    )

    print(
        f"Final test accuracy      : "
        f"{test_accuracy:.4f}"
    )

    print(
        f"Saved model              : "
        f"{MODEL_PATH}"
    )

    print("=" * 60)


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    train()
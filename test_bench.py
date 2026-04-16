import argparse
from pathlib import Path

from backend.inference import load_model, predict_video_probability

ROOT_DIR = Path(__file__).resolve().parent
MODEL_PATHS = {
    "model_d1": ROOT_DIR / "models" / "model_d1.keras",
    "model_d2": ROOT_DIR / "models" / "model_d2.keras",
    "model_mixed": ROOT_DIR / "models" / "model_mixed.keras",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run all SmartSurveil models on one test video and compare predictions."
    )
    parser.add_argument(
        "--video",
        required=True,
        type=str,
        help="Path to the test video file.",
    )
    return parser.parse_args()


def print_table(rows):
    headers = ["Model", "Shoplifting Probability", "Predicted Label"]
    col_widths = [
        max(len(str(row[i])) for row in [headers] + rows)
        for i in range(len(headers))
    ]

    def fmt(row):
        return " | ".join(str(row[i]).ljust(col_widths[i]) for i in range(len(row)))

    separator = "-+-".join("-" * w for w in col_widths)

    print(fmt(headers))
    print(separator)
    for row in rows:
        print(fmt(row))


def main() -> None:
    args = parse_args()
    video_path = Path(args.video)

    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    models = {}
    for name, path in MODEL_PATHS.items():
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")
        models[name] = load_model(str(path))

    rows = []
    for model_name, model in models.items():
        prob = predict_video_probability(model, str(video_path))
        label = "Shoplifting" if prob >= 0.5 else "Normal"
        rows.append([model_name, f"{prob * 100:.2f}%", label])

    print("\nSmartSurveil Model Comparison")
    print(f"Video: {video_path}")
    print_table(rows)


if __name__ == "__main__":
    main()

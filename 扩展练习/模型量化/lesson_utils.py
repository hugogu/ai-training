"""Small helpers for inspecting quantization and comparing fixed models."""

from collections import Counter
from pathlib import Path
from time import perf_counter

import numpy as np
import onnx


def symmetric_int8(values):
    """Demonstrate one symmetric, per-tensor quantizer with zero point 0."""
    values = np.asarray(values, dtype=np.float32)
    if values.size == 0 or not np.isfinite(values).all():
        raise ValueError("Expected a nonempty array of finite values.")
    maximum = float(np.max(np.abs(values)))
    scale = maximum / 127 if maximum else 1.0
    quantized = np.clip(np.rint(values / scale), -127, 127).astype(np.int8)
    restored = quantized.astype(np.float32) * scale
    return quantized, scale, restored


def model_summary(path):
    model = onnx.load(path)
    onnx.checker.check_model(model)
    weights = [
        tensor for tensor in model.graph.initializer
        if len(tensor.dims) == 2 and tensor.data_type == onnx.TensorProto.INT8
    ]
    return {
        "file_bytes": Path(path).stat().st_size,
        "operators": dict(Counter(node.op_type for node in model.graph.node)),
        "initializer_types": dict(Counter(
            onnx.TensorProto.DataType.Name(tensor.data_type)
            for tensor in model.graph.initializer
        )),
        "int8_weight_matrices": len(weights),
    }


def compare_predictions(y_true, original, quantized):
    """Compare probabilities whose class columns correspond to labels 0..K-1."""
    y_true = np.asarray(y_true)
    original, quantized = np.asarray(original), np.asarray(quantized)
    if (
        original.ndim != 2 or original.shape != quantized.shape
        or original.shape[0] != y_true.size or y_true.ndim != 1
        or original.shape[0] == 0 or original.shape[1] == 0
        or not np.isfinite(original).all() or not np.isfinite(quantized).all()
    ):
        raise ValueError("Expected matching, finite (N, K) arrays and N labels.")
    original_labels = original.argmax(axis=1)
    quantized_labels = quantized.argmax(axis=1)
    original_correct = original_labels == y_true
    quantized_correct = quantized_labels == y_true
    return {
        "original_accuracy": float(original_correct.mean()),
        "quantized_accuracy": float(quantized_correct.mean()),
        "accuracy_change_pp": float(
            (quantized_correct.mean() - original_correct.mean()) * 100
        ),
        "prediction_agreement": float(
            (original_labels == quantized_labels).mean()
        ),
        "changed_predictions": int(
            (original_labels != quantized_labels).sum()
        ),
        "correct_to_wrong": int((original_correct & ~quantized_correct).sum()),
        "wrong_to_correct": int((~original_correct & quantized_correct).sum()),
        "mean_absolute_probability_difference": float(
            np.abs(original - quantized).mean()
        ),
        "maximum_absolute_probability_difference": float(
            np.abs(original - quantized).max()
        ),
    }


def benchmark_sessions(sessions, batch, *, warmup=25, rounds=7, repeats=3000):
    """Report medians of round means, not percentiles of individual requests."""
    if batch.ndim != 2 or batch.shape[0] == 0:
        raise ValueError("Expected a nonempty two-dimensional batch.")
    if rounds < 1 or repeats < 1 or warmup < 0 or not sessions:
        raise ValueError("Invalid benchmark counts or empty sessions.")
    feeds = {
        name: {session.get_inputs()[0].name: batch}
        for name, session in sessions.items()
    }
    for name, session in sessions.items():
        for _ in range(warmup):
            session.run(None, feeds[name])
    measurements = {name: [] for name in sessions}
    names = list(sessions)
    for round_index in range(rounds):
        # Rotate execution order to reduce consistently favoring one model.
        start = round_index % len(names)
        for name in names[start:] + names[:start]:
            begin = perf_counter()
            for _ in range(repeats):
                sessions[name].run(None, feeds[name])
            measurements[name].append(
                (perf_counter() - begin) * 1000 / repeats
            )
    return {
        name: {
            "batch_size": int(batch.shape[0]),
            "median_round_mean_ms": float(np.median(samples)),
            "minimum_round_mean_ms": float(min(samples)),
            "maximum_round_mean_ms": float(max(samples)),
            "samples_per_second": float(
                batch.shape[0] * 1000 / np.median(samples)
            ),
            "round_mean_ms": samples,
        }
        for name, samples in measurements.items()
    }

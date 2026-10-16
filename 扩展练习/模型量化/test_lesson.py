import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

from lesson_utils import compare_predictions, model_summary, symmetric_int8


class QuantizationConceptTests(unittest.TestCase):
    def test_symmetric_mapping_and_rounding_error(self):
        values = np.array([-1.0, -0.5, 0.0, 0.25, 1.0], dtype=np.float32)
        quantized, scale, restored = symmetric_int8(values)
        np.testing.assert_array_equal(quantized, [-127, -64, 0, 32, 127])
        self.assertEqual(quantized.dtype, np.int8)
        self.assertEqual(restored[2], 0)
        self.assertLessEqual(float(np.max(np.abs(values - restored))), scale / 2 + 1e-7)

    def test_zero_tensor_and_invalid_values(self):
        quantized, scale, restored = symmetric_int8(np.zeros(4))
        self.assertEqual(scale, 1.0)
        np.testing.assert_array_equal(quantized, np.zeros(4, dtype=np.int8))
        np.testing.assert_array_equal(restored, np.zeros(4))
        for invalid in [[], [np.nan], [np.inf]]:
            with self.assertRaises(ValueError):
                symmetric_int8(invalid)

    def test_agreement_is_distinct_from_accuracy(self):
        y = np.array([0, 1, 1])
        original = np.array([[0.9, 0.1], [0.2, 0.8], [0.7, 0.3]])
        quantized = np.array([[0.9, 0.1], [0.8, 0.2], [0.1, 0.9]])
        result = compare_predictions(y, original, quantized)
        self.assertAlmostEqual(result["original_accuracy"], 2 / 3)
        self.assertAlmostEqual(result["quantized_accuracy"], 2 / 3)
        self.assertAlmostEqual(result["prediction_agreement"], 1 / 3)
        self.assertEqual(result["correct_to_wrong"], 1)
        self.assertEqual(result["wrong_to_correct"], 1)
        self.assertEqual(result["changed_predictions"], 2)
        self.assertEqual(result["accuracy_change_pp"], 0)

    def test_reject_incompatible_outputs(self):
        for y, a, b in [
            ([0], [[0.5, 0.5]], [[1.0]]),
            ([], np.empty((0, 2)), np.empty((0, 2))),
            ([0], [[np.nan, 1.0]], [[0.5, 0.5]]),
        ]:
            with self.assertRaises(ValueError):
                compare_predictions(y, a, b)

    def test_summary_distinguishes_int8_weights_from_int64_labels(self):
        graph = helper.make_graph(
            [helper.make_node("Identity", ["weights"], ["output"])],
            "inspection", [],
            [helper.make_tensor_value_info("output", TensorProto.INT8, [2, 2])],
            [
                numpy_helper.from_array(np.ones((2, 2), dtype=np.int8), "weights"),
                numpy_helper.from_array(np.array([0, 1], dtype=np.int64), "labels"),
            ],
        )
        model = helper.make_model(graph)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inspection.onnx"
            onnx.save(model, path)
            summary = model_summary(path)
        self.assertEqual(summary["int8_weight_matrices"], 1)
        self.assertEqual(summary["initializer_types"], {"INT8": 1, "INT64": 1})


class NotebookIntegrationTests(unittest.TestCase):
    def test_current_notebook_pipeline_in_temporary_directory(self):
        import matplotlib.pyplot as plt

        notebook = json.loads(
            Path(__file__).with_name("ONNX_INT8量化.ipynb").read_text()
        )
        namespace = {"display": lambda value: None}
        original_directory = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                with contextlib.redirect_stdout(io.StringIO()), patch.object(plt, "show"):
                    for index, cell in enumerate(notebook["cells"]):
                        if cell["cell_type"] == "code":
                            exec(
                                compile("".join(cell["source"]), f"cell-{index}", "exec"),
                                namespace,
                            )
                report = json.loads(Path("outputs/report.json").read_text())
                self.assertEqual(report["experiment"]["test_samples"], 360)
                for name in ["Dynamic INT8", "Static INT8"]:
                    self.assertEqual(report["models"][name]["int8_weight_matrices"], 2)
                    self.assertGreater(report["models"][name]["file_bytes"], 0)
                    self.assertGreater(
                        report["benchmarks"]["1"][name]["median_round_mean_ms"], 0
                    )
                self.assertTrue(Path("outputs/changed_predictions.csv").is_file())
            finally:
                os.chdir(original_directory)
                plt.close("all")


if __name__ == "__main__":
    unittest.main()

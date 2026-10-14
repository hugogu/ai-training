import ast
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from lesson_utils import collate_batch, encode_example, read_examples, style_checks


class FakeTokenizer:
    eos_token_id = 99

    def apply_chat_template(self, messages, **kwargs):
        return [11, 12]

    def encode(self, text, **kwargs):
        return [21] * len(text)


class SFTLabelTests(unittest.TestCase):
    def test_prompt_is_masked_but_answer_and_eos_are_targets(self):
        encoded = encode_example(
            FakeTokenizer(), {"task_id": "short", "prompt": "task", "response": "ab"}, 8
        )
        self.assertEqual(encoded["labels"].tolist(), [-100, -100, 21, 21, 99])

    def test_padding_does_not_mask_real_eos_when_pad_equals_eos(self):
        examples = [
            encode_example(FakeTokenizer(), {
                "task_id": str(i), "prompt": "task", "response": response
            }, 8)
            for i, response in enumerate(["a", "abc"])
        ]
        batch = collate_batch(examples, pad_token_id=99)
        self.assertEqual(batch["input_ids"][0, 3:].tolist(), [99, 99, 99])
        self.assertEqual(batch["labels"][0, 3:].tolist(), [99, -100, -100])
        self.assertEqual(batch["attention_mask"][0, 3:].tolist(), [1, 0, 0])

    def test_overlength_answer_is_rejected_instead_of_silently_truncated(self):
        with self.assertRaises(ValueError):
            encode_example(FakeTokenizer(), {
                "task_id": "long", "prompt": "task", "response": "abcdef"
            }, 4)


class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples = read_examples(Path(__file__).with_name("style_examples.jsonl"))

    def test_task_and_answer_splits_do_not_duplicate(self):
        self.assertEqual(len(self.examples), 32)
        self.assertEqual(len({row["task_id"] for row in self.examples}), 32)
        self.assertEqual(len({row["response"] for row in self.examples}), 32)
        self.assertEqual(
            {split: sum(row["split"] == split for row in self.examples)
             for split in ["train", "validation", "test"]},
            {"train": 24, "validation": 4, "test": 4},
        )

    def test_authored_answers_match_their_function_names_and_style(self):
        for row in self.examples:
            with self.subTest(task=row["task_id"]):
                ast.parse(row["response"])
                self.assertTrue(all(style_checks(row["response"], row["function_name"]).values()))
                self.assertTrue(row["source_refs"])
                self.assertNotIn("只输出代码", row["prompt"])

    def test_representative_authored_answers_have_correct_behavior(self):
        # 这里只执行经过编写与审查的样例答案，不执行模型生成内容。
        namespace = {"pd": pd, "np": np}
        for row in self.examples:
            exec(compile(row["response"], row["task_id"], "exec"), namespace)
        sensors = pd.DataFrame({"SensorType": ["Humidity", "Pressure", "Temperature"]})
        result = namespace["filter_sensor_types"](sensors, ["Humidity", "Temperature"])
        self.assertEqual(result.index.tolist(), [0, 2])
        self.assertIsNot(result, sensors)
        frame = pd.DataFrame({"a": [1, None], "b": [None, None]})
        self.assertEqual(namespace["count_missing_by_column"](frame).tolist(), [1, 2])
        self.assertEqual(namespace["get_top_indices"](np.array([0.1, 0.7, 0.2]), 2).tolist(), [1, 2])
        groups = pd.DataFrame({"g": ["a", "a", "b"], "v": [1, 1, 2]})
        self.assertEqual(namespace["group_unique_count"](groups, "g", "v").tolist(), [1, 1])


class StyleTests(unittest.TestCase):
    def test_empty_response_is_not_counted_as_code(self):
        self.assertFalse(style_checks("", "f")["raw_python"])
        self.assertFalse(style_checks("# no implementation", "f")["code_parsed"])

    def test_markdown_format_and_code_structure_are_separate(self):
        checks = style_checks("```python\ndef f(x):\n    return x\n```", "f")
        self.assertFalse(checks["raw_python"])
        self.assertTrue(checks["code_parsed"])
        self.assertTrue(checks["one_requested_function"])

    def test_loop_is_not_mistaken_for_vectorized_style(self):
        checks = style_checks("def f(items):\n    for item in items:\n        print(item)", "f")
        self.assertFalse(checks["no_explicit_loops"])


if __name__ == "__main__":
    unittest.main()

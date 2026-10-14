"""这个教学示例的样例读取、SFT 标签和静态风格检查。"""

import ast
import json
import re

import torch
from torch.nn.utils.rnn import pad_sequence


def read_examples(path):
    with open(path, encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def encode_example(tokenizer, example, max_length):
    prompt_ids = tokenizer.apply_chat_template(
        [{"role": "user", "content": example["prompt"]}],
        tokenize=True,
        add_generation_prompt=True,
    )
    response_ids = tokenizer.encode(example["response"], add_special_tokens=False)
    response_ids.append(tokenizer.eos_token_id)
    input_ids = prompt_ids + response_ids
    if len(input_ids) > max_length:
        raise ValueError(
            f"{example['task_id']} 有 {len(input_ids)} tokens，超过 {max_length}；"
            "请缩短样例或提高长度上限，避免把答案截断。"
        )
    return {
        "input_ids": torch.tensor(input_ids, dtype=torch.long),
        "labels": torch.tensor(
            [-100] * len(prompt_ids) + response_ids, dtype=torch.long
        ),
    }


def collate_batch(examples, pad_token_id):
    input_ids = [example["input_ids"] for example in examples]
    return {
        "input_ids": pad_sequence(
            input_ids, batch_first=True, padding_value=pad_token_id
        ),
        "attention_mask": pad_sequence(
            [torch.ones_like(ids) for ids in input_ids],
            batch_first=True,
            padding_value=0,
        ),
        "labels": pad_sequence(
            [example["labels"] for example in examples],
            batch_first=True,
            padding_value=-100,
        ),
    }


def _parse(source):
    try:
        return ast.parse(source)
    except (SyntaxError, ValueError):
        return None


def style_checks(response, function_name):
    """只检查可观察的形式；不执行模型代码，也不判断功能是否正确。"""
    raw_tree = _parse(response.strip())
    fenced = re.search(r"```(?:python)?\s*\n(.*?)```", response, re.S | re.I)
    code = fenced.group(1).strip() if fenced else response.strip()
    tree = _parse(code)
    functions = (
        [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        if tree is not None else []
    )
    one_function = (
        len(functions) == 1 and functions[0].name == function_name
        and len(tree.body) == 1
    )
    has_code = tree is not None and bool(tree.body)
    loop_types = (ast.For, ast.AsyncFor, ast.While, ast.ListComp, ast.SetComp,
                  ast.DictComp, ast.GeneratorExp)
    return {
        "raw_python": raw_tree is not None and bool(raw_tree.body),
        "code_parsed": has_code,
        "one_requested_function": one_function,
        "no_explicit_loops": (
            has_code and not any(
                isinstance(node, loop_types) for node in ast.walk(tree)
            )
        ),
        "no_docstring": (
            bool(functions) and all(ast.get_docstring(fn) is None for fn in functions)
        ),
        "compact_body": one_function and len(functions[0].body) <= 3,
    }

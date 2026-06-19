from transformers import AutoTokenizer, AutoModelForCausalLM

model_id = "openai/gpt-oss-120b"

tokenizer = AutoTokenizer.from_pretrained(model_id)

messages = [
    {
        "role": "system",
        "content": "You are a helpful assistant."
    },
    {
        "role": "user",
        "content": "Explain binary search in simple terms."
    }
]

prompt = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True,
    reasoning_effort="low",
)

inputs = tokenizer(
    prompt,
    # return_tensors="pt",
    add_special_tokens=False
)

print(inputs)
print("Prompt tokens:", inputs['input_ids'])
print("Prompt text:", tokenizer.decode(inputs['input_ids']))
print("EOS token:", tokenizer.eos_token)



from transformers import AutoTokenizer, GenerationConfig


def normalize_eos_ids(eos_token_id):
    if eos_token_id is None:
        return []
    if isinstance(eos_token_id, int):
        return [eos_token_id]
    return list(eos_token_id)


def decode_token_id(tokenizer, token_id):
    return tokenizer.decode(
        [token_id],
        skip_special_tokens=False,
    )


def get_all_eos_text(tokenizer, generation_config):
    eos_ids = normalize_eos_ids(generation_config.eos_token_id)

    return [
        decode_token_id(tokenizer, eos_id)
        for eos_id in eos_ids
    ]


def build_chat_template_text(
    tokenizer,
    messages,
    generation_config=None,
    reasoning_effort="low",
    add_generation_prompt=True,
):
    """
    Input: OpenAI messages format
    Output: prompt text only

    messages example:
    [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."}
    ]
    """

    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=add_generation_prompt,
        reasoning_effort=reasoning_effort,
    )

    eos_texts = []
    if generation_config is not None:
        eos_texts = get_all_eos_text(tokenizer, generation_config)

    return {
        "prompt": prompt,
        "eos": eos_texts,
    }


# -------------------------
# Example
# -------------------------

model_id = "openai/gpt-oss-120b"

tokenizer = AutoTokenizer.from_pretrained(model_id)
generation_config = GenerationConfig.from_pretrained(model_id)

messages = [
    {
        "role": "system",
        "content": "You are a helpful assistant.",
    },
    {
        "role": "user",
        "content": "Explain binary search in simple terms.",
    },
]

result = build_chat_template_text(
    tokenizer=tokenizer,
    messages=messages,
    generation_config=generation_config,
    reasoning_effort="low",
)

print("PROMPT:")
print(result["prompt"])

print("\nALL EOS:")
print(result["eos"])

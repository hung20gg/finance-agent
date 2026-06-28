from llm import get_llm_wrapper



llm = get_llm_wrapper("deepinfra:Qwen/Qwen3-32B")


messages = [
    {"role": "user", "content": "Who are you?"}
]

print(llm(messages, logprobs = 1))

# text = llm.apply_chat_template(messages, tokenize=False)
# print(text)
# text="<|im_start|>user\nWho are you?<|im_end|>\n<|im_start|>assistant\n<think>\n\n"

# print(llm.completion(text, logprobs=1))


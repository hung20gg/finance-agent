from llm import get_llm_wrapper



llm = get_llm_wrapper("deepinfra:openai/gpt-oss-120b")


messages = [
    {"role": "user", "content": "Who are you?"}
]

text = llm.apply_chat_template(messages, tokenize=False)
print(text)

print(llm.completion(text))
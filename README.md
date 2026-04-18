Việc phải làm:

- Với câu hỏi giá cổ phiếu, buộc phải thêm chữ giá cổ phiếu
- Bỏ những câu hỏi biến động
- Review 1 loạt câu hỏi yoy, qoq


check lại những câu tăng giảm % (có thể nó chỉ là phép trừ)
độ lệch chuẩn ?

1/4

Giá cổ phiếu không dùng
tỷ suất sinh lời 

Test via

```bash
python -m agent.test_agent
```

7/4

null question


qwen-sql:v1

```bash
vllm serve Qwen/Qwen3-4B-Thinking-2507 \
  --max-model-len 16000 \
  --enable-lora \
  --lora-modules qwen-sql-v1=models/qwen3-4b-simple/lora/sft \
  --max_lora_rank 64 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --gpu-memory-utilization 0.8
```

```bash
vllm serve Qwen/Qwen3-4B-Thinking-2507 \
  --max-model-len 16000 \
  --enable-lora \
  --lora-modules qwen-sql-v1-4e=models/qwen3-4b-v1-4e/lora/sft \
  --max_lora_rank 64 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --gpu-memory-utilization 0.8
```


```bash
vllm serve Qwen/Qwen3-4B-Thinking-2507 \
  --max-model-len 16000 \
  --enable-lora \
  --lora-modules qwen-sql-v1-acc=models/qwen3-4b-acc/lora/sft \
  --max_lora_rank 64 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --gpu-memory-utilization 0.8
```



-acc (train with partial error data, only require acc = 1, not drop anything)
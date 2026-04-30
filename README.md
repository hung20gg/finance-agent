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


```bash
vllm serve Qwen/Qwen3-4B-Thinking-2507 \
  --max-model-len 16000 \
  --max_lora_rank 64 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --gpu-memory-utilization 0.8
```

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
  --lora-modules qwen-sql-v1=models/qwen3-4b-simple/lora/sft \
  --max_lora_rank 64 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --gpu-memory-utilization 0.8
```

```bash
vllm serve Qwen/Qwen3-4B-Thinking-2507 \
  --max-model-len 20000 \
  --enable-lora \
  --lora-modules qwen-sql-v2=models/qwen3-4b-v2/lora/sft \
  --max_lora_rank 64 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --gpu-memory-utilization 0.85
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


```bash
vllm serve Qwen/Qwen3-4B-Thinking-2507 \
  --max-model-len 16000 \
  --enable-lora \
  --lora-modules qwen-sql-chart=models/qwen3-4b-chart/lora/sft \
  --max_lora_rank 64 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --gpu-memory-utilization 0.8
```

finance-agent/models/qwen3-1.7b-grpo/global_step_240/actor/lora_adapter


```bash
vllm serve hung20gg/qwen3-1.7b-sql \
  --max-model-len 20000 \
  --enable-lora \
  --lora-modules qwen-sql-1.7b-grpo=models/qwen3-1.7b-grpo/global_step_240/actor/lora_adapter \
  --max_lora_rank 64 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --gpu-memory-utilization 0.85
```


```bash
vllm serve models/qwen3-4b-full/full/sft \
  --max-model-len 16000 \
  --served-model-name qwen-sql-v1-full \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --gpu-memory-utilization 0.8
```



-acc (train with partial error data, only require acc = 1, not drop anything)


```bash
bash scripts/evaluate.sh --split val --model vllm:qwen-sql-v1-full --iteration 3
```

```bash
bash scripts/evaluate.sh --split val --iteration 3
```


```bash
vllm serve Qwen/Qwen3-1.7B \
  --max-model-len 20000 \
  --enable-lora \
  --lora-modules qwen-sql-1.7b-v2=models/qwen3-1.7b-test/lora/sft \
  --max_lora_rank 64 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --gpu-memory-utilization 0.85
```

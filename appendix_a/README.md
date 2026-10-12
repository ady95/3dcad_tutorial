# 부록 A. 로컬 LLM과 GPT-6 Astra 비교

예제 코드는 그대로 두고 환경변수로 모델만 바꿔 같은 과제를 비교합니다. 이 부록만 GPU가 필요합니다.

```bash
# 로컬 LLM (Ollama, OpenAI 호환 API)
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_API_KEY=ollama
export OPENAI_MODEL=qwen3.8:27b

python appendix_a/benchmark.py --tag qwen --runs 3          # 01-3·02-4·03-2·05-1 예제를 3회씩
python appendix_a/benchmark.py --report astra qwen          # 비교표
EVAL_OUT=output/appendix_a/qwen_eval python ch06/eval_agent.py   # 06-3 에이전트 평가
```

## 기준 버전 (실측)

Ollama 0.33.2 · qwen3.8:27b (Q4_K_M) · RTX 3090 24 GB × 2 (Linux) · 예제 실행 Windows 11 · FreeCAD 1.1.4 · Python 3.12 · gpt-6-astra

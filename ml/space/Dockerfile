# Hugging Face Space：把微調好的 GGUF 跑成 OpenAI 相容的 /v1/chat/completions
# 怎麼開 Space 見同一個資料夾的 README.md。
#
# --jinja   用模型自帶的對話模板（Qwen 的工具呼叫格式）；沒有它，工具呼叫會失效
# -c 4096   上下文長度：system（規則＋分類清單＋工具定義）加上一段話，大約 1500 tokens
# 7860      Hugging Face Space 固定對外的埠
FROM ghcr.io/ggml-org/llama.cpp:server

# 在 Space 的 Settings → Variables and secrets 改：
#   MODEL_REPO  （Variable）你的帳號/qwen2.5-1.5b-fambudget-GGUF:Q4_K_M
#   API_KEY     （Secret，可不設）設了之後後端的 MODEL_API_KEY 要填同一個值
ENV MODEL_REPO=your-name/qwen2.5-1.5b-fambudget-GGUF:Q4_K_M \
    LLAMA_CACHE=/tmp/llama-cache

ENTRYPOINT ["/bin/sh", "-c", "exec /app/llama-server -hf \"$MODEL_REPO\" --jinja -c 4096 --host 0.0.0.0 --port 7860 --alias qwen2.5-1.5b-fambudget ${API_KEY:+--api-key \"$API_KEY\"}"]

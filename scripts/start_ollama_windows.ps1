# 1) Ollama 설치 후 실행(이미 설치되어 있으면 건너뜀)
# https://ollama.com/download

# 2) 서버 실행
Start-Process -NoNewWindow -FilePath "ollama" -ArgumentList "serve"

# 3) 모델 받기 (4bit 양자화 권장: q4_K_M)
ollama pull llama3.1:8b-instruct-q4_K_M
# 대안(한글 강함): qwen2.5:14b-instruct-q4_K_M  (VRAM 8GB에선 빡셀 수 있음)

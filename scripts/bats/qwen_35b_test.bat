@echo off
:: ============================================================
:: Perfil Generado Automáticamente por Vision OS: Qwen_35B_Test
:: ============================================================
set BUILD_DIR=C:\Users\lolpl\Desktop\llama.cpp\llama-b10082-bin-win-cuda-13.3-x64\
"%BUILD_DIR%llama-server.exe" ^
  -m "%BUILD_DIR%gguf\modelo.gguf" ^
  -ngl 999 -fa on -ctk q4_0 -ctv q4_0 -c 131072 ^
  --spec-type draft-mtp --spec-draft-n-max 3 ^
  --port 8080 --host 127.0.0.1

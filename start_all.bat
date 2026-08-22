@echo off
title Vision OS — All-in-One Launcher
echo ============================================================
:: Vision OS — Iniciando Entorno Completo (Backend + Frontend)
:: ============================================================
echo.

:: 1. Iniciar Broker de Eventos
echo [1/3] Iniciando Broker de Eventos TCP (Puerto 5000)...
start "Vision OS - Event Broker" cmd /k "python core/broker_eventos.py"

:: Esperar 2 segundos a que el broker levante el puerto 5000
timeout /t 2 /nobreak >nul

:: 2. Iniciar LLM Router / Lóbulo Frontal
echo [2/3] Iniciando LLM Router / Lóbulo Frontal...
start "Vision OS - LLM Router" cmd /k "python cognitivo/llm_router.py"

:: 3. Iniciar Frontend Nativo Visión Studio (Tauri + React)
echo [3/3] Iniciando Visión Studio (Tauri Dev)...
cd vision_studio
start "Vision OS - Studio IDE" cmd /k "npm run tauri dev"

echo.
echo ============================================================
echo ¡Entorno iniciado con éxito! Las consolas están ejecutándose.
echo ============================================================

@echo off
title Visión OS — All-in-One Launcher
echo ============================================================
echo 🚀 Visión OS — Iniciando Entorno Completo (Hexagonal)
echo ============================================================
echo.

:: 1. Iniciar Orquestador Cerebral Unificado (14 daemons en un solo runtime)
echo [1/2] Iniciando Orquestador Cerebral Unificado...
start "Visión OS - Brainstem Orchestrator" cmd /k ".venv\Scripts\python.exe core\main.py"

:: Esperar 2 segundos
timeout /t 2 /nobreak >nul

:: 2. Iniciar Frontend Nativo Visión Studio (Tauri + React)
echo [2/2] Iniciando Visión Studio (Tauri Dev)...
cd vision_studio
start "Visión OS - Studio IDE" cmd /k "npm run tauri dev"

echo.
echo ============================================================
echo ¡Entorno iniciado con éxito! Orquestador y Studio activos.
echo ============================================================

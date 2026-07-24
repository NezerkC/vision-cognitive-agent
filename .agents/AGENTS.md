# Reglas Específicas del Proyecto — Visión OS

- **Inicio de Sesión e Alineación del Alcance (Scope Kickoff):** Al iniciar una sesión de trabajo o nueva tarea, la IA debe consultar o confirmar con el usuario el objetivo del día para determinar la clasificación exacta de la entrega (`feat`, `fix`, `chore`, `docs`, `refactor`, `release`). Esto define el nombre de la rama (`feat/*`, `fix/*`, `release/*`) y el prefijo del Conventional Commit.

- **Directorio de Documentación Personal:** Todos los planes de implementación (desde la versión inicial hasta las versiones revisadas con feedback del usuario), así como cualquier archivo de información del proyecto que el usuario pida o provea, deben guardarse de forma obligatoria en la carpeta `material_complementario`. Este directorio es de uso exclusivo y personal del usuario para centralizar toda su planificación y contexto.

- **Seguridad e Higiene de Credenciales:** NUNCA escribir o hardcodear API keys ni tokens sensibles en archivos de código fuente, YAML, JSON, Markdown o JS. Utilizar siempre la interpolación de variables de entorno (`.env` / `${OPENROUTER_API_KEY}`).

- **Git Workflow & Conventional Commits:** 
  - Todo cambio debe realizarse en feature/fix branches (`feat/*`, `fix/*`, `security/*`, `release/*`) partiendo de `develop`. Nunca commitear directo a `main` o `develop`.
  - Usar estrictamente Conventional Commits (`feat:`, `fix:`, `security:`, `test:`, `ci:`, `docs:`, `chore:`, `style:`).
  - NUNCA agregar `Co-Authored-By` ni firma de IA en los mensajes de commit.

- **Calidad de Código y Testing Obligatorio:** Antes de declarar finalizado un cambio, ejecutar la suite de Pytest (`pytest tests/`) y el linter Ruff (`ruff check core/ cognitivo/ sentidos/ memoria/ tests/`).

- **Diagnóstico y Causa Raíz (Sin Parches Superficiales):** Inspeccionar siempre logs y stack traces reales antes de emitir diagnósticos. Prohibido enmascarar errores silenciando excepciones o borrando/comentando assertions fallidas para pasar la CI.

- **Contrato de Eventos (EventBroker):** Todo mensaje enviado por el bus TCP debe seguir la estructura de sobres tipados con `Pydantic v2` definidos en `core/schemas.py`.

- **Pipelines de CI/CD (GitHub Actions):** Garantizar que todo cambio sea compatible con los workflows de `.github/workflows/ci.yml` (Security scan, Ruff lint, Pytest matriz 3.10-3.12).

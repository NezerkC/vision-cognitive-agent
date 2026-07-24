# Reglas Específicas del Proyecto — Visión OS

- **Directorio de Documentación Personal:** Todos los planes de implementación (desde la versión inicial hasta las versiones revisadas con feedback del usuario), así como cualquier archivo de información del proyecto que el usuario pida o provea, deben guardarse de forma obligatoria en la carpeta `material_complementario`. Este directorio es de uso exclusivo y personal del usuario para centralizar toda su planificación y contexto.

- **Seguridad e Higiene de Credenciales:** NUNCA escribir o hardcodear API keys ni tokens sensibles en archivos de código fuente, YAML, JSON, Markdown o JS. Utilizar siempre la interpolación de variables de entorno (`.env` / `${OPENROUTER_API_KEY}`).

- **Git Workflow & Conventional Commits:** 
  - Todo cambio debe realizarse en feature/fix branches (`feat/*`, `fix/*`, `security/*`) partiendo de `develop`. Nunca commitear directo a `main` o `develop`.
  - Usar estrictamente Conventional Commits (`feat:`, `fix:`, `security:`, `test:`, `ci:`, `docs:`, `chore:`, `style:`).
  - NUNCA agregar `Co-Authored-By` ni firma de IA en los mensajes de commit.

- **Calidad de Código y Testing Obligatorio:** Antes de declarar finalizado un cambio, ejecutar la suite de Pytest (`pytest tests/`) y el linter Ruff (`ruff check core/ cognitivo/ sentidos/ memoria/ tests/`).

- **Contrato de Eventos (EventBroker):** Todo mensaje enviado por el bus TCP debe seguir la estructura de sobres tipados con `Pydantic v2` definidos en `core/schemas.py`.

- **Pipelines de CI/CD (GitHub Actions):** Garantizar que todo cambio sea compatible con los workflows de `.github/workflows/ci.yml` (Security scan, Ruff lint, Pytest matriz 3.10-3.12).

# Plan de Implementación: Herramientas del Sistema y Niveles de Permisos para el Modo Build

Habilitar herramientas del sistema (lectura de archivos, escritura/edición de archivos y ejecución de comandos PowerShell) en el chat de **Visión Studio**, resguardadas por un **Sistema de Niveles de Permisos** configurable.

---

## User Review Required

> [!IMPORTANT]
> **Niveles de Permisos Propuestos**:
> 1. **Solo Lectura (`read_only`)**: El LLM solo puede realizar búsquedas web y leer contenido de archivos del workspace. Cualquier intento de escribir o ejecutar comandos es rechazado automáticamente.
> 2. **Pedir Confirmación (`ask`) [RECOMENDADO]**: Antes de escribir/editar un archivo o ejecutar un comando en PowerShell, el frontend pausa la ejecución y muestra un modal interactivo al usuario con los detalles de la acción (`Comando`, `Archivo`, `Ruta`). El usuario decide entre **Permitir** o **Rechazar**.
> 3. **Modo Autónomo (`auto`)**: El LLM tiene libertad total para leer, escribir y ejecutar comandos directamente sin pausas.

> [!WARNING]
> La ejecución de comandos PowerShell en modo `auto` otorga permisos de nivel de usuario sobre la máquina. Por defecto, el nivel inicial será **Pedir Confirmación (`ask`)**.

---

## Open Questions

Ninguna por el momento.

---

## Proposed Changes

### Backend Tauri (`vision_studio/src-tauri`)

#### [MODIFY] [lib.rs](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src-tauri/src/lib.rs)
- Crear e invocar nuevos comandos `tauri`:
  - `read_file_content(path: String) -> Result<String, String>`: Lee el contenido textual de un archivo.
  - `write_file_content(path: String, content: String) -> Result<String, String>`: Escribe o sobreescribe un archivo en disco.
  - `execute_powershell_command(command: String, cwd: Option<String>) -> Result<ExecutionResult, String>`: Ejecuta comandos en PowerShell dentro del directorio de trabajo especificado y retorna `stdout`, `stderr` y `exit_code`.
- Registrar los 3 comandos en el `generate_handler![]` de Tauri.

---

### Estado Global (`vision_studio/src/stores`)

#### [MODIFY] [useSettingsStore.ts](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/stores/useSettingsStore.ts)
- Agregar el campo `permissionLevel: 'read_only' | 'ask' | 'auto'` (por defecto `'ask'`).
- Agregar la función `setPermissionLevel(level: 'read_only' | 'ask' | 'auto')`.

---

### Componentes UI (`vision_studio/src/components`)

#### [NEW] [ToolApprovalModal.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/UI/ToolApprovalModal.tsx)
- Modal interactivo de alta calidad visual para pedir autorización previa al usuario cuando `permissionLevel === 'ask'`.
- Muestra el tipo de herramienta (`write_file` o `execute_powershell`), los argumentos exactos (código/comando/ruta) y los botones **Aprobar** / **Rechazar**.

#### [MODIFY] [SettingsModal.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Settings/SettingsModal.tsx)
- Agregar una sección de **Seguridad y Permisos del Agente** en los ajustes.
- Selector entre `Solo Lectura`, `Pedir Confirmación (Recomendado)` y `Autónomo Total`.

#### [MODIFY] [SidebarChat.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Sidebar/SidebarChat.tsx)
- Ampliar el arreglo `TOOLS` exponiendo:
  - `read_file`: Para inspeccionar archivos del proyecto.
  - `write_file`: Para crear o actualizar archivos de código.
  - `execute_powershell`: Para ejecutar comandos de terminal (npm, git, ruff, pytest, etc.).
- Actualizar el bucle de ejecución de tools en `handleSend`:
  - Verificar `settings.permissionLevel` antes de ejecutar `write_file` o `execute_powershell`.
  - Si es `read_only`, abortar la llamada con un mensaje descriptivo.
  - Si es `ask`, pausar el ciclo, abrir `ToolApprovalModal` y esperar la resolución de la promesa. Si el usuario aprueba, ejecutar la orden en Rust; si rechaza, devolver "Operación cancelada por el usuario".
- Actualizar el system prompt de **Build** para instruir al modelo a usar las herramientas disponibles de forma efectiva.

---

## Verification Plan

### Automated Tests
- Ejecutar la compilación y verificación de tipos con `npm run build` en `vision_studio`.

### Manual Verification
1. **Prueba de Lectura**: Enviar mensaje en modo Build pidiendo leer un archivo del proyecto. Verificar que use `read_file`.
2. **Prueba de Escritura con Confirmación (`ask`)**: Solicitar crear/editar un archivo. Verificar que aparezca el modal de aprobación con los botones Aprobar y Rechazar.
3. **Prueba de PowerShell**: Pedir listar archivos con `Get-ChildItem` o un comando equivalente en PowerShell y verificar la captura y renderizado del resultado en el chat.
4. **Prueba de Nivel Solo Lectura**: Cambiar el ajuste a `read_only` y verificar que el chat informe que las acciones destructivas o de ejecución están bloqueadas por permisos.

# Walkthrough: Gestor de Proyectos Estilo VS Code y Control de Barra Lateral

Se ha implementado con éxito el **Gestor de Proyectos completo estilo VS Code** y el **Control de Colapso Limpio de la Barra Lateral** en Visión Studio.

---

## 🛠️ Cambios Realizados

### Backend (`sentidos / sistema_periferico.py`)
- **`GET /api/workspace/tree`**: Devuelve la estructura de archivos y carpetas en tiempo real del workspace seleccionado, filtrando archivos ocultos y dependencias pesadas (`.git`, `node_modules`, `__pycache__`).
- **`POST /api/workspace/clone_git`**: Ejecuta la clonación asíncrona de repositorios mediante `git clone <url>`, alojándolos en `datos_crudos/` y devolviendo el árbol de archivos generado.

### Frontend (`vision_studio`)
- **`useSettingsStore.ts`**:
  - Se agregó el estado `isSidebarVisible: boolean` y las acciones `toggleSidebar()`, `setSidebarVisible()`.
  - Persistencia de `currentWorkspacePath` y del historial de `recentProjects`.
- **`ActivityBar.tsx`**:
  - Soporte para alternar apertura/cierre de la barra lateral al hacer clic en el ícono de la pestaña activa.
  - Listener global de atajo de teclado **`Ctrl + B`** (o `Cmd + B`) para colapsar y abrir el panel lateral en cualquier momento.
- **`SidebarComponents.tsx`**:
  - Botón de cierre (`X`) en la barra de título superior de la barra lateral.
  - Renderizado condicional que colapsa el sidebar cuando `isSidebarVisible` es falso.
- **`ProjectManager.tsx`** *(Nuevo)*:
  - Botón **"Abrir Carpeta"**: Permite abrir cualquier carpeta del equipo.
  - Botón **"Clonar Repositorio Git"**: Formulario interactivo para ingresar links de GitHub/GitLab con indicador de carga y clonación automática.
  - Listado de **"Proyectos Recientes"** para cambiar de workspace con 1 clic.
- **`FileTree.tsx`**:
  - Árbol de archivos recursivo interactivo conectado al backend, con íconos específicos por tipo de archivo (`.py`, `.ts`, `.json`, `.md`).
- **`MenuBar.tsx`**:
  - Opciones del menú superior **Archivo > Abrir Carpeta** y **Ver > Alternar Barra Lateral (Ctrl+B)** vinculadas a las acciones reales.

---

## 🧪 Resultados de Verificación

### Pruebas Automatizadas
- **Pytest**: `tests/unit/test_workspace.py` y `tests/unit/test_cuadernos.py` ejecutados con éxito.
  ```
  ============================= 1 passed in 12.66s ==============================
  ============================= 4 passed in 31.08s ==============================
  ```
- **Ruff Linter**: `ruff check core/ cognitivo/ sentidos/ memoria/ tests/`
  ```
  All checks passed!
  ```

---

## 📸 Demostración de Uso

1. **Colapsar / Abrir Barra Lateral**:
   - Presioná **`Ctrl + B`** o hacé clic en la pestaña activa de la ActivityBar o en la `X` del encabezado. La barra se colapsa limpiamente sin tapar el editor.
2. **Abrir una Carpeta**:
   - En el explorador, hacé clic en **"Abrir Carpeta"**, ingresá la ruta y presioná Enter. El árbol de archivos se actualizará automáticamente.
3. **Clonar Repositorio Git**:
   - Hacé clic en **"Clonar Repositorio Git"**, pegá una URL pública (ej. `https://github.com/psf/requests.git`) y presioná **Clonar**. El repositorio se clonará y abrirá en el explorador.

# Plan de Implementación: Gestor de Proyectos Estilo VS Code y Control de Paneles Laterales

Transformar la barra lateral y el explorador de **Visión Studio** en un **Gestor de Proyectos completo estilo VS Code**, agregando la capacidad de abrir carpetas reales, clonar repositorios de Git y abrir/cerrar (colapsar) la barra lateral limpiamente para que nunca tape el código ni el área de trabajo.

---

## 🧠 Análisis y Arquitectura del Diseño

### 1. Gestor de Proyectos Estilo VS Code (`Explorer / ProjectManager`)
En lugar de un árbol de archivos estático maquetiado:
- **Abrir Carpeta Local**: Permite seleccionar o ingresar la ruta de una carpeta en la computadora y carga su árbol de archivos real mediante la API del backend.
- **Clonar Repositorio Git**: Opción para ingresar la URL de un repositorio de GitHub/GitLab (`https://github.com/...`), ejecutar `git clone` en la sandbox y abrir la carpeta clonada inmediatamente.
- **Proyectos Recientes**: Listado persistente de las últimas carpetas trabajadas para alternar entre proyectos con 1 clic.
- **Navegador de Archivos Real**: Explorador de archivos recursivo con íconos de tipo de archivo (Python, JS, JSON, Markdown, etc.) y apertura de archivos en el editor principal.

### 2. Control Limpio de Apertura y Cierre de la Barra Lateral
Actualmente, cambiar de pestaña en la ActivityBar mantiene la barra lateral fija y la vista de Cuadernos se superpone sobre la pantalla.
- **Toggle On/Off (Activar / Colapsar)**:
  - Si se vuelve a hacer clic en la pestaña seleccionada en la `ActivityBar`, la barra lateral se oculta por completo (`isSidebarVisible = false`).
  - Agregar un botón de cierre (`X` o `ChevronLeft`) en el encabezado de la barra lateral.
  - Soporte para atajo de teclado **`Ctrl + B`** (estándar de VS Code) para abrir/cerrar la barra lateral al instante.
- **Disposición Limpia de Cuadernos**:
  - Ajustar `NotebooksView` para que utilice el espacio de trabajo central o se adapte limpiamente al panel lateral sin provocar desbordamientos (`overflow`) ni tapar el editor.

---

## 🛠️ Cambios Propuestos

### Componente Frontend (`vision_studio`)

#### [MODIFY] [useSettingsStore.ts](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/stores/useSettingsStore.ts)
- Agregar estado global `isSidebarVisible: boolean` y acción `toggleSidebar()`.
- Persistir historial de `recentProjects: string[]` y `currentWorkspacePath: string`.

#### [MODIFY] [ActivityBar.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Layout/ActivityBar.tsx)
- Actualizar el evento `onClick` de los botones: si la pestaña ya está activa, alternar `isSidebarVisible`.

#### [NEW] [ProjectManager.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Sidebar/ProjectManager.tsx)
- Vista de bienvenida del Explorador cuando no hay carpeta abierta (o menú superior):
  - Botón **"Abrir Carpeta"** (Folder dialog / Path input).
  - Botón **"Clonar Repositorio Git"** (Modal para pegar URL de Git y seleccionar carpeta).
  - Sección **"Proyectos Recientes"**.

#### [MODIFY] [FileTree.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Sidebar/FileTree.tsx)
- Integrar lectura dinámica del árbol de archivos conectada a la API `/api/workspace/tree`.

#### [MODIFY] [SidebarComponents.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Sidebar/SidebarComponents.tsx)
- Agregar botón de cerrar (`X`) en la cabecera.
- Integrar `ProjectManager` y ajustar el layout de `NotebooksView`.

---

### Componente Backend (`sentidos / sistema_periferico.py`)

#### [MODIFY] [sistema_periferico.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/sentidos/sistema_periferico.py)
- Agregar endpoint `GET /api/workspace/tree?path=...` para obtener la estructura de archivos/carpetas del workspace activo.
- Agregar endpoint `POST /api/workspace/clone_git` para ejecutar la clonación de repositorios vía `git clone`.

---

## 🧪 Plan de Verificación

### Automated Tests
- Ejecutar linter y tests del backend:
  ```bash
  .venv\Scripts\pytest tests/unit/
  .venv\Scripts\ruff check core/ cognitivo/ sentidos/ memoria/ tests/
  ```

### Manual Verification en Visión Studio
1. Presionar **`Ctrl + B`** o hacer clic en la pestaña activa de la ActivityBar para verificar que la barra lateral se oculte/muestre limpiamente.
2. Hacer clic en **"Abrir Carpeta"** en el Explorador y comprobar que se liste la estructura real de archivos.
3. Probar **"Clonar Repositorio Git"** ingresando un link de GitHub y verificar que se descargue y abra en la interfaz.

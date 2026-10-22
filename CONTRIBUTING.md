# Colaboración de dos integrantes

1. Crear una issue con alcance y responsable antes de comenzar.
2. Actualizar main: `git switch main` y `git pull --ff-only`.
3. Crear una rama: `git switch -c feat/nombre-de-tarea` (o `fix/...`, `docs/...`).
4. Hacer commits pequeños y subir la rama: `git push -u origin HEAD`.
5. Abrir un pull request hacia main; el otro integrante revisa los cambios.
6. Ejecutar `npm run typecheck` y `npm run build` antes de integrar.
7. Integrar mediante squash y eliminar la rama terminada.

Distribución inicial propuesta (acordar nombres en las issues):

| Integrante | Responsabilidad inicial |
| --- | --- |
| A | Estructura, navegación y dashboard |
| B | Mapa territorial y vistas de perfiles |

Comparación, estrategias, metodología y exportación se reparten después. Coordinar cambios en package.json y src/app/App.tsx para evitar conflictos.

Invitar al segundo integrante desde Settings → Collaborators con su usuario real. Se recomienda una regla para main que requiera pull request y una aprobación, si el plan de GitHub lo permite. Estas configuraciones todavía deben aplicarse en GitHub.

No subir credenciales ni datos personales. Las variables VITE_* son públicas en el navegador. No inventar perfiles definitivos: los define el equipo 1 mediante el análisis.

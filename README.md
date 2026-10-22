# ParticipaMX

Frontend del Reto 1: perfiles ciudadanos de participación, Hackathon INE. React + TypeScript + Vite.

## Estado

Estructura inicial y pantalla de bienvenida. Dashboard, mapa, perfiles, comparación, estrategias, metodología y exportación están pendientes. No hay resultados electorales ni conexión a un backend todavía.

El equipo 1 prepara el análisis de datos electorales 2009–2024 y define entre 4 y 6 perfiles a partir de sus resultados. El equipo de desarrollo web construye la plataforma. Fuente del alcance: ParticipaMX_Division_Equipos(1).docx.

## Ejecutar

Recomendado: Node.js 24 y npm.

```sh
git clone https://github.com/ManuelValdivia03/participamx.git
cd participamx
npm ci
npm run dev
```

package-lock.json está incluido. Los demás integrantes deben usar `npm ci` para instalar las mismas versiones. GitHub Actions comprobará los tipos y la compilación en cada pull request hacia main.

```sh
npm run typecheck
npm run build
npm run preview
```

## Estructura

```text
src/
  app/          Composición de la aplicación
  components/   Componentes compartidos
  features/     Módulos por funcionalidad
  services/     Integración de datos
  types/        Tipos compartidos
  styles/       Estilos globales
public/         Archivos estáticos
docs/           Acuerdos con el equipo 1
.github/        Plantilla de pull request
```

Crear cada módulo dentro de features cuando comience su implementación; evitar carpetas por pantalla sin contenido. Consultar [CONTRIBUTING.md](CONTRIBUTING.md) para el flujo de trabajo de dos integrantes.

## Repositorio y colaboración

Repositorio: [ManuelValdivia03/participamx](https://github.com/ManuelValdivia03/participamx). Rama principal: `main`.

Invitar al segundo integrante desde Settings → Collaborators y acordar tareas según [CONTRIBUTING.md](CONTRIBUTING.md). La invitación y las reglas de main deben configurarse en GitHub.

Cada integrante debe usar su propia identidad de Git y autenticarse mediante el flujo de GitHub; no guardar tokens en archivos del proyecto.

## Integración de datos

Acordar el contrato JSON, las claves territoriales, unidades, años y tratamiento de valores faltantes antes de integrar resultados. Ver [docs/datos.md](docs/datos.md).

La licencia de distribución queda pendiente de acuerdo con el equipo y las reglas del hackathon.

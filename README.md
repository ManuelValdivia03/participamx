# ParticipaMX · Equipo 2

Frontend del Reto 1: perfiles ciudadanos de participación, Hackathon INE. React + TypeScript + Vite.

## Estado

Estructura inicial y pantalla de bienvenida. Dashboard, mapa, perfiles, comparación, estrategias, metodología y exportación están pendientes. No hay resultados electorales ni conexión a un backend todavía.

El equipo 1 prepara el análisis de datos electorales 2009–2024 y define entre 4 y 6 perfiles a partir de sus resultados. El equipo 2 desarrolla la plataforma web. Fuente del alcance: ParticipaMX_Division_Equipos(1).docx.

## Ejecutar

Recomendado: Node.js 24 y npm.

```sh
npm install
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

## Crear el repositorio remoto

1. Abrir https://github.com/new con la cuenta propietaria elegida.
2. Nombre sugerido: `participamx-equipo-2`. Elegir visibilidad conforme a las reglas del hackathon.
3. Dejar desmarcadas las opciones de README, .gitignore y licencia: esta carpeta ya contiene los archivos iniciales.
4. Crear el repositorio y copiar su URL HTTPS real.
5. Desde esta carpeta, configurar la identidad real si Git la solicita (`git config user.name` y `git config user.email`). No usar identidades de ejemplo.
6. Ejecutar:

```sh
git add .
git commit -m "chore: iniciar frontend ParticipaMX"
```

Después ejecutar `git remote add origin URL_HTTPS_COPIADA` sustituyendo el marcador por la URL real, y `git push -u origin main`. Autenticarse mediante el flujo de GitHub; no guardar tokens en archivos del proyecto.

Invitar al segundo integrante y acordar tareas según CONTRIBUTING.md. La creación remota, invitación y reglas de main no se configuran mediante estos archivos.

## Integración de datos

Acordar el contrato JSON, las claves territoriales, unidades, años y tratamiento de valores faltantes antes de integrar resultados. Ver [docs/datos.md](docs/datos.md).

La licencia de distribución queda pendiente de acuerdo con el equipo y las reglas del hackathon.

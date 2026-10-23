# ParticipaMX

Aplicación web para consultar perfiles de participación ciudadana en México. La estamos desarrollando para el Reto 1 del Hackathon INE, a partir de datos electorales de 2009 a 2024.

Este repositorio contiene el frontend: navegación, mapas, gráficas, fichas y comparación de perfiles. El equipo de análisis entregará los indicadores y los resultados que se mostrarán en la plataforma.

> Por ahora, las cifras del menú principal y las fichas son ejemplos ficticios. El mapa sí utiliza geometrías de INEGI. Los resultados electorales todavía no están conectados.

## Correr el proyecto

Necesitas Node.js 24 y npm.

```sh
git clone https://github.com/ManuelValdivia03/participamx.git
cd participamx
npm ci
npm run dev
```

Abre la dirección que aparezca en la terminal. Si el puerto está ocupado, Vite elegirá otro.

Para trabajar sobre una copia que ya tienes, entra a su carpeta y ejecuta `npm run dev`. Usa `npm ci` de nuevo cuando cambie el archivo `package-lock.json`.

## Qué funciona

- **Menú principal:** filtros por año y territorio, tarjetas de indicadores, gráfica de evolución y distribución por perfiles. Incluye ejemplos con información incompleta.
- **Mapa territorial:** selección de estados, municipios y alcaldías; búsqueda por nombre o clave INE y regreso a la vista nacional.
- **Perfiles ciudadanos:** fichas con indicadores, características y acciones; comparación de dos o tres perfiles.
- **Metodología:** explicación del proceso previsto para el análisis.

La interfaz tiene modo claro y oscuro y se adapta a pantallas pequeñas.

El mapa conserva las claves INEGI de sus geometrías y usa correspondencias nominales para mostrar las claves INE de cada año. Los casos que requieren revisión aparecen como pendientes. Cambiar de año no cambia los límites del mapa: la división municipal sigue siendo la de 2024.

## Qué falta

Conectar la entrega del equipo de análisis, completar metodología y estrategias con sus resultados, añadir la exportación de fichas y reportes y preparar la publicación de la plataforma.

La limpieza de los archivos, el cálculo de indicadores y la definición de clusters quedan fuera del frontend.

## Comandos

| Comando | Para qué sirve |
| --- | --- |
| `npm run dev` | Iniciar el servidor de desarrollo |
| `npm run typecheck` | Revisar los tipos de TypeScript |
| `npm run test:map` | Comprobar geometrías y correspondencias de claves |
| `npm run build` | Generar la versión de producción en `dist/` |
| `npm run preview` | Revisar localmente la versión compilada |

Antes de subir cambios, revisa los tipos, las pruebas del mapa y la compilación. GitHub Actions también ejecuta las pruebas y compila el proyecto en los pull requests hacia `main`.

## Dónde está cada cosa

```text
src/
  app/                 Navegación y apariencia general
  components/          Componentes compartidos
  features/
    dashboard/         Indicadores y gráficas del menú principal
    map/               Mapa y selección territorial
    profiles/          Fichas y comparación
    methodology/       Página de metodología
  styles/              Estilos de la aplicación
public/data/           Geometrías y correspondencias territoriales
scripts/               Importación de catálogos y comprobaciones
docs/                  Fuentes, acuerdos de datos y notas de integración
```

Usamos React, TypeScript y Vite. El mapa se dibuja con SVG y D3 Geo; los municipios se cargan por estado desde los archivos del proyecto.

## Para trabajar en equipo

Crea una rama por tarea y abre un pull request hacia `main` cuando esté lista. Mantén los datos de ejemplo identificados y separados de los resultados reales. El flujo de colaboración está en [CONTRIBUTING.md](CONTRIBUTING.md).

Los formatos de entrega son propuestas para acordar con el equipo de análisis. Las notas están aquí:

- [Acuerdo de datos](docs/datos.md)
- [Dashboard](docs/dashboard-frontend.md)
- [Fichas y comparación](docs/perfiles-frontend.md)
- [Fuentes y geometrías del mapa](docs/mapa.md)
- [Claves INE e INEGI](docs/claves-territoriales.md)

## Fuentes y licencia

Las fuentes geográficas, sus licencias y las modificaciones realizadas están documentadas en [las notas del mapa](docs/mapa.md). La licencia del código sigue pendiente de acuerdo entre los integrantes y las reglas del hackathon.

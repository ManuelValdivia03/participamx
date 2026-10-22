# Mapa de entidades de México

La primera versión permite seleccionar cualquiera de las 32 entidades por clic, toque, teclado (Tab y Enter/Espacio) o selector. La selección enfoca su geometría; Vista nacional restablece el encuadre. La ficha muestra nombre y clave estatal. No incluye municipios ni indicadores electorales todavía.

## Procedencia

- Fuente original indicada por geoBoundaries: Instituto Nacional de Estadística y Geografía (INEGI), límites representados de 2020.
- Distribución: geoBoundaries gbOpen, MEX ADM1, ID `MEX-ADM1-31927357`, compilación del 21 de febrero de 2024.
- Metadatos: https://www.geoboundaries.org/api/current/gbOpen/MEX/ADM1/
- Descarga fijada: https://github.com/wmgeolab/geoBoundaries/raw/90a1d52/releaseData/gbOpen/MEX/ADM1/geoBoundaries-MEX-ADM1_simplified.geojson
- Fuente original enlazada por el proveedor: https://data.humdata.org/dataset/mexican-administrative-level-0-country-1-estado-and-2-municipio-boundary-polygons
- Licencia indicada en los metadatos: Creative Commons Attribution 3.0 IGO, https://creativecommons.org/licenses/by/3.0/igo/

Se conserva la geometría simplificada en `src/features/map/data/mexico-states.json`. No se requieren servicios de teselas, tokens ni peticiones externas para dibujar el mapa. El módulo se carga al abrir Mapa territorial.

## Adaptaciones

Se proyecta con Mercator y se ajusta la orientación de los anillos a la convención de D3 para evitar dibujar el complemento de los polígonos. Los nombres se presentan en español actual. El catálogo local asigna claves estatales 01–32, conservadas como cadenas.

La fuente denomina Distrito Federal a Ciudad de México y asigna `MX-MEX` tanto a esa entidad como a Mexico. Por ello no se usa `shapeISO` como identificador: el catálogo distingue Ciudad de México (09) y Estado de México (15) por el nombre de origen. Las claves deberán cotejarse con los archivos electorales al integrar indicadores.

Los colores señalan selección, no participación electoral. Los límites generalizados sirven para exploración visual; su fecha y simplificación deben considerarse al integrar series de otros años.

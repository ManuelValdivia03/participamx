# Mapa de entidades de México

Se pueden seleccionar las 32 entidades por clic, toque, teclado (Tab y Enter/Espacio) o selector. Al elegir un estado se carga su división municipal; se pueden buscar municipios por nombre (sin distinguir acentos) o clave de cinco dígitos, seleccionarlos en el mapa o la lista y enfocar su geometría. La ficha muestra nombre, estado y claves. Ciudad de México usa la denominación alcaldía. Volver al estado y Vista nacional restablecen cada nivel. No incluye indicadores electorales todavía.

## Municipios y demarcaciones (2024)

- Fuente: INEGI, Áreas geoestadísticas municipales 2024, capa `00mun` del [servicio oficial](https://lcidsig.inegi.org.mx/server/rest/services/Hosted/%C3%81reas_geoestad%C3%ADsticas_municipales_2024/FeatureServer/0).
- Copia local: 2,478 registros en 32 archivos `public/data/municipalities/01.json` a `32.json`. La aplicación descarga solo el estado elegido y conserva sus datos en memoria durante la sesión. Cancela solicitudes al cambiar de estado y ofrece reintento ante errores.
- Claves geográficas INEGI: `cve_ent` (2), `cve_mun` (3) y `cvegeo` (5), conservadas como cadenas; `cvegeo = cve_ent + cve_mun`. Los nombres proceden de `nomgeo`. Son identificadores de geometría; no deben confundirse con las claves municipales INE. La interfaz usa como referencia principal la clave INE del año seleccionado mediante las [correspondencias territoriales](claves-territoriales.md).
- Transformaciones: reproyección del servicio a WGS84, generalización a 0.001 grados, cinco decimales, selección de atributos y separación por estado. Normalización de anillos en el navegador. Las geometrías son para exploración visual.
- Metadatos: `public/data/municipalities/metadata.json`, con fuente, transformación, recuentos y metadatos de la capa. Reproducir descarga: `node scripts/import-municipalities.mjs` (requiere acceso a Internet).
- Reutilización conforme a los [Términos de libre uso de INEGI](https://www.inegi.org.mx/inegi/terminos.html). Se muestra la atribución y se identifican las transformaciones de ParticipaMX.

Los estados de la vista nacional representan 2020 y la división municipal corresponde a 2024: pueden existir diferencias en los bordes. Se encuadra cada estado a partir de su colección municipal cuando está disponible. Para indicadores de otros años se debe validar la correspondencia territorial, incluidas altas y cambios de municipio; no se trasladan resultados automáticamente entre años.

`npm run test:map` valida las 32 entidades y todas las geometrías municipales del conjunto final: recuentos, unicidad y composición de claves, áreas esféricas y encuadres.

## Procedencia

- Fuente original indicada por geoBoundaries: Instituto Nacional de Estadística y Geografía (INEGI), límites representados de 2020.
- Distribución: geoBoundaries gbOpen, MEX ADM1, ID `MEX-ADM1-31927357`, compilación del 21 de febrero de 2024.
- Metadatos: https://www.geoboundaries.org/api/current/gbOpen/MEX/ADM1/
- Descarga fijada: https://github.com/wmgeolab/geoBoundaries/raw/90a1d52/releaseData/gbOpen/MEX/ADM1/geoBoundaries-MEX-ADM1_simplified.geojson
- Fuente original enlazada por el proveedor: https://data.humdata.org/dataset/mexican-administrative-level-0-country-1-estado-and-2-municipio-boundary-polygons
- Licencia indicada en los metadatos: Creative Commons Attribution 3.0 IGO, https://creativecommons.org/licenses/by/3.0/igo/

La geometría simplificada se almacena en `src/features/map/data/mexico-states.json`, con coordenadas redondeadas a cuatro decimales para reducir la descarga. No se requieren servicios de teselas, tokens ni peticiones externas para dibujar el mapa. El módulo se carga al abrir Mapa territorial.

## Adaptaciones

Se proyecta con Mercator y se normaliza cada anillo por separado a la convención de D3 (exteriores horarios e interiores antihorarios). Se omiten anillos degenerados por el redondeo; de otro modo, pequeñas islas colapsadas podían interpretarse como el globo y generar un rectángulo que reducía México a un punto. `npm run test:map` comprueba áreas, claves y encuadres con el archivo final distribuido, y se ejecuta también en CI. Los nombres se presentan en español actual. El catálogo local asigna claves estatales 01–32, conservadas como cadenas.

La fuente denomina Distrito Federal a Ciudad de México y asigna `MX-MEX` tanto a esa entidad como a Mexico. Por ello no se usa `shapeISO` como identificador: el catálogo distingue Ciudad de México (09) y Estado de México (15) por el nombre de origen. Las claves deberán cotejarse con los archivos electorales al integrar indicadores.

Los colores señalan selección, no participación electoral. Los límites generalizados sirven para exploración visual; su fecha y simplificación deben considerarse al integrar series de otros años.

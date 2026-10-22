# Identificadores electorales INE y geometrías INEGI

ParticipaMX utiliza `año + clave INE` como referencia de integración electoral municipal. `inegiCode` identifica únicamente la geometría y se conserva para trazabilidad; nunca es sustituto automático de una clave INE ausente.

## Datos de origen y correspondencias

Las claves electorales proceden de `EDOCVE` (2 dígitos) y `MPIOCVE` (3) de los seis ZIP generales DatosAbiertos_DECEyEC_ConteosCensales, proporcionados por el usuario. Se conservan los ceros iniciales. No se mezclan los ZIP de modalidades especiales.

Los archivos `public/data/ine-crosswalk/01.json` a `32.json` contienen una tabla por año (2009, 2012, 2015, 2018, 2021 y 2024), indexada por clave de geometría INEGI. Cada entrada guarda clave y nombre INE y método de correspondencia. `metadata.json` identifica archivos fuente, huella de la auditoría y todos los registros no resueltos.

| Año | Correspondencias nominales únicas | Registros INE pendientes |
| --- | ---: | ---: |
| 2009 | 2443 | 15 |
| 2012 | 2440 | 15 |
| 2015 | 2443 | 15 |
| 2018 | 2448 | 15 |
| 2021 | 2457 | 11 |
| 2024 | 2451 | 26 |

Se acepta solo una coincidencia de nombre normalizado dentro de la misma entidad, sin acentos, espacios, signos ni diferencias de mayúsculas, y con unicidad en ambos sentidos. No se hace emparejamiento aproximado ni se presume igualdad de códigos. Esta correspondencia es nominal y derivada por ParticipaMX: no es una tabla oficial de equivalencias ni valida que los límites históricos sean idénticos.

Ejemplo comprobado en los archivos: San Francisco de los Romo tiene INE `01010` e INEGI `01011`; El Llano tiene INE `01011` e INEGI `01010`. La prueba automática verifica que no se intercambien.

## Uso en la aplicación

- El selector de año cambia las claves y limpia la selección municipal; el año no modifica las geometrías INEGI 2024.
- `properties.code` y `ineCode` contienen la clave INE o `null`; `ineName` conserva el nombre electoral. `inegiCode` mantiene el identificador original del polígono.
- La selección gráfica usa `inegiCode` internamente para permitir explorar también territorios sin correspondencia. Esto no asigna una clave electoral.
- La búsqueda usa nombre geográfico, nombre electoral y clave INE del año; no interpreta una clave INEGI como electoral.
- La ficha muestra la clave INE como principal y la INEGI como referencia secundaria.
- Un caso no resuelto aparece como “Correspondencia territorial pendiente”. No implica ausencia de datos, inexistencia histórica ni participación cero.
- `electoralJoinKey` devuelve `año:claveINE` o `null`; los futuros indicadores no deben enlazarse cuando devuelve `null`. La homologación de límites históricos debe revisarse antes de comparar indicadores de distintos años.

Los nombres duplicados (por ejemplo, San Juan Mixtepec y San Pedro Mixtepec en Oaxaca), abreviaturas y cambios de nombre quedan sin asignar mientras se revisan con evidencia adicional. Villa de Pozos tampoco recibe una clave inventada si no figura en el ZIP elegido.

## Reproducción y pruebas

La auditoría local está en `../analisis-cobertura/auditoria.json` y no se publica con el repositorio. Para reconstruir las tablas desde ella:

```sh
python scripts/build-ine-crosswalk.py ../analisis-cobertura/auditoria.json
npm run test:map
```

Las pruebas verifican las seis anualidades, unicidad de claves, existencia de geometrías, recuentos, intercambio de códigos en Aguascalientes y bloqueo de nombres ambiguos o correspondencias ausentes. No prueban equivalencia histórica de límites.

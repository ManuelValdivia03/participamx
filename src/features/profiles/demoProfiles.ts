import type { ProfileDataset } from './types'

// These records exercise the interface only. They are not clusters derived from INE data.
export const demoProfiles: ProfileDataset = {
  mode: 'demo',
  year: 2024,
  source: 'Datos ficticios para probar la interfaz. No proceden de los ZIP electorales.',
  updatedAt: null,
  participationDefinition: 'Porcentajes ficticios de demostración. El equipo de análisis entregará la definición y el denominador del indicador real.',
  profiles: [
    {
      id: 'demo-a', name: 'Perfil de ejemplo A',
      summary: 'Una ficha para explorar indicadores, características y acciones en un mismo lugar.',
      description: 'Esta descripción ilustra cómo se presentará la interpretación de un perfil. Los perfiles definitivos, sus nombres y sus características serán entregados por el equipo de análisis.',
      participation: 68.4, coverage: 96.2, medianAge: 42, municipalityCount: 125,
      characteristics: ['Ejemplo de característica territorial.', 'Ejemplo de un patrón descrito por el análisis.', 'Ejemplo de contexto para leer los indicadores.'],
      strategies: ['Ejemplo de acción: preparar materiales informativos accesibles.', 'Ejemplo de acción: acercar información a espacios comunitarios.'],
      limitations: ['Todos los valores de esta ficha son ficticios.', 'No debe usarse para tomar decisiones sobre territorios o personas.'],
    },
    {
      id: 'demo-b', name: 'Perfil de ejemplo B',
      summary: 'Otro conjunto ficticio para probar la comparación entre fichas.',
      description: 'Este ejemplo permite comprobar cómo cambian los indicadores y la información contextual entre dos fichas. No representa una agrupación ciudadana real.',
      participation: 54.7, coverage: 91.8, medianAge: 35, municipalityCount: 210,
      characteristics: ['Ejemplo de una diferencia respecto a otra ficha.', 'Ejemplo de información sobre el contexto local.'],
      strategies: ['Ejemplo de acción: ofrecer contenidos en distintos formatos.', 'Ejemplo de acción: habilitar espacios de diálogo ciudadano.'],
      limitations: ['Valores simulados, sin evidencia electoral asociada.', 'La comparación demuestra la interfaz; no evalúa a la ciudadanía.'],
    },
    {
      id: 'demo-c', name: 'Perfil de ejemplo C',
      summary: 'Un ejemplo con información parcial para probar datos no disponibles.',
      description: 'La ficha mantiene visibles los indicadores pendientes sin sustituirlos por cero. El equipo de análisis definirá el alcance de los datos que entregue.',
      participation: 61.2, coverage: null, medianAge: null, municipalityCount: 87,
      characteristics: ['Ejemplo de contexto con indicadores pendientes.'],
      strategies: ['Ejemplo de acción: adaptar materiales al contexto que describa el análisis.'],
      limitations: ['Cobertura y edad mediana no disponibles en este ejemplo.', 'Los valores restantes también son ficticios.'],
    },
    {
      id: 'demo-d', name: 'Perfil de ejemplo D',
      summary: 'Una cuarta ficha para probar la selección de hasta tres perfiles.',
      description: 'El número de ejemplos es una elección de interfaz. No anticipa la cantidad de clusters que se obtendrá al analizar los datos.',
      participation: 72.1, coverage: 98.4, medianAge: 46, municipalityCount: 163,
      characteristics: ['Ejemplo de una lectura alternativa de los indicadores.', 'Ejemplo de un hallazgo expresado en lenguaje claro.'],
      strategies: ['Ejemplo de acción: facilitar la consulta y comprensión de información cívica.'],
      limitations: ['Datos de demostración, no un resultado del modelo.'],
    },
  ],
}

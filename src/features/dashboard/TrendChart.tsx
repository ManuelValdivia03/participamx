import { dashboardNumber } from './types'

function electionType(year: number): string {
  return [2012, 2018, 2024].includes(year)
    ? 'Presidencial'
    : 'Intermedia'
}

export function TrendChart({
  points,
  selectedYear,
  onSelectYear,
  demo
}: {
  points: { year: number; value: number | null }[]
  selectedYear: number
  onSelectYear: (year: number) => void
  demo: boolean
}) {
  const x = (index: number) =>
    55 + index * (590 / Math.max(points.length - 1, 1))

  const y = (value: number) => 220 - value * 1.8

  const segments: string[] = []
  let current = ''

  points.forEach((point, index) => {
    if (point.value === null) {
      if (current) segments.push(current)
      current = ''
      return
    }

    current += `${current ? 'L' : 'M'}${x(index)},${y(point.value)} `
  })

  if (current) segments.push(current)

  const available = points.some(point => point.value !== null)

  return (
    <div className="trend-chart">
      {!available ? (
        <p className="dashboard-empty">
          La serie temporal no está disponible para este territorio.
        </p>
      ) : (
        <svg
          viewBox="0 0 700 270"
          role="img"
          aria-label={`Evolución de la participación en porcentaje${demo ? ', datos ficticios' : ''}. Valores disponibles en la tabla inferior.`}
        >
          <title>
            Evolución de participación · escala de 0 a 100%
          </title>

          {[0, 25, 50, 75, 100].map(value => (
            <g key={value}>
              <line
                className="trend-gridline"
                x1="55"
                x2="645"
                y1={y(value)}
                y2={y(value)}
              />
              <text
                className="trend-axis"
                x="40"
                y={y(value) + 4}
                textAnchor="end"
              >
                {value}%
              </text>
            </g>
          ))}

          {segments.map((segment, index) => (
            <path
              className="trend-line"
              d={segment}
              key={index}
              fill="none"
            />
          ))}

          {points.map((point, index) => (
            <g key={point.year}>
              {point.value !== null && (
                <circle
                  className={`trend-point${point.year === selectedYear ? ' selected' : ''}`}
                  cx={x(index)}
                  cy={y(point.value)}
                  r={point.year === selectedYear ? 7 : 4}
                >
                  <title>
                    {point.year}: {point.value}%
                    {demo ? ' (ficticio)' : ''}
                    {' · '}
                    {electionType(point.year)}
                  </title>
                </circle>
              )}

              <text
                className={`trend-axis${point.year === selectedYear ? ' selected' : ''}`}
                x={x(index)}
                y="250"
                textAnchor="middle"
              >
                {point.year}
              </text>
            </g>
          ))}
        </svg>
      )}

      <div
        className="trend-year-buttons"
        aria-label="Elegir año de la serie"
      >
        {points.map(point => (
          <button
            type="button"
            key={point.year}
            aria-pressed={point.year === selectedYear}
            onClick={() => onSelectYear(point.year)}
          >
            {point.year}
            <small>{dashboardNumber(point.value, '%')}</small>
            <small>{electionType(point.year)}</small>
          </button>
        ))}
      </div>

      <details className="dashboard-data-table">
        <summary>Consultar valores en tabla</summary>

        <table>
          <caption>
            Participación por año
            {demo ? ' · Valores ficticios' : ''}
          </caption>

          <thead>
            <tr>
              <th scope="col">Año</th>
              <th scope="col">Tipo de elección</th>
              <th scope="col">Participación</th>
            </tr>
          </thead>

          <tbody>
            {points.map(point => (
              <tr key={point.year}>
                <th scope="row">{point.year}</th>
                <td>{electionType(point.year)}</td>
                <td>{dashboardNumber(point.value, '%')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>

      <p className="dashboard-chart-note">
        La gráfica conserva los años sin información como huecos;
        no los convierte en cero.
      </p>
    </div>
  )
}

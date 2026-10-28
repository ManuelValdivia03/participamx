import { comparableReferenceHelp, countDefinitions, percentagePointsHelp } from './statisticsPresentation'

export function StatisticalHelp() {
  return <details className="statistics-help"><summary>Cómo leer porcentajes, referencias y abreviaturas</summary>
    <p>{percentagePointsHelp}</p><p>{comparableReferenceHelp}</p>
    <dl>{countDefinitions.map(([code, name, meaning]) => <div key={code}><dt><abbr title={name}>{code}</abbr> · {name}</dt><dd>{meaning}</dd></div>)}</dl>
    <p>Una tasa de participación se calcula sobre SV + NV. Una proporción de lista nominal se calcula sobre LN. Los porcentajes de municipios o segmentos cuentan esas unidades, no personas.</p>
    <p>Las diferencias usan valores originales y se redondean sólo al mostrarse. Por eso restar dos etiquetas redondeadas puede dar una centésima distinta. Un valor no disponible no se sustituye por cero.</p>
  </details>
}

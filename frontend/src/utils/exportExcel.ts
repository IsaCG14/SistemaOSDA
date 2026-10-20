/**
 * Exportación a Excel (.xlsx) de documentos - OSDA
 * Genera un archivo Excel real con SheetJS, respetando los filtros activos.
 */
import * as XLSX from 'xlsx'

export interface DocumentoExport {
  correlativo: string
  tipo_doc_codigo?: string
  tipo_documento?: string
  oficina_origen_sigla?: string
  oficina_origen?: string
  oficina_destino_sigla?: string
  oficina_destino?: string
  fecha_documento?: string | null
  fecha_recepcion?: string | null
  remitente?: string | null
  destinatario?: string | null
  asunto?: string | null
  estado?: string
  prioridad?: string
  folios?: number | null
  observaciones?: string | null
}

const CABECERAS = [
  'Correlativo', 'Tipo', 'Oficina Origen', 'Oficina Destino',
  'Fecha Documento', 'Fecha Recepción', 'Remitente', 'Destinatario',
  'Asunto', 'Estado', 'Prioridad', 'Folios', 'Observaciones',
]

export async function exportarDocumentosExcel(
  fetchDocumentos: (limit: number, offset: number) => Promise<DocumentoExport[]>,
  nombreArchivo?: string,
): Promise<number> {
  // Paginar la API hasta traer TODOS los documentos que matcheen los filtros
  const PAGE = 100
  let offset = 0
  let todas: DocumentoExport[] = []
  for (;;) {
    const lote = await fetchDocumentos(PAGE, offset)
    todas = todas.concat(lote)
    if (lote.length < PAGE) break
    offset += PAGE
    if (offset >= 5000) break // tope de seguridad
  }

  const filas = todas.map((d) => [
    d.correlativo,
    d.tipo_doc_codigo || d.tipo_documento || '',
    d.oficina_origen_sigla || d.oficina_origen || '',
    d.oficina_destino_sigla || d.oficina_destino || '',
    d.fecha_documento || '',
    d.fecha_recepcion || '',
    d.remitente || '',
    d.destinatario || '',
    d.asunto || '',
    d.estado || '',
    d.prioridad || '',
    d.folios ?? '',
    d.observaciones || '',
  ])

  const hoja = XLSX.utils.aoa_to_sheet([CABECERAS, ...filas])
  // Anchos razonables para las columnas principales
  hoja['!cols'] = [
    { wch: 24 }, { wch: 10 }, { wch: 16 }, { wch: 16 }, { wch: 14 },
    { wch: 14 }, { wch: 28 }, { wch: 28 }, { wch: 50 }, { wch: 12 },
    { wch: 10 }, { wch: 8 }, { wch: 40 },
  ]
  hoja['!autofilter'] = { ref: XLSX.utils.encode_range({ s: { r: 0, c: 0 }, e: { r: filas.length, c: CABECERAS.length - 1 } }) }

  const libro = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(libro, hoja, 'Documentos')

  const fecha = new Date().toISOString().slice(0, 10)
  const nombre = nombreArchivo || `documentos_${fecha}`
  XLSX.writeFile(libro, `${nombre}.xlsx`)
  return todas.length
}

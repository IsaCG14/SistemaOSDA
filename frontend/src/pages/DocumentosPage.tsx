import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { useState, useEffect } from 'react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { 
  Search, Filter, Plus, Download, Edit, Eye, Trash2, 
  Loader2, ChevronLeft, ChevronRight, FileText, Building2,
  XCircle, Loader2 as Loader2Icon
} from 'lucide-react'
import { Documento } from '../types'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { EmptyState } from '../components/EmptyState'
import { exportarDocumentosExcel } from '../utils/exportExcel'

const ESTADO_COLORES: Record<string, string> = {
  RECIBIDO: 'badge-info',
  EN_TRAMITE: 'badge-warning',
  RESPONDIDO: 'badge-success',
  ARCHIVADO: 'badge-gray',
  DERIVADO: 'badge-info',
  RECHAZADO: 'badge-danger',
  EXTRAVIADO: 'badge-danger',
}

const TIPOS_DOCUMENTO = [
  'MEMO', 'OFICIO', 'CIRCULAR', 'INFORME', 'NOTA', 
  'ACTA', 'RESOLUCION', 'SOLICITUD', 'RECIBO', 'OTRO'
]

export function DocumentosPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(20)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [estadoFiltro, setEstadoFiltro] = useState('')
  const [tipoFiltro, setTipoFiltro] = useState('')
  const [oficinaOrigenFiltro, setOficinaOrigenFiltro] = useState('')
  const [oficinaDestinoFiltro, setOficinaDestinoFiltro] = useState('')
  const [fechaDesde, setFechaDesde] = useState('')
  const [fechaHasta, setFechaHasta] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const [exportando, setExportando] = useState(false)
  const [selectedDoc, setSelectedDoc] = useState<Documento | null>(null)
  const [editingDoc, setEditingDoc] = useState<Documento | null>(null)
  const [formData, setFormData] = useState({
    correlativo: '',
    tipo_doc_codigo: '',
    oficina_origen_sigla: '',
    oficina_destino_sigla: '',
    fecha_documento: '',
    fecha_recepcion: '',
    remitente: '',
    destinatario: '',
    remitente_id: '',
    destinatario_id: '',
    asunto: '',
    folios: 0,
    observaciones: '',
    prioridad: 'NORMAL',
    estado: 'RECIBIDO',
  })

  // Debounce search input (300ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search)
    }, 300)
    return () => clearTimeout(timer)
  }, [search])

  // Fetch oficinas for select filters
  const { data: oficinas = [] } = useQuery({
    queryKey: ['oficinas-select'],
    queryFn: async () => {
      const resp = await api.get('/oficinas')
      return resp.data
    },
    select: (data) => data.filter(o => o.activa).sort((a, b) => a.sigla.localeCompare(b.sigla))
  })

  // Fetch tipos de documento for select filters
  const { data: tiposDocumento = [] } = useQuery({
    queryKey: ['tipos-documento-select'],
    queryFn: async () => {
      const resp = await api.get('/tipos-documento')
      return resp.data
    },
    select: (data) => data.sort((a, b) => a.codigo.localeCompare(b.codigo))
  })

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ['documentos', page, pageSize, debouncedSearch, estadoFiltro, tipoFiltro, oficinaOrigenFiltro, oficinaDestinoFiltro, fechaDesde, fechaHasta],
    queryFn: async () => {
      const params = new URLSearchParams()
      params.append('limit', pageSize.toString())
      params.append('offset', (page * pageSize).toString())
      if (debouncedSearch) params.append('search', debouncedSearch)
      if (estadoFiltro) params.append('estado', estadoFiltro)
      if (tipoFiltro) params.append('tipo_documento', tipoFiltro)
      if (oficinaOrigenFiltro) params.append('oficina_origen', oficinaOrigenFiltro)
      if (oficinaDestinoFiltro) params.append('oficina_destino', oficinaDestinoFiltro)
      if (fechaDesde) params.append('fecha_desde', fechaDesde)
      if (fechaHasta) params.append('fecha_hasta', fechaHasta)
      
      const resp = await api.get(`/documentos?${params}`)
      return resp.data
    },
    placeholderData: (previousData) => previousData,
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/documentos/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documentos'] })
    },
  })

  const updateMutation = useMutation({
    mutationFn: async (doc: Partial<Documento> & { id: string }) => {
      console.log('updateMutation mutationFn called', doc)
      const { id, ...rest } = doc
      console.log('Sending to backend:', { id, rest })
      const resp = await api.put(`/documentos/${id}`, rest)
      console.log('updateMutation response', resp.data)
      return resp.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documentos'] })
      setEditingDoc(null)
    },
    onError: (error: any) => {
      console.error('updateMutation error', error)
      console.error('error.response:', error.response)
      console.error('error.response.data:', error.response?.data)
      console.error('error.response.status:', error.response?.status)
      console.error('error.config:', error.config)
      console.error('error.config.data:', error.config?.data)
    }
  })

  const handleDelete = async (id: string) => {
    if (confirm('¿Está seguro de archivar este documento?')) {
      await deleteMutation.mutateAsync(id)
    }
  }

  // Exportar a Excel TODOS los documentos que matchean los filtros activos
  const handleExportar = async () => {
    setExportando(true)
    try {
      const total = await exportarDocumentosExcel(async (limit, offset) => {
        const params = new URLSearchParams()
        params.append('limit', limit.toString())
        params.append('offset', offset.toString())
        if (debouncedSearch) params.append('search', debouncedSearch)
        if (estadoFiltro) params.append('estado', estadoFiltro)
        if (tipoFiltro) params.append('tipo_documento', tipoFiltro)
        if (oficinaOrigenFiltro) params.append('oficina_origen', oficinaOrigenFiltro)
        if (oficinaDestinoFiltro) params.append('oficina_destino', oficinaDestinoFiltro)
        if (fechaDesde) params.append('fecha_desde', fechaDesde)
        if (fechaHasta) params.append('fecha_hasta', fechaHasta)
        const resp = await api.get(`/documentos?${params}`)
        return resp.data
      })
      alert(`Se exportaron ${total} documento${total === 1 ? '' : 's'} a Excel.`)
    } catch (err: any) {
      console.error('Error exportando:', err)
      alert('No se pudo exportar: ' + (err?.message || 'error desconocido'))
    } finally {
      setExportando(false)
    }
  }

  const openView = (doc: Documento) => {
    setSelectedDoc(doc)
  }

  const openEdit = (doc: Documento) => {
    setEditingDoc(doc)
    setFormData({
      correlativo: doc.correlativo,
      tipo_doc_codigo: doc.tipo_doc_codigo || doc.tipo_documento,
      oficina_origen_sigla: doc.oficina_origen_sigla || doc.oficina_origen,
      oficina_destino_sigla: doc.oficina_destino_sigla || doc.oficina_destino,
      fecha_documento: doc.fecha_documento || '',
      fecha_recepcion: doc.fecha_recepcion || '',
      remitente: doc.remitente || doc.remitente_id || '',
      destinatario: doc.destinatario || doc.destinatario_id || '',
      remitente_id: doc.remitente_id || '',
      destinatario_id: doc.destinatario_id || '',
      asunto: doc.asunto || '',
      folios: doc.folios || 0,
      observaciones: doc.observaciones || '',
      prioridad: doc.prioridad || 'NORMAL',
      estado: doc.estado || 'RECIBIDO',
    })
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    console.log('handleSubmit called', { editingDoc, formData })
    if (editingDoc) {
      updateMutation.mutate({ ...formData, id: editingDoc.id })
    }
  }

  const closeModals = () => {
    setSelectedDoc(null)
    setEditingDoc(null)
  }

  if (isLoading && !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="card p-8 text-center">
        <p className="text-red-600 dark:text-red-400">Error cargando documentos: {(error as Error).message}</p>
      </div>
    )
  }

  const documentos = data || []
  const totalPages = Math.ceil((data?.length || 0) / pageSize)

  return (
    <div className="space-y-6 bg-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-heading">Documentos</h1>
          <p className="text-muted mt-1">Gestión y consulta de documentos registrados</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => handleExportar()}
            disabled={exportando}
            className="btn-secondary flex items-center gap-2"
          >
            {exportando ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            {exportando ? 'Exportando...' : 'Exportar'}
          </button>
          <button className="btn-primary flex items-center gap-2">
            <Plus className="w-4 h-4" />
            Nuevo Documento
          </button>
        </div>
      </div>

      {/* Filtros */}
      <div className="card">
        <div className="p-4 border-b border-default flex items-center justify-between">
          <h2 className="text-lg font-semibold text-heading">Filtros</h2>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="btn-secondary text-sm flex items-center gap-1"
          >
            {showFilters ? 'Ocultar' : 'Mostrar'} filtros
          </button>
        </div>
      
        {showFilters && (
          <div className="p-4 space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4">
              <div>
                <label className="label">Buscar</label>
                <div className="flex gap-1">
                  <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') setDebouncedSearch(search)
                    }}
                    className="input flex-1"
                    placeholder="Correlativo, asunto, remitente... (busca al escribir, ignora acentos)"
                  />
                  <button
                    type="button"
                    onClick={() => setDebouncedSearch(search)}
                    className="btn-secondary flex items-center justify-center px-3"
                    aria-label="Buscar"
                  >
                    <Search className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <div>
                <label className="label">Estado</label>
                <select
                  value={estadoFiltro}
                  onChange={(e) => setEstadoFiltro(e.target.value)}
                  className="input"
                >
                  <option value="">Todos</option>
                  {Object.keys(ESTADO_COLORES).map(e => (
                    <option key={e} value={e}>{e}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Tipo</label>
                <select
                  value={tipoFiltro}
                  onChange={(e) => setTipoFiltro(e.target.value)}
                  className="input"
                >
                  <option value="">Todos</option>
                  {TIPOS_DOCUMENTO.map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Oficina Origen</label>
                <select
                  value={oficinaOrigenFiltro}
                  onChange={(e) => setOficinaOrigenFiltro(e.target.value)}
                  className="input"
                >
                  <option value="">Todas</option>
                  {oficinas.map(o => (
                    <option key={o.sigla} value={o.sigla}>{o.sigla} - {o.nombre}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Oficina Destino</label>
                <select
                  value={oficinaDestinoFiltro}
                  onChange={(e) => setOficinaDestinoFiltro(e.target.value)}
                  className="input"
                >
                  <option value="">Todas</option>
                  {oficinas.map(o => (
                    <option key={o.sigla} value={o.sigla}>{o.sigla} - {o.nombre}</option>
                  ))}
                </select>
              </div>
              <div className="sm:col-span-2 lg:col-span-2 flex gap-4">
                <div className="flex-1">
                  <label className="label">Fecha desde</label>
                  <input
                    type="date"
                    value={fechaDesde}
                    onChange={(e) => setFechaDesde(e.target.value)}
                    className="input"
                  />
                </div>
                <div className="flex-1">
                  <label className="label">Fecha hasta</label>
                  <input
                    type="date"
                    value={fechaHasta}
                    onChange={(e) => setFechaHasta(e.target.value)}
                    className="input"
                  />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Tabla de documentos */}
      <div className="card">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-default">
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Correlativo</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Tipo</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Oficinas</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Fechas</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Asunto</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-default">
              {documentos.map((doc: Documento) => (
                <tr key={doc.id} className="card-hover">
                  <td className="px-4 py-3">
                    <code className="text-sm font-mono text-heading">{doc.correlativo}</code>
                  </td>
                  <td className="px-4 py-3">
                    <span className="badge badge-gray">{doc.tipo_doc_codigo || doc.tipo_documento}</span>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted">
                    <div className="flex items-center gap-1">
                      <Building2 className="w-3 h-3" />
                      <span>{doc.oficina_origen_sigla || doc.oficina_origen} → {doc.oficina_destino_sigla || doc.oficina_destino}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted">
                    <div>Doc: {doc.fecha_documento ? (() => { const [y,m,d] = doc.fecha_documento.split('-').map(Number); return format(new Date(y, m-1, d), 'dd/MM/yyyy', { locale: es }) })() : '-'}</div>
                    <div>Rec: {doc.fecha_recepcion ? (() => { const [y,m,d] = doc.fecha_recepcion.split('-').map(Number); return format(new Date(y, m-1, d), 'dd/MM/yyyy', { locale: es }) })() : '-'}</div>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted max-w-md truncate">
                    {doc.asunto || '-'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => openView(doc)}
                        className="p-2 rounded-lg btn-ghost"
                        aria-label="Ver detalle"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => openEdit(doc)}
                        className="p-2 rounded-lg btn-ghost"
                        aria-label="Editar"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(doc.id)}
                        disabled={deleteMutation.isPending}
                        className="p-2 rounded-lg btn-ghost text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300"
                        aria-label="Archivar"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!documentos.length && (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center">
                    <EmptyState
                      icon={FileText}
                      title="No hay documentos"
                      description="No se encontraron documentos con los filtros actuales"
                    />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Paginación */}
        {documentos.length > 0 && (
          <div className="p-4 border-t border-default flex items-center justify-between">
            <p className="text-sm text-muted">
              Mostrando {page * pageSize + 1} - {Math.min((page + 1) * pageSize, documentos.length)} de {documentos.length}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(0, p - 1))}
                disabled={page === 0}
                className="p-2 rounded-lg btn-ghost disabled:opacity-50"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-sm text-muted px-2">
                Página {page + 1} de {totalPages || 1}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="p-2 rounded-lg btn-ghost disabled:opacity-50"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Modal Ver Detalle */}
      {selectedDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-card rounded-xl shadow-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto">
            <div className="p-6 border-b border-default">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-heading">Detalle del Documento</h2>
                <button onClick={closeModals} className="text-muted hover:text-heading">
                  <XCircle className="w-5 h-5" />
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div><span className="text-muted">Correlativo:</span> <code className="font-mono text-heading ml-2">{selectedDoc.correlativo}</code></div>
                <div><span className="text-muted">Tipo:</span> <span className="ml-2"><span className="badge badge-gray">{selectedDoc.tipo_doc_codigo || selectedDoc.tipo_documento}</span></span></div>
                <div className="md:col-span-2"><span className="text-muted">Oficinas:</span> <span className="ml-2">{selectedDoc.oficina_origen_sigla || selectedDoc.oficina_origen} → {selectedDoc.oficina_destino_sigla || selectedDoc.oficina_destino}</span></div>
                <div><span className="text-muted">Fecha Documento:</span> <span className="ml-2">{selectedDoc.fecha_documento ? (() => { const [y,m,d] = selectedDoc.fecha_documento.split('-').map(Number); return format(new Date(y, m-1, d), 'dd/MM/yyyy', { locale: es }) })() : '-'}</span></div>
                <div><span className="text-muted">Fecha Recepción:</span> <span className="ml-2">{selectedDoc.fecha_recepcion ? (() => { const [y,m,d] = selectedDoc.fecha_recepcion.split('-').map(Number); return format(new Date(y, m-1, d), 'dd/MM/yyyy', { locale: es }) })() : '-'}</span></div>
                <div className="md:col-span-2"><span className="text-muted">Remitente:</span> <span className="ml-2">{selectedDoc.remitente || selectedDoc.remitente_id || '-'}</span></div>
                <div className="md:col-span-2"><span className="text-muted">Destinatario:</span> <span className="ml-2">{selectedDoc.destinatario || selectedDoc.destinatario_id || '-'}</span></div>
                <div className="md:col-span-2"><span className="text-muted">Asunto:</span> <p className="mt-1 text-heading">{selectedDoc.asunto || '-'}</p></div>
                <div><span className="text-muted">Folios:</span> <span className="ml-2">{selectedDoc.folios || '-'}</span></div>
                <div><span className="text-muted">Prioridad:</span> <span className="ml-2">{selectedDoc.prioridad || 'NORMAL'}</span></div>
                <div className="md:col-span-2"><span className="text-muted">Estado:</span> <span className="ml-2"><span className={`badge ${ESTADO_COLORES[selectedDoc.estado] || 'badge-gray'}`}>{selectedDoc.estado}</span></span></div>
                <div className="md:col-span-2"><span className="text-muted">Confianza OCR:</span> <span className="ml-2">{selectedDoc.confianza_ocr ? `${selectedDoc.confianza_ocr}%` : '-'}</span></div>
                <div className="md:col-span-2"><span className="text-muted">Observaciones:</span> <p className="mt-1 text-muted">{selectedDoc.observaciones || '-'}</p></div>
                <div><span className="text-muted">Creado:</span> <span className="ml-2">{selectedDoc.creado_en ? format(new Date(selectedDoc.creado_en), 'dd/MM/yyyy HH:mm', { locale: es }) : '-'}</span></div>
                <div><span className="text-muted">Actualizado:</span> <span className="ml-2">{selectedDoc.actualizado_en ? format(new Date(selectedDoc.actualizado_en), 'dd/MM/yyyy HH:mm', { locale: es }) : '-'}</span></div>
              </div>
            </div>
            <div className="p-4 border-t border-default flex justify-end gap-2">
              <button onClick={() => { openEdit(selectedDoc); setSelectedDoc(null); }} className="btn-primary">Editar</button>
              <button onClick={closeModals} className="btn-secondary">Cerrar</button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Editar */}
      {editingDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-card rounded-xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-default">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-heading">Editar Documento</h2>
                <button onClick={closeModals} className="text-muted hover:text-heading">
                  <XCircle className="w-5 h-5" />
                </button>
              </div>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="label">Correlativo</label>
                  <input
                    type="text"
                    value={formData.correlativo}
                    onChange={(e) => setFormData({ ...formData, correlativo: e.target.value })}
                    className="input"
                    required
                  />
                </div>
                <div>
                  <label className="label">Tipo Documento</label>
                  <select
                    value={formData.tipo_doc_codigo}
                    onChange={(e) => setFormData({ ...formData, tipo_doc_codigo: e.target.value })}
                    className="input"
                    required
                  >
                    {TIPOS_DOCUMENTO.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label">Oficina Origen</label>
                  <input
                    type="text"
                    value={formData.oficina_origen_sigla}
                    onChange={(e) => setFormData({ ...formData, oficina_origen_sigla: e.target.value })}
                    className="input"
                    placeholder="OTIC"
                    required
                  />
                </div>
                <div>
                  <label className="label">Oficina Destino</label>
                  <input
                    type="text"
                    value={formData.oficina_destino_sigla}
                    onChange={(e) => setFormData({ ...formData, oficina_destino_sigla: e.target.value })}
                    className="input"
                    placeholder="OGA"
                    required
                  />
                </div>
                <div>
                  <label className="label">Fecha Documento</label>
                  <input
                    type="date"
                    value={formData.fecha_documento}
                    onChange={(e) => setFormData({ ...formData, fecha_documento: e.target.value })}
                    className="input"
                    required
                  />
                </div>
                <div>
                  <label className="label">Fecha Recepción</label>
                  <input
                    type="date"
                    value={formData.fecha_recepcion}
                    onChange={(e) => setFormData({ ...formData, fecha_recepcion: e.target.value })}
                    className="input"
                  />
                </div>
                <div>
                  <label className="label">Remitente</label>
                  <input
                    type="text"
                    value={formData.remitente}
                    onChange={(e) => setFormData({ ...formData, remitente: e.target.value })}
                    className="input"
                    placeholder="Nombre del remitente"
                  />
                </div>
                <div>
                  <label className="label">Destinatario</label>
                  <input
                    type="text"
                    value={formData.destinatario}
                    onChange={(e) => setFormData({ ...formData, destinatario: e.target.value })}
                    className="input"
                    placeholder="Nombre del destinatario"
                  />
                </div>
              </div>
              <div>
                <label className="label">Asunto</label>
                <input
                  type="text"
                  value={formData.asunto}
                  onChange={(e) => setFormData({ ...formData, asunto: e.target.value })}
                  className="input"
                  placeholder="Asunto del documento"
                  required
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                                <label className="label">Folios</label>
                                <input
                                  type="number"
                                  value={formData.folios}
                                  onChange={(e) => setFormData({ ...formData, folios: parseInt(e.target.value) || 0 })}
                                  className="input"
                                  min={0}
                                />
                              </div>
                <div>
                  <label className="label">Prioridad</label>
                  <select
                    value={formData.prioridad}
                    onChange={(e) => setFormData({ ...formData, prioridad: e.target.value })}
                    className="input"
                  >
                    <option value="NORMAL">Normal</option>
                    <option value="URGENTE">Urgente</option>
                    <option value="BAJA">Baja</option>
                  </select>
                </div>
                <div>
                  <label className="label">Estado</label>
                  <select
                    value={formData.estado}
                    onChange={(e) => setFormData({ ...formData, estado: e.target.value })}
                    className="input"
                  >
                    {Object.keys(ESTADO_COLORES).map(e => <option key={e} value={e}>{e}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="label">Observaciones</label>
                <textarea
                  value={formData.observaciones}
                  onChange={(e) => setFormData({ ...formData, observaciones: e.target.value })}
                  className="input"
                  rows={3}
                  placeholder="Observaciones adicionales..."
                />
              </div>
              <div className="flex gap-2 pt-4 border-t border-default">
                <button
                  type="button"
                  onClick={closeModals}
                  className="btn-secondary flex-1"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={updateMutation.isPending}
                  className="btn-primary flex-1"
                >
                  {updateMutation.isPending ? (
                    <span className="flex items-center justify-center gap-2">
                      <Loader2Icon className="w-4 h-4 animate-spin" />
                      Guardando...
                    </span>
                  ) : (
                    'Guardar Cambios'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
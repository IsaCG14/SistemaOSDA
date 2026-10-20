import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { EmptyState } from '../components/EmptyState'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import {
  FileText, Building2, Clock, AlertCircle, CheckCircle,
  TrendingUp, TrendingDown, Minus, Plus, Search, Filter, Download, Calendar,
  Loader2
} from 'lucide-react'
import { useState, useEffect } from 'react'
import { Documento } from '../types'
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

const COLORS_METRIC: Record<string, string> = {
  blue: 'bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400',
  green: 'bg-green-50 text-green-600 dark:bg-green-900/30 dark:text-green-400',
  yellow: 'bg-yellow-50 text-yellow-600 dark:bg-yellow-900/30 dark:text-yellow-400',
  purple: 'bg-purple-50 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400',
  red: 'bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-400',
}

interface Oficina {
  sigla: string
  nombre: string
  activa: boolean
}

interface TipoDocumento {
  codigo: string
  nombre: string
}

export function DashboardPage() {
  const [fechaDesde, setFechaDesde] = useState('')
  const [fechaHasta, setFechaHasta] = useState('')
  const [oficinaFiltro, setOficinaFiltro] = useState('')
  const [tipoFiltro, setTipoFiltro] = useState('')
  const [exportando, setExportando] = useState(false)

  // Exportar a Excel los documentos que matchean los filtros del Dashboard
  const handleExportar = async () => {
    setExportando(true)
    try {
      const total = await exportarDocumentosExcel(async (limit, offset) => {
        const params = new URLSearchParams()
        if (fechaDesde) params.append('fecha_desde', fechaDesde)
        if (fechaHasta) params.append('fecha_hasta', fechaHasta)
        if (oficinaFiltro) params.append('oficina_origen', oficinaFiltro)
        if (tipoFiltro) params.append('tipo_documento', tipoFiltro)
        params.append('limit', limit.toString())
        params.append('offset', offset.toString())
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

  // Fetch oficinas for select
  const { data: oficinas = [] } = useQuery({
    queryKey: ['oficinas-select'],
    queryFn: async () => {
      const resp = await api.get('/oficinas')
      return resp.data as Oficina[]
    },
    select: (data) => data.filter(o => o.activa).sort((a, b) => a.sigla.localeCompare(b.sigla))
  })

  // Fetch tipos de documento for select
  const { data: tiposDocumento = [] } = useQuery({
    queryKey: ['tipos-documento-select'],
    queryFn: async () => {
      const resp = await api.get('/tipos-documento')
      return resp.data as TipoDocumento[]
    },
    select: (data) => data.sort((a, b) => a.codigo.localeCompare(b.codigo))
  })

  const { data: metricas, isLoading: loadingMetricas } = useQuery({
    queryKey: ['metricas', fechaDesde, fechaHasta, oficinaFiltro, tipoFiltro],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (fechaDesde) params.append('fecha_desde', fechaDesde)
      if (fechaHasta) params.append('fecha_hasta', fechaHasta)
      if (oficinaFiltro) params.append('oficina_origen', oficinaFiltro)
      if (tipoFiltro) params.append('tipo_documento', tipoFiltro)
      const resp = await api.get(`/documentos/metricas?${params}`)
      return resp.data
    },
  })

  const { data: documentosRecientes, isLoading: loadingDocs } = useQuery({
    queryKey: ['documentos-recientes', fechaDesde, fechaHasta, oficinaFiltro, tipoFiltro],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (fechaDesde) params.append('fecha_desde', fechaDesde)
      if (fechaHasta) params.append('fecha_hasta', fechaHasta)
      if (oficinaFiltro) params.append('oficina_origen', oficinaFiltro)
      if (tipoFiltro) params.append('tipo_documento', tipoFiltro)
      params.append('limit', '10')
      params.append('offset', '0')
      const resp = await api.get(`/documentos?${params}`)
      return resp.data
    },
  })

  const { data: pendientes } = useQuery({
    queryKey: ['pendientes'],
    queryFn: async () => {
      const resp = await api.get('/consultas/pendientes')
      return resp.data
    },
  })

  if (loadingMetricas) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6 bg-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-heading">Dashboard</h1>
          <p className="text-muted mt-1">Resumen de gestión documental</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => handleExportar()}
            disabled={exportando}
            className="btn-secondary flex items-center gap-2"
          >
            {exportando ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            {exportando ? 'Exportando...' : 'Exportar Excel'}
          </button>
        </div>
      </div>

      {/* Filtros */}
      <div className="card p-4">
        <div className="flex flex-col sm:flex-row gap-4">
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
          <div className="flex-1">
            <label className="label">Oficina origen</label>
            <select
              value={oficinaFiltro}
              onChange={(e) => setOficinaFiltro(e.target.value)}
              className="input"
            >
              <option value="">Todas las oficinas</option>
              {oficinas.map(o => (
                <option key={o.sigla} value={o.sigla}>{o.sigla} - {o.nombre}</option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <label className="label">Tipo documento</label>
            <select
              value={tipoFiltro}
              onChange={(e) => setTipoFiltro(e.target.value)}
              className="input"
            >
              <option value="">Todos los tipos</option>
              {tiposDocumento.map(t => (
                <option key={t.codigo} value={t.codigo}>{t.codigo} - {t.nombre}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Métricas principales */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Documentos"
          value={metricas?.total || 0}
          icon={FileText}
          color="blue"
          trend={metricas?.tendencia_total}
        />
        <MetricCard
          title="Este Mes"
          value={metricas?.este_mes || 0}
          icon={Calendar}
          color="green"
          trend={metricas?.tendencia_mes}
        />
        <MetricCard
          title="Pendientes"
          value={pendientes?.length || 0}
          icon={Clock}
          color="yellow"
          trend={metricas?.tendencia_pendientes}
        />
        <MetricCard
          title="Oficinas Activas"
          value={metricas?.oficinas_activas || 0}
          icon={Building2}
          color="purple"
        />
      </div>

      {/* Gráficos / Documentos por estado */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <div className="p-4 border-b border-default">
            <h2 className="text-lg font-semibold text-heading">Documentos por Estado</h2>
          </div>
          <div className="p-4 space-y-3">
            {metricas?.por_estado?.map((item: any) => (
              <div key={item.estado} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className={`badge ${ESTADO_COLORES[item.estado] || 'badge-gray'}`}>
                    {item.estado}
                  </span>
                </div>
                <div className="flex items-center gap-4">
                  <div className="w-32 h-2 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-600 rounded-full transition-all"
                      style={{ width: `${(item.count / (metricas.total || 1)) * 100}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium text-heading w-12 text-right">
                    {item.count}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="p-4 border-b border-default">
            <h2 className="text-lg font-semibold text-heading">Documentos por Oficina (Origen)</h2>
          </div>
          <div className="p-4 space-y-3">
            {metricas?.por_oficina_origen?.map((item: any) => (
              <div key={item.oficina} className="flex items-center justify-between">
                <span className="text-sm font-medium text-heading">{item.oficina}</span>
                <span className="text-sm text-muted">{item.count} docs</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Documentos recientes */}
      <div className="card">
        <div className="p-4 border-b border-default flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <h2 className="text-lg font-semibold text-heading">Documentos Recientes</h2>
          <a href="/documentos" className="link">
            Ver todos →
          </a>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-default">
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Correlativo</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Tipo</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Oficinas</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Fecha</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Estado</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Asunto</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-default">
              {documentosRecientes?.map((doc: Documento) => (
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
                    {doc.fecha_documento ? (() => { const [y,m,d] = doc.fecha_documento.split('-').map(Number); return format(new Date(y, m-1, d), 'dd/MM/yyyy', { locale: es }) })() : '-'}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`badge ${ESTADO_COLORES[doc.estado] || 'badge-gray'}`}>
                      {doc.estado}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted max-w-xs truncate">
                    {doc.asunto || '-'}
                  </td>
                </tr>
              ))}
              {!documentosRecientes?.length && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted">
                    No hay documentos recientes
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function MetricCard({ title, value, icon: Icon, color, trend }: any) {
  const bgColor = COLORS_METRIC[color] || COLORS_METRIC.blue

  return (
    <div className="card p-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-muted">{title}</p>
          <p className="text-3xl font-bold text-heading mt-1">{value.toLocaleString()}</p>
          {trend !== undefined && (
            <p className={`text-sm mt-1 flex items-center gap-1 ${trend >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
              {trend >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
              <span>{Math.abs(trend)}%</span> vs mes anterior
            </p>
          )}
        </div>
        <div className={`p-3 rounded-xl ${bgColor}`}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </div>
  )
}
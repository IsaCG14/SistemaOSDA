import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { useState } from 'react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { 
  Search, Filter, Download, Clock, FileText, Building2, 
  ArrowRight, ArrowLeft, RefreshCw, Loader2
} from 'lucide-react'
import { Documento } from '../types'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { EmptyState } from '../components/EmptyState'

const ESTADO_COLORES: Record<string, string> = {
  RECIBIDO: 'badge-info',
  EN_TRAMITE: 'badge-warning',
  RESPONDIDO: 'badge-success',
  ARCHIVADO: 'badge-gray',
  DERIVADO: 'badge-info',
  RECHAZADO: 'badge-danger',
  EXTRAVIADO: 'badge-danger',
}

export function ConsultasPage() {
  const [activeTab, setActiveTab] = useState<'pendientes' | 'trace' | 'correlativo' | 'oficina'>('pendientes')
  const [traceCorrelativo, setTraceCorrelativo] = useState('')
  const [correlativoOficina, setCorrelativoOficina] = useState('')
  const [correlativoTipo, setCorrelativoTipo] = useState('')
  const [oficinaConsulta, setOficinaConsulta] = useState('')
  const [mesConsulta, setMesConsulta] = useState(new Date().getMonth() + 1)
  const [anioConsulta, setAnioConsulta] = useState(new Date().getFullYear())

  // Consultas reactivas
  const { data: pendientes, isLoading: loadingPendientes } = useQuery({
    queryKey: ['pendientes'],
    queryFn: async () => {
      const resp = await api.get('/consultas/pendientes')
      return resp.data
    },
    enabled: activeTab === 'pendientes',
  })

  const { data: trace, isLoading: loadingTrace } = useQuery({
    queryKey: ['trace', traceCorrelativo],
    queryFn: async () => {
      const resp = await api.get(`/consultas/trace/${traceCorrelativo}`)
      return resp.data
    },
    enabled: activeTab === 'trace' && traceCorrelativo.length > 0,
  })

  const { data: ultimoCorrelativo, isLoading: loadingCorrelativo } = useQuery({
    queryKey: ['ultimo-correlativo', correlativoOficina, correlativoTipo],
    queryFn: async () => {
      const resp = await api.get('/consultas/ultimo-correlativo', {
        params: { oficina: correlativoOficina, tipo_documento: correlativoTipo }
      })
      return resp.data
    },
    enabled: activeTab === 'correlativo' && !!correlativoOficina && !!correlativoTipo,
  })

  const { data: porOficina, isLoading: loadingOficina } = useQuery({
    queryKey: ['por-oficina', oficinaConsulta, mesConsulta, anioConsulta],
    queryFn: async () => {
      const resp = await api.get('/consultas/por-oficina', {
        params: { oficina: oficinaConsulta, mes: mesConsulta, anio: anioConsulta }
      })
      return resp.data
    },
    enabled: activeTab === 'oficina' && !!oficinaConsulta,
  })

  const tabs = [
    { id: 'pendientes', label: 'Pendientes', icon: Clock },
    { id: 'trace', label: 'Trazabilidad', icon: ArrowRight },
    { id: 'correlativo', label: 'Último Correlativo', icon: FileText },
    { id: 'oficina', label: 'Por Oficina', icon: Building2 },
  ]

  return (
    <div className="space-y-6 bg-page">
      <div>
        <h1 className="text-2xl font-bold text-heading">Consultas Avanzadas</h1>
        <p className="text-muted mt-1">Consultas rápidas mediante Graphify</p>
      </div>

      {/* Tabs */}
      <div className="card">
        <div className="border-b border-default">
          <nav className="flex overflow-x-auto" aria-label="Tabs">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                    : 'border-transparent text-muted hover:text-heading hover:border-default'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        <div className="p-4">
          {activeTab === 'pendientes' && (
            <PendientesPanel data={pendientes} loading={loadingPendientes} />
          )}
          {activeTab === 'trace' && (
            <TracePanel 
              correlativo={traceCorrelativo} 
              setCorrelativo={setTraceCorrelativo}
              data={trace} 
              loading={loadingTrace} 
            />
          )}
          {activeTab === 'correlativo' && (
            <CorrelativoPanel
              oficina={correlativoOficina}
              setOficina={setCorrelativoOficina}
              tipo={correlativoTipo}
              setTipo={setCorrelativoTipo}
              data={ultimoCorrelativo}
              loading={loadingCorrelativo}
            />
          )}
          {activeTab === 'oficina' && (
            <OficinaPanel
              oficina={oficinaConsulta}
              setOficina={setOficinaConsulta}
              mes={mesConsulta}
              setMes={setMesConsulta}
              anio={anioConsulta}
              setAnio={setAnioConsulta}
              data={porOficina}
              loading={loadingOficina}
            />
          )}
        </div>
      </div>
    </div>
  )
}

function PendientesPanel({ data, loading }: any) {
  if (loading) {
    return <div className="flex justify-center py-8"><LoadingSpinner /></div>
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-heading">
          Documentos Pendientes de Respuesta ({data?.length || 0})
        </h2>
      </div>
      {data?.length ? (
        <div className="space-y-3">
          {data.map((doc: any) => (
            <div key={doc.id || doc.correlativo} className="card p-4 card-hover">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 flex-wrap">
                    <code className="text-sm font-mono text-heading bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded">
                      {doc.correlativo}
                    </code>
                    <span className={`badge ${ESTADO_COLORES[doc.estado] || 'badge-gray'}`}>
                      {doc.estado}
                    </span>
                    <span className="badge badge-gray">{doc.tipo_documento}</span>
                  </div>
                  <p className="text-sm text-muted mt-1 truncate">{doc.asunto}</p>
                  <div className="flex items-center gap-4 mt-2 text-sm text-muted">
                    <span className="flex items-center gap-1">
                      <Building2 className="w-3 h-3" />
                      {doc.oficina_origen_sigla} → {doc.oficina_destino_sigla}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      Recibido: {doc.fecha_recepcion ? format(new Date(doc.fecha_recepcion), 'dd/MM/yyyy', { locale: es }) : '-'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Clock}
          title="No hay documentos pendientes"
          description="Todos los documentos están al día"
        />
      )}
    </div>
  )
}

function TracePanel({ correlativo, setCorrelativo, data, loading }: any) {
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (correlativo.trim()) {
      // Trigger query refetch via key change
    }
  }

  return (
    <div>
      <form onSubmit={handleSearch} className="mb-6">
        <div className="flex gap-4">
          <div className="flex-1">
            <label className="label">Correlativo a rastrear</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={correlativo}
                onChange={(e) => setCorrelativo(e.target.value.toUpperCase())}
                className="input font-mono"
                placeholder="OTIC-MEMO-2026-0001"
              />
              <button type="submit" className="btn-primary flex items-center gap-2">
                <Search className="w-4 h-4" />
                Buscar
              </button>
            </div>
          </div>
        </div>
      </form>

      {loading && <div className="flex justify-center py-8"><LoadingSpinner /></div>}

      {data && !loading && (
        <div className="space-y-6">
          <div className="card">
            <div className="p-4 border-b border-default">
              <h3 className="text-lg font-semibold text-heading">Documento Principal</h3>
            </div>
            <div className="p-4">
              <TraceDocumento doc={data.documento} />
            </div>
          </div>

          {data.respuestas?.length && (
            <div className="card">
              <div className="p-4 border-b border-default">
                <h3 className="text-lg font-semibold text-heading">
                  Respuestas ({data.respuestas.length})
                </h3>
              </div>
              <div className="p-4 space-y-3">
                {data.respuestas.map((doc: any) => (
                  <div key={doc.id} className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <TraceDocumento doc={doc} compact />
                  </div>
                ))}
              </div>
            </div>
          )}

          {data.referencias?.length && (
            <div className="card">
              <div className="p-4 border-b border-default">
                <h3 className="text-lg font-semibold text-heading">
                  Referencias ({data.referencias.length})
                </h3>
              </div>
              <div className="p-4 space-y-3">
                {data.referencias.map((doc: any) => (
                  <div key={doc.id} className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <TraceDocumento doc={doc} compact />
                  </div>
                ))}
              </div>
            </div>
          )}

          {data.anexos?.length && (
            <div className="card">
              <div className="p-4 border-b border-default">
                <h3 className="text-lg font-semibold text-heading">
                  Anexos ({data.anexos.length})
                </h3>
              </div>
              <div className="p-4 space-y-3">
                {data.anexos.map((doc: any) => (
                  <div key={doc.id} className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <TraceDocumento doc={doc} compact />
                  </div>
                ))}
              </div>
            </div>
          )}

          {data.flujo_oficinas?.length && (
            <div className="card">
              <div className="p-4 border-b border-default">
                <h3 className="text-lg font-semibold text-heading">Flujo de Oficinas</h3>
              </div>
              <div className="p-4 space-y-3">
                {data.flujo_oficinas.map((f: any, i: number) => (
                  <div key={i} className="flex items-center gap-4 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <span className={`badge ${f.tipo === 'origen' ? 'badge-info' : 'badge-success'}`}>
                      {f.tipo === 'origen' ? 'Origen' : 'Destino'}
                    </span>
                    <div className="flex-1">
                      <p className="font-medium text-heading">{f.oficina?.nombre || f.oficina?.sigla}</p>
                      <p className="text-sm text-muted">
                        {f.personas?.length} persona(s) asociada(s)
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!data && !loading && correlativo && (
        <EmptyState
          icon={FileText}
          title="Documento no encontrado"
          description={`No se encontró trazabilidad para ${correlativo}`}
        />
      )}
    </div>
  )
}

function TraceDocumento({ doc, compact }: any) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <code className="text-sm font-mono text-heading">{doc.correlativo}</code>
          <span className={`badge ${ESTADO_COLORES[doc.estado] || 'badge-gray'}`}>
            {doc.estado}
          </span>
          <span className="badge badge-gray">{doc.tipo_documento}</span>
        </div>
        {!compact && (
          <p className="text-sm text-muted mt-1 truncate">{doc.asunto}</p>
        )}
        <div className="flex items-center gap-4 mt-1 text-sm text-muted">
          <span>{doc.oficina_origen_sigla} → {doc.oficina_destino_sigla}</span>
          <span>{doc.fecha_documento ? format(new Date(doc.fecha_documento), 'dd/MM/yyyy', { locale: es }) : '-'}</span>
        </div>
      </div>
    </div>
  )
}

function CorrelativoPanel({ oficina, setOficina, tipo, setTipo, data, loading }: any) {
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
  }

  return (
    <div>
      <form onSubmit={handleSearch} className="mb-6">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="label">Oficina</label>
            <input
              type="text"
              value={oficina}
              onChange={(e) => setOficina(e.target.value.toUpperCase())}
              className="input font-mono"
              placeholder="OTIC"
            />
          </div>
          <div>
            <label className="label">Tipo de Documento</label>
            <input
              type="text"
              value={tipo}
              onChange={(e) => setTipo(e.target.value.toUpperCase())}
              className="input font-mono"
              placeholder="MEMO"
            />
          </div>
          <div className="flex items-end">
            <button type="submit" className="btn-primary w-full flex items-center justify-center gap-2">
              <Search className="w-4 h-4" />
              Consultar
            </button>
          </div>
        </div>
      </form>

      {loading && <div className="flex justify-center py-8"><LoadingSpinner /></div>}

      {data && !loading && (
        <div className="card">
          <div className="p-4">
            {data.correlativo ? (
              <div className="text-center">
                <p className="text-sm text-muted">Último correlativo registrado</p>
                <code className="text-3xl font-mono text-blue-600 dark:text-blue-400 block mt-2">{data.correlativo}</code>
                <p className="text-sm text-muted mt-2">
                  Fecha: {data.fecha ? format(new Date(data.fecha), 'dd/MM/yyyy', { locale: es }) : 'N/A'}
                </p>
              </div>
            ) : (
              <div className="text-center text-muted py-8">
                <FileText className="w-12 h-12 mx-auto mb-4 text-muted" />
                <p>No hay correlativos registrados para {oficina} - {tipo}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function OficinaPanel({ oficina, setOficina, mes, setMes, anio, setAnio, data, loading }: any) {
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
  }

  return (
    <div>
      <form onSubmit={handleSearch} className="mb-6">
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div>
            <label className="label">Oficina</label>
            <input
              type="text"
              value={oficina}
              onChange={(e) => setOficina(e.target.value.toUpperCase())}
              className="input font-mono"
              placeholder="OTIC"
            />
          </div>
          <div>
            <label className="label">Mes</label>
            <select
              value={mes}
              onChange={(e) => setMes(parseInt(e.target.value))}
              className="input"
            >
              {Array.from({ length: 12 }, (_, i) => i + 1).map(m => (
                <option key={m} value={m}>
                  {m.toString().padStart(2, '0')} - {new Date(2024, m - 1).toLocaleString('es', { month: 'long' })}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Año</label>
            <select
              value={anio}
              onChange={(e) => setAnio(parseInt(e.target.value))}
              className="input"
            >
              {Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i).map(a => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <button type="submit" className="btn-primary w-full flex items-center justify-center gap-2">
              <Search className="w-4 h-4" />
              Consultar
            </button>
          </div>
        </div>
      </form>

      {loading && <div className="flex justify-center py-8"><LoadingSpinner /></div>}

      {data && !loading && (
        <div>
          {data.length ? (
            <div className="card">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-default">
                      <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Correlativo</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Tipo</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Fecha</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Estado</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Asunto</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-default">
                    {data.map((doc: any) => (
                      <tr key={doc.id} className="card-hover">
                        <td className="px-4 py-3"><code className="text-sm font-mono text-heading">{doc.correlativo}</code></td>
                        <td className="px-4 py-3"><span className="badge badge-gray">{doc.tipo_documento}</span></td>
                        <td className="px-4 py-3 text-sm text-muted">
                          {doc.fecha_documento ? format(new Date(doc.fecha_documento), 'dd/MM/yyyy', { locale: es }) : '-'}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`badge ${ESTADO_COLORES[doc.estado] || 'badge-gray'}`}>{doc.estado}</span>
                        </td>
                        <td className="px-4 py-3 text-sm text-muted max-w-xs truncate">{doc.asunto || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <EmptyState
              icon={Building2}
              title="Sin resultados"
              description={`No hay documentos para ${oficina} en ${mes}/${anio}`}
            />
          )}
        </div>
      )}
    </div>
  )
}
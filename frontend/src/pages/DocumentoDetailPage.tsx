import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { 
  FileText, Building2, Clock, AlertCircle, CheckCircle, 
  Search, Filter, Download, Eye, Edit, Trash2, Loader2,
  ChevronLeft, ChevronRight, ArrowLeft, Copy
} from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Documento } from '../types'
import { LoadingSpinner } from '../components/LoadingSpinner'

const ESTADO_COLORES: Record<string, string> = {
  RECIBIDO: 'badge-info',
  EN_TRAMITE: 'badge-warning',
  RESPONDIDO: 'badge-success',
  ARCHIVADO: 'badge-gray',
  DERIVADO: 'badge-info',
  RECHAZADO: 'badge-danger',
  EXTRAVIADO: 'badge-danger',
}

import { useParams } from 'react-router-dom'

export function DocumentoDetailPage() {
  const { id } = useParams<{ id: string }>()
  
  const { data: documento, isLoading, error } = useQuery({
    queryKey: ['documento', id],
    queryFn: async () => {
      const resp = await api.get(`/documentos/${id}`)
      return resp.data
    },
    enabled: !!id,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !documento) {
    return (
      <div className="card p-8 text-center">
        <p className="text-red-600">Documento no encontrado</p>
        <Link to="/documentos" className="btn-primary mt-4 inline-block">
          Volver a la lista
        </Link>
      </div>
    )
  }

  const doc = documento as Documento

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link to="/documentos" className="p-2 rounded-lg hover:bg-gray-100">
            <ArrowLeft className="w-5 h-5 text-gray-600" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{doc.correlativo}</h1>
            <p className="text-gray-600 mt-1">{doc.asunto || 'Sin asunto'}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary flex items-center gap-2">
            <Download className="w-4 h-4" />
            Exportar
          </button>
          <button className="btn-primary flex items-center gap-2">
            <Edit className="w-4 h-4" />
            Editar
          </button>
        </div>
      </div>

      {/* Badges de estado y tipo */}
      <div className="flex flex-wrap gap-3">
        <span className={`badge ${ESTADO_COLORES[doc.estado] || 'badge-gray'}`}>
          {doc.estado}
        </span>
        <span className="badge badge-gray">{doc.tipo_documento}</span>
        <span className="badge badge-info">Prioridad: {doc.prioridad || 'NORMAL'}</span>
        {doc.confianza_ocr && (
          <span className="badge badge-gray">OCR: {(doc.confianza_ocr * 100).toFixed(0)}%</span>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Panel principal */}
        <div className="lg:col-span-2 space-y-6">
          {/* Información principal */}
          <div className="card">
            <div className="p-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Información del Documento</h2>
            </div>
            <div className="p-4 space-y-4">
              <InfoRow label="Correlativo" value={doc.correlativo} copyable />
              <InfoRow label="Tipo de documento" value={doc.tipo_documento} />
              <InfoRow label="Fecha del documento" value={doc.fecha_documento ? format(new Date(doc.fecha_documento), 'dd/MM/yyyy', { locale: es }) : '-'} />
              <InfoRow label="Fecha de recepción" value={doc.fecha_recepcion ? format(new Date(doc.fecha_recepcion), 'dd/MM/yyyy', { locale: es }) : '-'} />
              <InfoRow label="Folios" value={doc.folios?.toString() || '-'} />
              <InfoRow label="Anexos" value={doc.anexos?.length ? doc.anexos.join(', ') : '-'} />
              <InfoRow label="Prioridad" value={doc.prioridad || 'NORMAL'} />
            </div>
          </div>

          {/* Oficinas y personas */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="card">
              <div className="p-4 border-b border-gray-200">
                <h2 className="text-lg font-semibold text-gray-900">Oficinas</h2>
              </div>
              <div className="p-4 space-y-3">
                <InfoRow label="Origen" value={doc.oficina_origen} icon={Building2} />
                <InfoRow label="Destino" value={doc.oficina_destino} icon={Building2} />
              </div>
            </div>

            <div className="card">
              <div className="p-4 border-b border-gray-200">
                <h2 className="text-lg font-semibold text-gray-900">Personas</h2>
              </div>
              <div className="p-4 space-y-3">
                <InfoRow label="Remitente" value={doc.remitente || '-'} icon={FileText} />
                <InfoRow label="Destinatario" value={doc.destinatario || '-'} icon={FileText} />
              </div>
            </div>
          </div>

          {/* Asunto y observaciones */}
          <div className="card">
            <div className="p-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Asunto / Referencia</h2>
            </div>
            <div className="p-4">
              <p className="text-gray-700 whitespace-pre-wrap">{doc.asunto || 'Sin asunto'}</p>
            </div>
          </div>

          {doc.observaciones && (
            <div className="card">
              <div className="p-4 border-b border-gray-200">
                <h2 className="text-lg font-semibold text-gray-900">Observaciones</h2>
              </div>
              <div className="p-4">
                <p className="text-gray-700 whitespace-pre-wrap">{doc.observaciones}</p>
              </div>
            </div>
          )}

          {/* Trazabilidad */}
          <div className="card">
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Trazabilidad</h2>
              <button className="btn-secondary text-sm">Ver en Graphify</button>
            </div>
            <div className="p-4">
              <p className="text-gray-500 text-center py-8">
                La trazabilidad completa (respuestas, referencias, anexos, flujo de oficinas)
                se consulta desde el motor Graphify.
              </p>
            </div>
          </div>
        </div>

        {/* Panel lateral - Metadatos */}
        <div className="space-y-4">
          <div className="card">
            <div className="p-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Metadatos</h2>
            </div>
            <div className="p-4 space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">ID</span>
                <code className="text-gray-900 font-mono text-xs">{doc.id}</code>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Creado</span>
                <span className="text-gray-900">{doc.created_at ? format(new Date(doc.created_at), 'dd/MM/yyyy HH:mm', { locale: es }) : '-'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Actualizado</span>
                <span className="text-gray-900">{doc.updated_at ? format(new Date(doc.updated_at), 'dd/MM/yyyy HH:mm', { locale: es }) : '-'}</span>
              </div>
              {doc.confirmado_por && (
                <div className="flex justify-between">
                  <span className="text-gray-500">Confirmado por</span>
                  <span className="text-gray-900">{doc.confirmado_por}</span>
                </div>
              )}
              {doc.confirmado_en && (
                <div className="flex justify-between">
                  <span className="text-gray-500">Confirmado el</span>
                  <span className="text-gray-900">{format(new Date(doc.confirmado_en), 'dd/MM/yyyy HH:mm', { locale: es })}</span>
                </div>
              )}
            </div>
          </div>

          {/* Acciones rápidas */}
          <div className="card">
            <div className="p-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Acciones</h2>
            </div>
            <div className="p-4 space-y-2">
              <button className="btn-secondary w-full justify-start flex items-center gap-2">
                <Eye className="w-4 h-4" />
                Ver en Graphify
              </button>
              <button className="btn-secondary w-full justify-start flex items-center gap-2">
                <FileText className="w-4 h-4" />
                Ver historial de cambios
              </button>
              <button className="btn-secondary w-full justify-start flex items-center gap-2">
                <Download className="w-4 h-4" />
                Exportar a PDF
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function InfoRow({ label, value, icon: Icon, copyable }: any) {
  return (
    <div className="flex items-start gap-4">
      {Icon && <Icon className="w-5 h-5 text-gray-400 flex-shrink-0 mt-0.5" />}
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
        <p className="text-sm text-gray-900 break-words">{value}</p>
      </div>
      {copyable && (
        <button className="p-1 hover:bg-gray-100 rounded text-gray-400" title="Copiar">
          <Copy className="w-4 h-4" />
        </button>
      )}
    </div>
  )
}
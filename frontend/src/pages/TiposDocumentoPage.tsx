import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { useState } from 'react'
import { 
  FileStack, Plus, Edit, Trash2, Search, Loader2,
  Clock, CheckCircle, XCircle
} from 'lucide-react'
import { TipoDocumento } from '../types'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { EmptyState } from '../components/EmptyState'

export function TiposDocumentoPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editingTipo, setEditingTipo] = useState<TipoDocumento | null>(null)
  const [formData, setFormData] = useState({
    codigo: '',
    nombre: '',
    prefijo_correlativo: '',
    plazo_dias_respuesta: 5,
    requiere_anexos: false,
  })

  const { data: tipos, isLoading } = useQuery({
    queryKey: ['tipos-documento'],
    queryFn: async () => {
      const resp = await api.get('/tipos-documento')
      return resp.data
    },
  })

  const createMutation = useMutation({
    mutationFn: async (data: Partial<TipoDocumento>) => {
      const resp = await api.post('/tipos-documento', data)
      return resp.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tipos-documento'] })
      setShowModal(false)
      resetForm()
    },
  })

  const updateMutation = useMutation({
    mutationFn: async (data: Partial<TipoDocumento> & { id: string }) => {
      const { id, ...rest } = data
      const resp = await api.put(`/tipos-documento/${id}`, rest)
      return resp.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tipos-documento'] })
      setShowModal(false)
      setEditingTipo(null)
      resetForm()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/tipos-documento/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tipos-documento'] })
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (editingTipo) {
      updateMutation.mutate({ ...formData, id: editingTipo.codigo })
    } else {
      createMutation.mutate(formData)
    }
  }

  const resetForm = () => {
    setFormData({
      codigo: '',
      nombre: '',
      prefijo_correlativo: '',
      plazo_dias_respuesta: 5,
      requiere_anexos: false,
    })
    setEditingTipo(null)
  }

  const openCreate = () => {
    resetForm()
    setShowModal(true)
  }

  const openEdit = (tipo: TipoDocumento) => {
    setEditingTipo(tipo)
    setFormData({
      codigo: tipo.codigo,
      nombre: tipo.nombre,
      prefijo_correlativo: tipo.prefijo_correlativo,
      plazo_dias_respuesta: tipo.plazo_dias_respuesta,
      requiere_anexos: tipo.requiere_anexos,
    })
    setShowModal(true)
  }

  const filteredTipos = tipos?.filter(t => 
    t.codigo.toLowerCase().includes(search.toLowerCase()) ||
    t.nombre.toLowerCase().includes(search.toLowerCase())
  ) || []

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6 bg-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-heading">Tipos de Documento</h1>
          <p className="text-muted mt-1">Catálogo de tipos documentales y sus reglas</p>
        </div>
        <button onClick={openCreate} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          Nuevo Tipo
        </button>
      </div>

      <div className="card p-4">
        <div className="flex gap-4">
          <div className="flex-1">
            <label className="label">Buscar</label>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input"
              placeholder="Buscar por código o nombre..."
            />
          </div>
        </div>
      </div>

      <div className="card">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-default">
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Código</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Nombre</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Prefijo Correlativo</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Plazo (días)</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Requiere Anexos</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-default">
              {filteredTipos.map((tipo: TipoDocumento) => (
                <tr key={tipo.codigo} className="card-hover">
                  <td className="px-4 py-3">
                    <code className="text-sm font-mono text-heading">{tipo.codigo}</code>
                  </td>
                  <td className="px-4 py-3 text-sm text-heading">{tipo.nombre}</td>
                  <td className="px-4 py-3">
                    <code className="text-sm text-muted">{tipo.prefijo_correlativo}</code>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted">{tipo.plazo_dias_respuesta}</td>
                  <td className="px-4 py-3">
                    <span className={`badge ${tipo.requiere_anexos ? 'badge-info' : 'badge-gray'}`}>
                      {tipo.requiere_anexos ? 'Sí' : 'No'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => openEdit(tipo)}
                        className="p-2 rounded-lg btn-ghost"
                        aria-label="Editar"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => deleteMutation.mutate(tipo.codigo)}
                        disabled={deleteMutation.isPending}
                        className="p-2 rounded-lg btn-ghost text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300"
                        aria-label="Eliminar"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!filteredTipos.length && (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center">
                    <EmptyState
                      icon={FileStack}
                      title="No hay tipos de documento"
                      description={search ? 'No se encontraron tipos con ese filtro' : 'Comience creando el primer tipo de documento'}
                      action={<button onClick={openCreate} className="btn-primary">Crear tipo</button>}
                    />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-card rounded-xl shadow-xl max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-heading">
                {editingTipo ? 'Editar Tipo de Documento' : 'Nuevo Tipo de Documento'}
              </h2>
              <button onClick={() => { setShowModal(false); resetForm(); }} className="text-muted hover:text-heading">
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="label">Código</label>
                <input
                  type="text"
                  value={formData.codigo}
                  onChange={(e) => setFormData({ ...formData, codigo: e.target.value.toUpperCase() })}
                  className="input"
                  placeholder="MEMO"
                  maxLength={20}
                  disabled={!!editingTipo}
                  required
                />
              </div>
              <div>
                <label className="label">Nombre</label>
                <input
                  type="text"
                  value={formData.nombre}
                  onChange={(e) => setFormData({ ...formData, nombre: e.target.value })}
                  className="input"
                  placeholder="Memorándum"
                  required
                />
              </div>
              <div>
                <label className="label">Prefijo Correlativo</label>
                <input
                  type="text"
                  value={formData.prefijo_correlativo}
                  onChange={(e) => setFormData({ ...formData, prefijo_correlativo: e.target.value.toUpperCase() })}
                  className="input"
                  placeholder="OTIC-MEMO"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Plazo respuesta (días)</label>
                  <input
                    type="number"
                    value={formData.plazo_dias_respuesta}
                    onChange={(e) => setFormData({ ...formData, plazo_dias_respuesta: parseInt(e.target.value) || 5 })}
                    className="input"
                    min={1}
                    max={365}
                  />
                </div>
                <div className="flex items-end gap-2">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="requiere_anexos"
                      checked={formData.requiere_anexos}
                      onChange={(e) => setFormData({ ...formData, requiere_anexos: e.target.checked })}
                      className="w-4 h-4 text-blue-600 rounded border-default"
                    />
                    <label htmlFor="requiere_anexos" className="text-sm text-muted">Requiere anexos</label>
                  </div>
                </div>
              </div>
              <div className="flex gap-2 pt-4">
                <button
                  type="button"
                  onClick={() => { setShowModal(false); resetForm(); }}
                  className="btn-secondary flex-1"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending || updateMutation.isPending}
                  className="btn-primary flex-1"
                >
                  {createMutation.isPending || updateMutation.isPending ? (
                    <span className="flex items-center justify-center gap-2">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Guardando...
                    </span>
                  ) : (
                    'Guardar'
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